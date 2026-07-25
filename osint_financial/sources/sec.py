"""Connecteur SEC EDGAR : résolution ticker→CIK, filings récents, faits XBRL.

Points de sécurité :

* Toutes les URL sont **construites** à partir d'un CIK validé (10 chiffres),
  jamais concaténées avec une chaîne utilisateur.
* Les réponses distantes sont traitées comme hostiles : typage vérifié champ
  par champ, listes plafonnées, chaînes tronquées. L'original faisait confiance
  à la structure JSON et réinjectait le contenu dans le HTML et dans les
  invites LLM.
* Le cache disque est écrit atomiquement dans un répertoire confiné.
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
_MAX_FILINGS = 40
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


@dataclass(frozen=True)
class Filing:
    form: str
    filed_at: date | None
    accession: str
    primary_document: str
    description: str
    url: str | None

    @property
    def signal_weight(self) -> int:
        return FILING_SIGNAL.get(self.form.upper(), 0)


@dataclass
class SecProfile:
    cik: str
    ticker: str
    company_name: str
    sic_description: str | None = None
    filings: list[Filing] = field(default_factory=list)
    facts: dict[str, float] = field(default_factory=dict)
    fact_dates: dict[str, str] = field(default_factory=dict)
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

        count = min(len(forms), _MAX_FILINGS)
        cik_int = str(int(cik))
        filings: list[Filing] = []
        for index in range(count):
            form = _as_str(forms[index], 24)
            if not form:
                continue
            accession = _as_str(accessions[index] if index < len(accessions) else "", 32)
            document = _as_str(documents[index] if index < len(documents) else "", 160)
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
                    filed_at=_parse_date(dates[index] if index < len(dates) else None),
                    accession=accession,
                    primary_document=document,
                    description=_as_str(
                        descriptions[index] if index < len(descriptions) else "", 200
                    ),
                    url=url,
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
    def extract_facts(payload: dict[str, Any]) -> tuple[dict[str, float], dict[str, str]]:
        """Extrait les agrégats utiles du bloc us-gaap, avec leur date.

        On garde la valeur annuelle la plus récente pour chaque concept, en
        privilégiant les formulaires 10-K puis 10-Q.
        """
        wanted = {
            "assets": ("Assets",),
            "liabilities": ("Liabilities",),
            "revenue": (
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
            ),
            "net_income": ("NetIncomeLoss",),
            "eps": ("EarningsPerShareDiluted", "EarningsPerShareBasic"),
            "cash": ("CashAndCashEquivalentsAtCarryingValue",),
            "long_term_debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
        }
        gaap = payload.get("facts", {})
        gaap = gaap.get("us-gaap", {}) if isinstance(gaap, dict) else {}
        if not isinstance(gaap, dict):
            return {}, {}

        values: dict[str, float] = {}
        dates: dict[str, str] = {}
        for key, concepts in wanted.items():
            for concept in concepts:
                node = gaap.get(concept)
                if not isinstance(node, dict):
                    continue
                best = _latest_unit_value(node)
                if best is not None:
                    values[key], dates[key] = best
                    break
        return values, dates


def _latest_unit_value(node: dict[str, Any]) -> tuple[float, str] | None:
    units = node.get("units")
    if not isinstance(units, dict):
        return None
    best_value: float | None = None
    best_end = ""
    best_rank = -1
    for unit_name, entries in units.items():
        if unit_name not in ("USD", "USD/shares"):
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries[-400:]:
            if not isinstance(entry, dict):
                continue
            value = _as_float(entry.get("val"))
            end = _as_str(entry.get("end"), 12)
            if value is None or not end:
                continue
            form = _as_str(entry.get("form"), 16).upper()
            rank = 2 if form == "10-K" else 1 if form == "10-Q" else 0
            if (end, rank) > (best_end, best_rank):
                best_value, best_end, best_rank = value, end, rank
    if best_value is None:
        return None
    return best_value, best_end


def _is_safe_doc_name(name: str) -> bool:
    """Autorise uniquement un nom de fichier plat pour l'URL d'archive."""
    if not name or len(name) > 160:
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    return all(ch.isalnum() or ch in "._-" for ch in name)


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
        profile.facts, profile.fact_dates = SecClient.extract_facts(facts_payload)
    except OsintError as exc:
        profile.warnings.append(f"XBRL indisponible : {exc}")

    return profile


def days_since_last_filing(filings: list[Filing], today: date | None = None) -> int | None:
    today = today or datetime.now(timezone.utc).date()
    dated = [f.filed_at for f in filings if f.filed_at]
    if not dated:
        return None
    return (today - max(dated)).days
