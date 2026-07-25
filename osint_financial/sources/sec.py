"""Connecteur SEC EDGAR : ticker→CIK, filings (avec items 8-K), séries XBRL.

Points de sécurité :

* Toutes les URL sont **construites** à partir d'un CIK validé (10 chiffres),
  jamais concaténées avec une chaîne utilisateur.
* Les réponses distantes sont traitées comme hostiles : typage vérifié champ
  par champ, listes plafonnées, chaînes tronquées.
* Le cache disque est écrit atomiquement dans un répertoire confiné.

Ce que ce module apporte par rapport à la version précédente, pour honorer les
règles annoncées dans le guide :

* la colonne ``items`` des 8-K est lue, ce qui rend réellement calculable
  « SI 8-K ET items ∈ {1.01, 2.01, 7.01, 8.01} → ALERTE FORTE » et
  « item 3.02 → dilution » ;
* les faits XBRL sont extraits en **séries temporelles** et non plus seulement
  en dernière valeur, ce qui permet la croissance du chiffre d'affaires, le
  suivi du nombre d'actions (dilution) et le flux de trésorerie disponible du
  DCF.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ..errors import DataUnavailable, OsintError
from ..httpclient import HttpClient
from ..logging_setup import get_logger
from ..validation import validate_cik

log = get_logger(__name__)

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_CACHE_TTL_SECONDS = 24 * 3600
_MAX_FILINGS = 60
_MAX_STR = 300

#: Formulaires porteurs de signal, avec leur poids d'attention (cf. §5 du guide).
FILING_SIGNAL = {
    "8-K": 3,
    "10-K": 3,
    "10-Q": 2,
    "4": 3,
    "SC 13D": 3,
    "SC 13G": 2,
    "DEF 14A": 1,
    "144": 1,
}

#: Items 8-K déclenchant une alerte forte (§5 du guide).
ALERT_ITEMS = frozenset({"1.01", "2.01", "7.01", "8.01"})
#: Item 8-K signalant une émission de titres non enregistrée (dilution).
DILUTION_ITEM = "3.02"
#: Libellés des items les plus significatifs, pour l'affichage.
ITEM_LABELS = {
    "1.01": "accord important conclu",
    "1.02": "résiliation d'un accord important",
    "2.01": "acquisition ou cession d'actifs",
    "2.02": "résultats publiés",
    "3.02": "émission de titres non enregistrée (dilution)",
    "4.01": "changement de commissaire aux comptes",
    "5.02": "changement de dirigeant",
    "7.01": "communication réglementée",
    "8.01": "autre événement important",
}

#: Concepts XBRL exploités, par ordre de préférence.
CONCEPTS: dict[str, tuple[str, ...]] = {
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "assets_current": ("AssetsCurrent",),
    "liabilities_current": ("LiabilitiesCurrent",),
    "equity": ("StockholdersEquity",),
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss",),
    "eps": ("EarningsPerShareDiluted", "EarningsPerShareBasic"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "long_term_debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    "shares": (
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "CommonStockSharesOutstanding",
    ),
}

_UNITLESS_KEYS = frozenset({"shares"})


@dataclass(frozen=True)
class Filing:
    form: str
    filed_at: date | None
    accession: str
    primary_document: str
    description: str
    url: str | None
    items: tuple[str, ...] = ()

    @property
    def signal_weight(self) -> int:
        return FILING_SIGNAL.get(self.form.upper(), 0)

    @property
    def is_alert(self) -> bool:
        """8-K portant au moins un item d'alerte forte."""
        return self.form.upper() == "8-K" and bool(ALERT_ITEMS.intersection(self.items))

    @property
    def is_dilution(self) -> bool:
        return self.form.upper() == "8-K" and DILUTION_ITEM in self.items

    def item_labels(self) -> list[str]:
        return [f"{code} — {ITEM_LABELS[code]}" for code in self.items if code in ITEM_LABELS]


@dataclass(frozen=True)
class FactPoint:
    """Une observation XBRL datée."""

    end: str
    value: float
    form: str
    fiscal_year: int | None = None
    fiscal_period: str | None = None

    @property
    def is_annual(self) -> bool:
        return self.form.upper().startswith("10-K")


@dataclass
class SecProfile:
    cik: str
    ticker: str
    company_name: str
    sic_description: str | None = None
    filings: list[Filing] = field(default_factory=list)
    facts: dict[str, float] = field(default_factory=dict)
    fact_dates: dict[str, str] = field(default_factory=dict)
    series: dict[str, list[FactPoint]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _as_str(value: Any, limit: int = _MAX_STR) -> str:
    """Convertit une valeur distante en chaîne bornée et sans contrôle."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = "".join(ch for ch in text if ch == "\n" or ch >= " ")
    text = " ".join(text.split())
    return text[:limit]


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value.replace(",", "").strip())
        except ValueError:
            return None
    else:
        return None
    # NaN/inf casseraient silencieusement toutes les comparaisons du scoring.
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _parse_date(value: Any) -> date | None:
    text = _as_str(value, 32)
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_items(raw: Any) -> tuple[str, ...]:
    """Découpe la colonne ``items`` (« 1.01,9.01 » ou « Item 1.01 »)."""
    text = _as_str(raw, 200)
    if not text:
        return ()
    codes: list[str] = []
    for chunk in text.replace(";", ",").split(","):
        token = chunk.strip().lower().removeprefix("item").strip()
        # Un item est de la forme N.NN.
        parts = token.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            code = f"{int(parts[0])}.{parts[1][:2].ljust(2, '0')}"
            if code not in codes:
                codes.append(code)
    return tuple(codes[:12])


class SecClient:
    """Accès en lecture seule à l'API publique EDGAR."""

    def __init__(self, http: HttpClient, cache_dir: Path | None = None) -> None:
        self.http = http
        self.cache_dir = cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    # -------------------------------------------------------------- cache

    def _cached_json(self, name: str, url: str) -> Any:
        if self.cache_dir is None:
            return self.http.get_json(url)
        path = self.cache_dir / f"{name}.json"
        if path.is_file() and (time.time() - path.stat().st_mtime) < _CACHE_TTL_SECONDS:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                log.debug("cache %s illisible, rechargement", name)
        payload = self.http.get_json(url)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
        return payload

    # ------------------------------------------------------------ ticker

    def resolve_cik(self, ticker: str) -> tuple[str, str]:
        """Retourne ``(cik10, raison_sociale)`` pour un ticker validé."""
        payload = self._cached_json("company_tickers", TICKER_MAP_URL)
        if not isinstance(payload, dict):
            raise OsintError("format inattendu pour la table des tickers SEC")

        for entry in payload.values():
            if not isinstance(entry, dict):
                continue
            if _as_str(entry.get("ticker"), 16).upper() == ticker:
                return validate_cik(entry.get("cik_str")), _as_str(entry.get("title"), 160)
        raise DataUnavailable(f"ticker {ticker} absent du référentiel SEC")

    # ----------------------------------------------------------- filings

    def submissions(self, cik: str) -> dict[str, Any]:
        cik = validate_cik(cik)
        payload = self.http.get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        if not isinstance(payload, dict):
            raise OsintError("format inattendu pour les submissions SEC")
        return payload

    @staticmethod
    def parse_filings(payload: dict[str, Any], cik: str) -> list[Filing]:
        """Transforme le bloc ``filings.recent`` (colonnes parallèles) en objets.

        Robuste aux colonnes de longueurs différentes : l'original supposait
        une structure bien formée et aurait levé un ``IndexError``.
        """
        recent = payload.get("filings", {})
        recent = recent.get("recent", {}) if isinstance(recent, dict) else {}
        if not isinstance(recent, dict):
            return []

        def column(name: str) -> list[Any]:
            values = recent.get(name)
            return values if isinstance(values, list) else []

        forms = column("form")
        dates = column("filingDate")
        accessions = column("accessionNumber")
        documents = column("primaryDocument")
        descriptions = column("primaryDocDescription")
        items = column("items")

        def at(values: list[Any], index: int) -> Any:
            return values[index] if index < len(values) else None

        count = min(len(forms), _MAX_FILINGS)
        cik_int = str(int(cik))
        filings: list[Filing] = []
        for index in range(count):
            form = _as_str(at(forms, index), 24)
            if not form:
                continue
            accession = _as_str(at(accessions, index), 32)
            document = _as_str(at(documents, index), 160)
            url = None
            # Construction contrôlée : aucun fragment distant n'est repris tel
            # quel dans l'URL, uniquement des caractères sûrs.
            if accession.replace("-", "").isdigit() and _is_safe_doc_name(document):
                url = (
                    "https://www.sec.gov/Archives/edgar/data/"
                    f"{cik_int}/{accession.replace('-', '')}/{document}"
                )
            filings.append(
                Filing(
                    form=form,
                    filed_at=_parse_date(at(dates, index)),
                    accession=accession,
                    primary_document=document,
                    description=_as_str(at(descriptions, index), 200),
                    url=url,
                    items=_parse_items(at(items, index)),
                )
            )
        return filings

    # -------------------------------------------------------------- XBRL

    def company_facts(self, cik: str) -> dict[str, Any]:
        cik = validate_cik(cik)
        payload = self.http.get_json(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        )
        if not isinstance(payload, dict):
            raise OsintError("format inattendu pour companyfacts")
        return payload

    @staticmethod
    def extract_series(payload: dict[str, Any]) -> dict[str, list[FactPoint]]:
        """Extrait les séries temporelles des concepts utiles.

        Les faits sont dédupliqués par (date de fin, formulaire) et triés par
        date croissante. Le premier concept disponible dans
        :data:`CONCEPTS` l'emporte : on ne mélange jamais deux définitions
        comptables dans une même série.
        """
        facts = payload.get("facts")
        if not isinstance(facts, dict):
            return {}
        namespaces = [ns for ns in ("us-gaap", "dei", "ifrs-full") if isinstance(facts.get(ns), dict)]

        series: dict[str, list[FactPoint]] = {}
        for key, concepts in CONCEPTS.items():
            for concept in concepts:
                node = None
                for namespace in namespaces:
                    candidate = facts[namespace].get(concept)
                    if isinstance(candidate, dict):
                        node = candidate
                        break
                if node is None:
                    continue
                points = _series_from_node(node, unitless=key in _UNITLESS_KEYS)
                if points:
                    series[key] = points
                    break
        return series

    @staticmethod
    def extract_facts(
        payload: dict[str, Any]
    ) -> tuple[dict[str, float], dict[str, str], dict[str, list[FactPoint]]]:
        """Dernière valeur connue de chaque concept, plus les séries complètes."""
        series = SecClient.extract_series(payload)
        values: dict[str, float] = {}
        dates: dict[str, str] = {}
        for key, points in series.items():
            best = latest_point(points)
            if best is not None:
                values[key] = best.value
                dates[key] = best.end
        return values, dates, series


def _series_from_node(node: dict[str, Any], unitless: bool = False) -> list[FactPoint]:
    units = node.get("units")
    if not isinstance(units, dict):
        return []

    accepted = ("USD", "USD/shares") if not unitless else ("shares", "pure")
    collected: dict[tuple[str, str], FactPoint] = {}
    for unit_name, entries in units.items():
        if unit_name not in accepted:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries[-600:]:
            if not isinstance(entry, dict):
                continue
            value = _as_float(entry.get("val"))
            end = _as_str(entry.get("end"), 12)
            if value is None or len(end) < 10:
                continue
            form = _as_str(entry.get("form"), 16).upper()
            fiscal_year = entry.get("fy")
            point = FactPoint(
                end=end,
                value=value,
                form=form,
                fiscal_year=int(fiscal_year) if isinstance(fiscal_year, int) else None,
                fiscal_period=_as_str(entry.get("fp"), 4) or None,
            )
            collected[(end, form)] = point
    return sorted(collected.values(), key=lambda p: (p.end, p.form))


def latest_point(points: list[FactPoint]) -> FactPoint | None:
    """Dernier point, en privilégiant l'annuel à date égale."""
    if not points:
        return None
    return max(points, key=lambda p: (p.end, 2 if p.is_annual else 1))


def annual_points(points: list[FactPoint]) -> list[FactPoint]:
    """Points annuels (10-K), un par exercice, du plus ancien au plus récent."""
    by_year: dict[str, FactPoint] = {}
    for point in points:
        if point.is_annual:
            by_year[point.end[:4]] = point
    return [by_year[year] for year in sorted(by_year)]


def _is_safe_doc_name(name: str) -> bool:
    """Autorise un nom de fichier plat, éventuellement préfixé par un dossier XSL.

    EDGAR référence les Form 3/4/5 via leur rendu (``xslF345X03/doc.xml``). On
    accepte ce préfixe précis, et rien d'autre : ni ``..``, ni chemin absolu,
    ni second niveau arbitraire.
    """
    if not name or len(name) > 160:
        return False
    if "\\" in name or ".." in name:
        return False
    parts = name.split("/")
    if len(parts) == 2:
        if not parts[0].startswith("xsl") or not parts[0].isalnum():
            return False
        parts = parts[1:]
    elif len(parts) != 1:
        return False
    leaf = parts[0]
    if not leaf:
        return False
    return all(ch.isalnum() or ch in "._-" for ch in leaf)


def fetch_profile(client: SecClient, ticker: str) -> SecProfile:
    """Assemble le profil SEC complet ; les échecs partiels sont non fatals."""
    cik, name = client.resolve_cik(ticker)
    profile = SecProfile(cik=cik, ticker=ticker, company_name=name or ticker)

    try:
        submissions = client.submissions(cik)
        profile.filings = SecClient.parse_filings(submissions, cik)
        profile.sic_description = _as_str(submissions.get("sicDescription"), 120) or None
    except OsintError as exc:
        profile.warnings.append(f"filings indisponibles : {exc}")

    try:
        facts_payload = client.company_facts(cik)
        profile.facts, profile.fact_dates, profile.series = SecClient.extract_facts(facts_payload)
    except OsintError as exc:
        profile.warnings.append(f"XBRL indisponible : {exc}")

    return profile


def days_since_last_filing(filings: list[Filing], today: date | None = None) -> int | None:
    today = today or datetime.now(timezone.utc).date()
    dated = [f.filed_at for f in filings if f.filed_at]
    if not dated:
        return None
    return (today - max(dated)).days
