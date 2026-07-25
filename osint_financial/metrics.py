"""Agrégation des sources en un jeu de métriques traçable.

Principe conservé : **chaque métrique porte sa provenance et sa date**, et
l'absence de donnée est représentée explicitement (``None``) plutôt que
confondue avec une valeur neutre.

Ce module rend calculables les tests annoncés au §4 du guide, qui n'avaient
aucune implémentation :

* test de croissance → séries annuelles de chiffre d'affaires (XBRL) ;
* test de liquidité → ratio de liquidité générale et autonomie en mois ;
* test de dilution → variation du nombre d'actions + item 8-K 3.02 ;
* test de gouvernance → Form 4 réellement lus (achat/vente d'initiés) ;
* catalyseurs → items 8-K, et non plus simple présence d'un dépôt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .errors import OsintError
from .httpclient import HttpClient
from .logging_setup import get_logger
from .sources import forms, market, prices, sec
from .technical import TechnicalView, analyze as analyze_technical
from .valuation import DcfResult, PeerValuation, discounted_cash_flow, implied_growth, peer_median_pe
from .validation import validate_ticker

log = get_logger(__name__)

#: PE médians sectoriels indicatifs (moyennes historiques de marché). Repères
#: grossiers utilisés uniquement à défaut de comparables mesurés (``--peers``).
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

MAX_PEERS = 6


def sector_from_sic(description: str | None) -> str:
    if not description:
        return "default"
    text = description.lower()
    for sector, keywords in _SIC_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return sector
    return "default"


@dataclass(frozen=True)
class CollectOptions:
    """Ce que l'on accepte de payer en appels réseau."""

    history: bool = True
    insiders: bool = True
    macro: bool = True
    peers: tuple[str, ...] = ()
    history_range: str = "2y"


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

    # --- Fondamentaux ----------------------------------------------------
    eps: float | None = None
    pe_ratio: float | None = None
    pe_sector: float | None = None
    pe_source: str = "table sectorielle statique"
    revenue: float | None = None
    net_income: float | None = None
    assets: float | None = None
    liabilities: float | None = None
    assets_current: float | None = None
    liabilities_current: float | None = None
    equity: float | None = None
    cash: float | None = None
    long_term_debt: float | None = None
    operating_cash_flow: float | None = None
    capex: float | None = None
    free_cash_flow: float | None = None
    shares_outstanding: float | None = None
    market_cap: float | None = None
    net_debt: float | None = None

    debt_to_assets: float | None = None
    profit_margin: float | None = None
    current_ratio: float | None = None

    # --- Croissance, liquidité, dilution ---------------------------------
    revenue_growth_yoy_pct: float | None = None
    revenue_cagr_pct: float | None = None
    revenue_growth_note: str | None = None
    cash_runway_months: float | None = None
    share_count_growth_pct: float | None = None

    # --- Valorisation ----------------------------------------------------
    target_price_pe: float | None = None
    upside_pe_pct: float | None = None
    dcf: DcfResult = field(default_factory=DcfResult)
    peer_valuation: PeerValuation = field(default_factory=PeerValuation)

    # --- Dépôts SEC -------------------------------------------------------
    filings: list[sec.Filing] = field(default_factory=list)
    filings_available: bool = False
    days_since_last_filing: int | None = None
    alert_filings: list[sec.Filing] = field(default_factory=list)
    dilution_filings: list[sec.Filing] = field(default_factory=list)
    strong_signals: list[str] = field(default_factory=list)
    insider: forms.InsiderActivity | None = None

    # --- Marché -----------------------------------------------------------
    technical: TechnicalView | None = None

    fact_dates: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["filings"] = [_filing_dict(f) for f in self.filings]
        data["alert_filings"] = [_filing_dict(f) for f in self.alert_filings]
        data["dilution_filings"] = [_filing_dict(f) for f in self.dilution_filings]
        data["dcf"] = self.dcf.to_dict()
        data["peer_valuation"] = self.peer_valuation.to_dict()
        data["insider"] = self.insider.to_dict() if self.insider else None
        data["technical"] = self.technical.to_dict() if self.technical else None
        return data


def _filing_dict(filing: sec.Filing) -> dict[str, Any]:
    return {
        "form": filing.form,
        "filed_at": filing.filed_at.isoformat() if filing.filed_at else None,
        "accession": filing.accession,
        "description": filing.description,
        "items": list(filing.items),
        "url": filing.url,
    }


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    """Division protégée : ni ZeroDivisionError ni ratio absurde."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0 or denominator != denominator:
        return None
    result = numerator / denominator
    return result if result == result and abs(result) < 1e9 else None


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


# ---------------------------------------------------------------- collecte


def collect(
    http: HttpClient,
    ticker: str,
    sec_client: sec.SecClient,
    options: CollectOptions | None = None,
) -> Metrics:
    """Interroge les sources et construit les métriques dérivées."""
    ticker = validate_ticker(ticker)
    options = options or CollectOptions()
    metrics = Metrics(ticker=ticker, company_name=ticker)

    series: dict[str, list[sec.FactPoint]] = {}

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
        series = profile.series
        metrics.fact_dates = profile.fact_dates
        metrics.eps = facts.get("eps")
        metrics.revenue = facts.get("revenue")
        metrics.net_income = facts.get("net_income")
        metrics.assets = facts.get("assets")
        metrics.liabilities = facts.get("liabilities")
        metrics.assets_current = facts.get("assets_current")
        metrics.liabilities_current = facts.get("liabilities_current")
        metrics.equity = facts.get("equity")
        metrics.cash = facts.get("cash")
        metrics.long_term_debt = facts.get("long_term_debt")
        metrics.operating_cash_flow = facts.get("operating_cash_flow")
        metrics.capex = facts.get("capex")
        metrics.shares_outstanding = facts.get("shares")

        metrics.alert_filings = [f for f in profile.filings if f.is_alert][:10]
        metrics.dilution_filings = [f for f in profile.filings if f.is_dilution][:10]
        metrics.strong_signals = _strong_signals(profile.filings)
    except OsintError as exc:
        metrics.warnings.append(f"SEC indisponible : {exc}")

    # --- Form 4 (gouvernance) --------------------------------------------
    if options.insiders and metrics.cik and metrics.filings:
        try:
            metrics.insider = forms.collect_insider_activity(http, metrics.cik, metrics.filings)
            metrics.warnings.extend(metrics.insider.warnings)
        except OsintError as exc:
            metrics.warnings.append(f"Form 4 indisponibles : {exc}")

    # --- Marché : prix et historique --------------------------------------
    price_series: prices.PriceSeries | None = None
    if options.history:
        try:
            price_series = prices.fetch_history(http, ticker, options.history_range)
            metrics.technical = analyze_technical(price_series)
            metrics.price = price_series.last
            metrics.currency = price_series.currency
            metrics.price_source = f"{price_series.source} (historique)"
            metrics.price_as_of = price_series.last_date.isoformat()
        except OsintError as exc:
            metrics.warnings.append(f"historique indisponible : {exc}")

    if metrics.price is None:
        try:
            quote = market.fetch_quote(http, ticker)
            metrics.price = quote.price
            metrics.currency = quote.currency
            metrics.price_source = quote.source
            metrics.price_as_of = quote.as_of.isoformat() if quote.as_of else None
        except OsintError as exc:
            metrics.warnings.append(f"cotation indisponible : {exc}")

    # --- Dérivés fondamentaux ---------------------------------------------
    _derive_fundamentals(metrics)
    _derive_growth(metrics, series)
    _derive_dilution(metrics, series)

    # --- Valorisation ------------------------------------------------------
    metrics.pe_sector = SECTOR_PE.get(metrics.sector, SECTOR_PE["default"])
    if options.peers:
        _apply_peers(http, metrics, sec_client, options.peers)
    _derive_pe_target(metrics)
    _derive_dcf(metrics, series)

    return metrics


def _derive_fundamentals(metrics: Metrics) -> None:
    metrics.debt_to_assets = _round(_safe_ratio(metrics.liabilities, metrics.assets), 4)
    metrics.profit_margin = _round(_safe_ratio(metrics.net_income, metrics.revenue), 4)
    metrics.current_ratio = _round(
        _safe_ratio(metrics.assets_current, metrics.liabilities_current), 3
    )

    if metrics.operating_cash_flow is not None:
        capex = metrics.capex or 0.0
        # Le capex XBRL est déclaré en valeur positive (un décaissement).
        metrics.free_cash_flow = round(metrics.operating_cash_flow - abs(capex), 2)

    if metrics.long_term_debt is not None or metrics.cash is not None:
        metrics.net_debt = round((metrics.long_term_debt or 0.0) - (metrics.cash or 0.0), 2)

    if metrics.price and metrics.shares_outstanding:
        metrics.market_cap = round(metrics.price * metrics.shares_outstanding, 2)

    # Autonomie de trésorerie : seulement pertinente si l'entreprise brûle du cash.
    if metrics.free_cash_flow is not None and metrics.free_cash_flow < 0 and metrics.cash:
        monthly_burn = abs(metrics.free_cash_flow) / 12.0
        if monthly_burn > 0:
            metrics.cash_runway_months = round(metrics.cash / monthly_burn, 1)


def _derive_growth(metrics: Metrics, series: dict[str, list[sec.FactPoint]]) -> None:
    annual = sec.annual_points(series.get("revenue", []))
    values = [point.value for point in annual if point.value > 0]
    if len(values) >= 2:
        metrics.revenue_growth_yoy_pct = _round((values[-1] / values[-2] - 1.0) * 100.0, 2)
    if values:
        rate, note = implied_growth(values)
        metrics.revenue_cagr_pct = _round(rate * 100.0, 2)
        metrics.revenue_growth_note = note
    else:
        metrics.revenue_growth_note = "aucune série annuelle de chiffre d'affaires exploitable"


def _derive_dilution(metrics: Metrics, series: dict[str, list[sec.FactPoint]]) -> None:
    annual = sec.annual_points(series.get("shares", []))
    values = [point.value for point in annual if point.value > 0]
    if len(values) >= 2:
        metrics.share_count_growth_pct = _round((values[-1] / values[-2] - 1.0) * 100.0, 2)


def _derive_pe_target(metrics: Metrics) -> None:
    if metrics.eps is None:
        return
    if metrics.eps <= 0:
        metrics.warnings.append("BPA négatif ou nul : PE et prix cible non calculables")
        return
    metrics.pe_ratio = _round(_safe_ratio(metrics.price, metrics.eps), 2)
    if metrics.pe_sector is None:
        return
    target = metrics.eps * metrics.pe_sector
    metrics.target_price_pe = round(target, 2)
    upside = _safe_ratio(target - (metrics.price or 0.0), metrics.price)
    metrics.upside_pe_pct = _round(upside * 100.0, 2) if upside is not None else None


def _derive_dcf(metrics: Metrics, series: dict[str, list[sec.FactPoint]]) -> None:
    annual_revenue = [p.value for p in sec.annual_points(series.get("revenue", [])) if p.value > 0]
    growth, note = implied_growth(annual_revenue)

    # Le DCF utilise le flux annuel le plus récent, pas une valeur trimestrielle.
    annual_ocf = sec.annual_points(series.get("operating_cash_flow", []))
    annual_capex = sec.annual_points(series.get("capex", []))
    free_cash_flow = metrics.free_cash_flow
    if annual_ocf:
        capex_value = abs(annual_capex[-1].value) if annual_capex else 0.0
        free_cash_flow = round(annual_ocf[-1].value - capex_value, 2)

    metrics.dcf = discounted_cash_flow(
        free_cash_flow=free_cash_flow,
        shares=metrics.shares_outstanding,
        net_debt=metrics.net_debt or 0.0,
        growth=growth,
        current_price=metrics.price,
    )
    metrics.dcf.warnings.insert(0, f"hypothèse de croissance — {note}")


def _apply_peers(
    http: HttpClient, metrics: Metrics, sec_client: sec.SecClient, peers: tuple[str, ...]
) -> None:
    """Calcule un PE médian sur des comparables réellement mesurés."""
    measured: dict[str, float | None] = {}
    for raw in peers[:MAX_PEERS]:
        try:
            peer = validate_ticker(raw)
        except OsintError:
            continue
        if peer == metrics.ticker:
            continue
        measured[peer] = _peer_pe(http, sec_client, peer)

    valuation = peer_median_pe(measured)
    metrics.peer_valuation = valuation
    if valuation.median_pe is not None:
        metrics.pe_sector = valuation.median_pe
        metrics.pe_source = valuation.source
    else:
        metrics.warnings.append(f"comparables inexploitables : {valuation.source}")


def _peer_pe(http: HttpClient, sec_client: sec.SecClient, peer: str) -> float | None:
    try:
        cik, _ = sec_client.resolve_cik(peer)
        facts, _, _ = sec.SecClient.extract_facts(sec_client.company_facts(cik))
        eps = facts.get("eps")
        if eps is None or eps <= 0:
            return None
        quote = market.fetch_quote(http, peer)
        return quote.price / eps
    except OsintError as exc:
        log.debug("comparable %s ignoré : %s", peer, exc)
        return None


def _strong_signals(filings: list[sec.Filing]) -> list[str]:
    """Signaux notables tirés des métadonnées et des items 8-K."""
    signals: list[str] = []
    for filing in filings[:25]:
        form = filing.form.upper()
        label = filing.filed_at.isoformat() if filing.filed_at else "date inconnue"
        if form == "8-K" and filing.items:
            described = ", ".join(filing.item_labels()) or ", ".join(filing.items)
            prefix = "ALERTE" if filing.is_alert else "8-K"
            signals.append(f"{prefix} {label} : {described}")
        elif form.startswith("SC 13D"):
            signals.append(f"SC 13D le {label} : participation active >5 %")
        elif form.startswith("SC 13G"):
            signals.append(f"SC 13G le {label} : participation passive >5 %")
    return signals[:10]
