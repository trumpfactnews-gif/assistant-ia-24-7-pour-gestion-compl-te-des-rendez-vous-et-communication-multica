"""Agrégation des sources en un jeu de métriques traçable.

Différence majeure avec l'original : **chaque métrique porte sa provenance et
sa date**, et l'absence de donnée est représentée explicitement (``None``)
plutôt que confondue avec une valeur neutre. Dans l'ancien code,
``len(data.get("filings", []))`` valait 0 aussi bien quand l'entreprise n'avait
rien déposé que quand l'appel SEC avait échoué — deux situations qui n'ont pas
du tout le même sens et qui aboutissaient pourtant à la même pénalité de score.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from .errors import OsintError
from .httpclient import HttpClient
from .logging_setup import get_logger
from .sources import market, sec
from .validation import validate_ticker

log = get_logger(__name__)

#: PE médians sectoriels indicatifs (source : moyennes historiques de marché).
#: Ce sont des repères grossiers, volontairement conservateurs ; ils servent à
#: situer un ordre de grandeur, pas à produire un prix cible opposable.
SECTOR_PE = {
    "technology": 28.0,
    "healthcare": 18.0,
    "finance": 12.0,
    "energy": 12.0,
    "industrials": 20.0,
    "consumer": 19.0,
    "utilities": 17.0,
    "default": 18.0,
}

_SIC_KEYWORDS = (
    ("technology", ("computer", "software", "semiconductor", "data processing", "electronic")),
    ("healthcare", ("pharmaceutical", "biological", "medical", "health", "surgical")),
    ("finance", ("bank", "insurance", "credit", "investment", "finance", "security broker")),
    ("energy", ("petroleum", "crude", "oil", "gas", "coal", "drilling")),
    ("utilities", ("electric services", "water supply", "utilit")),
    ("consumer", ("retail", "food", "apparel", "beverage", "restaurant", "household")),
    ("industrials", ("machinery", "aircraft", "construction", "steel", "transport", "industrial")),
)


def sector_from_sic(description: str | None) -> str:
    if not description:
        return "default"
    text = description.lower()
    for sector, keywords in _SIC_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return sector
    return "default"


@dataclass
class Metrics:
    """Instantané financier d'un émetteur, avec traçabilité."""

    ticker: str
    company_name: str
    cik: str | None = None
    sector: str = "default"
    sic_description: str | None = None

    price: float | None = None
    currency: str = "USD"
    price_source: str | None = None
    price_as_of: str | None = None

    eps: float | None = None
    pe_ratio: float | None = None
    pe_sector: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    assets: float | None = None
    liabilities: float | None = None
    cash: float | None = None
    long_term_debt: float | None = None

    debt_to_assets: float | None = None
    profit_margin: float | None = None

    target_price_pe: float | None = None
    upside_pe_pct: float | None = None

    filings: list[sec.Filing] = field(default_factory=list)
    filings_available: bool = False
    days_since_last_filing: int | None = None
    strong_signals: list[str] = field(default_factory=list)

    fact_dates: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["filings"] = [
            {
                "form": f.form,
                "filed_at": f.filed_at.isoformat() if f.filed_at else None,
                "accession": f.accession,
                "description": f.description,
                "url": f.url,
            }
            for f in self.filings
        ]
        return data


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    """Division protégée : ni ZeroDivisionError ni ratio absurde.

    L'original calculait ``(target_pe - price) / price`` sans garde ; un prix
    nul ou négatif renvoyé par l'API faisait planter le processus après les
    appels réseau, perdant tout le travail déjà fait.
    """
    if numerator is None or denominator is None:
        return None
    if denominator == 0 or denominator != denominator:
        return None
    result = numerator / denominator
    return result if result == result and abs(result) < 1e9 else None


def collect(http: HttpClient, ticker: str, sec_client: sec.SecClient) -> Metrics:
    """Interroge les sources et construit les métriques dérivées."""
    ticker = validate_ticker(ticker)
    metrics = Metrics(ticker=ticker, company_name=ticker)

    # --- SEC -------------------------------------------------------------
    try:
        profile = sec.fetch_profile(sec_client, ticker)
        metrics.cik = profile.cik
        metrics.company_name = profile.company_name or ticker
        metrics.sic_description = profile.sic_description
        metrics.sector = sector_from_sic(profile.sic_description)
        metrics.filings = profile.filings
        metrics.filings_available = not any("filings indisponibles" in w for w in profile.warnings)
        metrics.days_since_last_filing = sec.days_since_last_filing(profile.filings)
        metrics.warnings.extend(profile.warnings)

        facts = profile.facts
        metrics.fact_dates = profile.fact_dates
        metrics.eps = facts.get("eps")
        metrics.revenue = facts.get("revenue")
        metrics.net_income = facts.get("net_income")
        metrics.assets = facts.get("assets")
        metrics.liabilities = facts.get("liabilities")
        metrics.cash = facts.get("cash")
        metrics.long_term_debt = facts.get("long_term_debt")
        metrics.strong_signals = _strong_signals(profile.filings)
    except OsintError as exc:
        metrics.warnings.append(f"SEC indisponible : {exc}")

    # --- Marché ----------------------------------------------------------
    try:
        quote = market.fetch_quote(http, ticker)
        metrics.price = quote.price
        metrics.currency = quote.currency
        metrics.price_source = quote.source
        metrics.price_as_of = quote.as_of.isoformat() if quote.as_of else None
    except OsintError as exc:
        metrics.warnings.append(f"cotation indisponible : {exc}")

    # --- Dérivés ---------------------------------------------------------
    metrics.pe_sector = SECTOR_PE.get(metrics.sector, SECTOR_PE["default"])

    if metrics.eps is not None and metrics.eps > 0:
        metrics.pe_ratio = _safe_ratio(metrics.price, metrics.eps)
        target = metrics.eps * metrics.pe_sector
        metrics.target_price_pe = round(target, 2)
        upside = _safe_ratio(target - (metrics.price or 0.0), metrics.price)
        metrics.upside_pe_pct = round(upside * 100.0, 2) if upside is not None else None
    elif metrics.eps is not None and metrics.eps <= 0:
        metrics.warnings.append("BPA négatif ou nul : PE et prix cible non calculables")

    metrics.debt_to_assets = _round(_safe_ratio(metrics.liabilities, metrics.assets), 4)
    metrics.profit_margin = _round(_safe_ratio(metrics.net_income, metrics.revenue), 4)

    return metrics


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _strong_signals(filings: list[sec.Filing]) -> list[str]:
    """Signaux notables, sans prétendre lire le contenu des documents.

    L'original annonçait détecter « achat d'initié » ou « revenue > attentes ».
    Rien dans les métadonnées EDGAR ne permet cela : il faut parser le document
    lui-même. On s'en tient donc à ce qui est réellement observable, et on le
    dit.
    """
    signals: list[str] = []
    for filing in filings[:20]:
        form = filing.form.upper()
        label = filing.filed_at.isoformat() if filing.filed_at else "date inconnue"
        if form == "8-K":
            signals.append(f"8-K déposé le {label} : événement à lire manuellement")
        elif form.startswith("SC 13D"):
            signals.append(f"SC 13D le {label} : participation active >5 %")
        elif form == "4":
            signals.append(f"Form 4 le {label} : transaction d'initié déclarée")
    return signals[:8]
