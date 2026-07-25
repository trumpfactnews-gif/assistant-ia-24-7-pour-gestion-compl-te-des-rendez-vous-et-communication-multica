"""Lecture des Form 4 (transactions d'initiés) — XML EDGAR.

Le guide promettait : « SI filing = Form 4 ET transaction = ACHAT initié →
SIGNAL BULLISH ». Les métadonnées ``submissions.json`` ne donnent que le type de
formulaire et sa date : impossible d'en déduire le sens d'une transaction. Il
faut ouvrir le document. C'est ce que fait ce module.

Sécurité du parsing XML — le contenu vient d'un tiers (la société analysée) :

* toute déclaration ``<!DOCTYPE`` ou ``<!ENTITY`` fait rejeter le document.
  Cela neutralise XXE (lecture de fichiers locaux, SSRF via entité externe) et
  l'expansion récursive d'entités (« billion laughs »), auxquels
  ``xml.etree.ElementTree`` reste sensible ;
* la taille est déjà plafonnée par le client HTTP ;
* le nombre de transactions lues est borné ;
* aucune valeur n'est évaluée : les nombres passent par une conversion stricte.

Codes de transaction retenus (table SEC) : ``P`` achat sur le marché,
``S`` vente. Les autres (``A`` attribution, ``M`` exercice d'options,
``F`` retenue fiscale, ``G`` donation…) sont comptés à part : ce sont des
mouvements de rémunération, pas des paris sur le titre. C'est exactement la
distinction qui manquait à la version d'origine.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

from ..errors import DataUnavailable, OsintError, SecurityError
from ..httpclient import HttpClient
from ..logging_setup import get_logger

log = get_logger(__name__)

BUY_CODE = "P"
SELL_CODE = "S"
COMPENSATION_CODES = frozenset({"A", "M", "F", "G", "C", "X", "D", "I"})

MAX_TRANSACTIONS = 60
MAX_FORMS_FETCHED = 12


@dataclass(frozen=True)
class InsiderTransaction:
    owner: str
    is_officer: bool
    is_director: bool
    officer_title: str
    code: str
    transaction_date: date | None
    shares: float | None
    price_per_share: float | None
    acquired: bool | None

    @property
    def value(self) -> float | None:
        if self.shares is None or self.price_per_share is None:
            return None
        return self.shares * self.price_per_share

    @property
    def is_open_market_buy(self) -> bool:
        return self.code == BUY_CODE and self.acquired is True

    @property
    def is_open_market_sell(self) -> bool:
        return self.code == SELL_CODE and self.acquired is False


@dataclass
class InsiderActivity:
    """Agrégat des Form 4 lus, sur la fenêtre disponible."""

    transactions: list[InsiderTransaction] = field(default_factory=list)
    forms_read: int = 0
    forms_failed: int = 0
    window_start: date | None = None
    window_end: date | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.forms_read > 0

    @property
    def buys(self) -> list[InsiderTransaction]:
        return [t for t in self.transactions if t.is_open_market_buy]

    @property
    def sells(self) -> list[InsiderTransaction]:
        return [t for t in self.transactions if t.is_open_market_sell]

    @property
    def buy_value(self) -> float:
        return sum(t.value or 0.0 for t in self.buys)

    @property
    def sell_value(self) -> float:
        return sum(t.value or 0.0 for t in self.sells)

    @property
    def net_value(self) -> float:
        return self.buy_value - self.sell_value

    @property
    def distinct_buyers(self) -> int:
        return len({t.owner for t in self.buys if t.owner})

    @property
    def distinct_sellers(self) -> int:
        return len({t.owner for t in self.sells if t.owner})

    @property
    def compensation_only(self) -> bool:
        """Vrai si aucun achat/vente de marché : que de la rémunération."""
        return self.available and not self.buys and not self.sells

    def verdict(self) -> str:
        """Signal d'initiés, en vocabulaire fermé."""
        if not self.available:
            return "INCONNU"
        if self.compensation_only:
            return "NEUTRE_REMUNERATION"
        # Achat groupé : plusieurs initiés distincts achètent — le signal le
        # plus documenté de la littérature sur les initiés.
        if self.distinct_buyers >= 2 and self.net_value > 0:
            return "ACHAT_GROUPE"
        if self.buys and self.net_value > 0:
            return "ACHAT_ISOLE"
        if self.distinct_sellers >= 3 and self.net_value < 0:
            return "VENTE_GROUPEE"
        if self.sells and self.net_value < 0:
            return "VENTE"
        return "NEUTRE"

    def to_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "verdict": self.verdict(),
            "forms_read": self.forms_read,
            "forms_failed": self.forms_failed,
            "buy_count": len(self.buys),
            "sell_count": len(self.sells),
            "buy_value": round(self.buy_value, 2),
            "sell_value": round(self.sell_value, 2),
            "net_value": round(self.net_value, 2),
            "distinct_buyers": self.distinct_buyers,
            "distinct_sellers": self.distinct_sellers,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "warnings": self.warnings,
        }


def raw_xml_url(cik: str, accession: str, primary_document: str) -> str | None:
    """URL du XML brut d'un Form 4.

    EDGAR référence souvent le rendu XSL (``xslF345X03/wf-form4_1.xml``) ; le
    document source est le même nom sans ce préfixe. On ne conserve que des
    noms de fichiers plats, validés caractère par caractère.
    """
    digits = accession.replace("-", "")
    if not digits.isdigit() or not cik.isdigit():
        return None

    parts = primary_document.split("/")
    if len(parts) == 2:
        # Un seul préfixe est admis, celui du rendu XSL des formulaires 3/4/5.
        if not parts[0].startswith("xsl") or not parts[0].isalnum():
            return None
        parts = parts[1:]
    elif len(parts) != 1:
        return None

    name = parts[0]
    if not name or len(name) > 128 or not name.lower().endswith(".xml"):
        return None
    if not all(ch.isalnum() or ch in "._-" for ch in name):
        return None
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{digits}/{name}"


def _guard_xml(raw: bytes) -> None:
    """Refuse les documents porteurs d'une DTD ou d'entités."""
    head = raw[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in raw[:65536].lower():
        raise SecurityError("XML avec DTD ou entités : document refusé")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_value(node: ET.Element | None, *path: str) -> str | None:
    """Descend ``path`` en ignorant les préfixes de namespace."""
    current = node
    for name in path:
        if current is None:
            return None
        current = next((c for c in current if _local(c.tag) == name), None)
    if current is None:
        return None
    # Les champs Form 4 encapsulent la donnée dans <value>.
    inner = next((c for c in current if _local(c.tag) == "value"), None)
    text = (inner if inner is not None else current).text
    return text.strip() if isinstance(text, str) else None


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw.replace(",", "").strip())
    except ValueError:
        return None
    if value != value or abs(value) > 1e15:
        return None
    return value


def _to_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _flag(node: ET.Element | None, name: str) -> bool:
    value = _find_value(node, name)
    return value in {"1", "true", "TRUE", "Y", "y"}


def parse_form4(raw: bytes) -> list[InsiderTransaction]:
    """Extrait les transactions non dérivées d'un Form 4."""
    _guard_xml(raw)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise DataUnavailable(f"Form 4 illisible : {exc.__class__.__name__}") from None

    owner_node = next((c for c in root if _local(c.tag) == "reportingOwner"), None)
    owner = ""
    is_officer = is_director = False
    officer_title = ""
    if owner_node is not None:
        owner = _find_value(owner_node, "reportingOwnerId", "rptOwnerName") or ""
        relationship = next(
            (c for c in owner_node if _local(c.tag) == "reportingOwnerRelationship"), None
        )
        is_officer = _flag(relationship, "isOfficer")
        is_director = _flag(relationship, "isDirector")
        officer_title = _find_value(relationship, "officerTitle") or ""

    transactions: list[InsiderTransaction] = []
    for table in root:
        if _local(table.tag) != "nonDerivativeTable":
            continue
        for entry in table:
            if _local(entry.tag) != "nonDerivativeTransaction":
                continue
            if len(transactions) >= MAX_TRANSACTIONS:
                break
            code = (_find_value(entry, "transactionCoding", "transactionCode") or "").upper()[:2]
            acquired_raw = _find_value(
                entry, "transactionAmounts", "transactionAcquiredDisposedCode"
            )
            acquired = None
            if acquired_raw in {"A", "D"}:
                acquired = acquired_raw == "A"
            transactions.append(
                InsiderTransaction(
                    owner=owner[:120],
                    is_officer=is_officer,
                    is_director=is_director,
                    officer_title=officer_title[:80],
                    code=code,
                    transaction_date=_to_date(_find_value(entry, "transactionDate")),
                    shares=_to_float(
                        _find_value(entry, "transactionAmounts", "transactionShares")
                    ),
                    price_per_share=_to_float(
                        _find_value(entry, "transactionAmounts", "transactionPricePerShare")
                    ),
                    acquired=acquired,
                )
            )
    return transactions


def collect_insider_activity(
    http: HttpClient,
    cik: str,
    filings: Iterable,
    max_forms: int = MAX_FORMS_FETCHED,
) -> InsiderActivity:
    """Télécharge et agrège les Form 4 les plus récents.

    Chaque échec est isolé : un document corrompu ne fait pas tomber l'analyse.
    """
    activity = InsiderActivity()
    candidates = [f for f in filings if f.form.upper() == "4"][:max_forms]
    if not candidates:
        return activity

    for filing in candidates:
        url = raw_xml_url(cik, filing.accession, filing.primary_document)
        if url is None:
            activity.forms_failed += 1
            continue
        try:
            transactions = parse_form4(http.get_bytes(url, accept="application/xml"))
        except (OsintError, ValueError) as exc:
            activity.forms_failed += 1
            log.debug("Form 4 ignoré (%s) : %s", filing.accession, exc)
            continue
        activity.forms_read += 1
        activity.transactions.extend(transactions)

    dated = [t.transaction_date for t in activity.transactions if t.transaction_date]
    if dated:
        activity.window_start, activity.window_end = min(dated), max(dated)
    if activity.forms_failed:
        activity.warnings.append(f"{activity.forms_failed} Form 4 non exploitable(s)")
    return activity
