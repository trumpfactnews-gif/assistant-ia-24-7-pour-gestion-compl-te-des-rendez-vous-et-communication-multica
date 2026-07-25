"""Moteur de scoring explicite, déterministe et auditable.

Chaque règle est nommée, pondérée, et retourne la preuve chiffrée qui la
déclenche. Une règle dont les données manquent est comptée comme *non évaluée*
— jamais comme neutre — et fait baisser l'indice de confiance. Sous 50 % de
couverture, la recommandation est ``INSUFFICIENT_DATA`` : l'outil refuse de
conclure plutôt que d'afficher un « HOLD » sans contenu.

Le **score de résilience** annoncé au §4 du guide (« 50 % fondamentaux + 25 %
position marché + 25 % macro ») est calculé ici, chaque composante étant
adossée à une source réelle : fondamentaux du XBRL, position de marché de
l'historique de cours, macro du régime de marché mesuré.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from .metrics import Metrics

# --- Seuils (regroupés pour être relus et discutés) -----------------------
DEBT_HIGH = 0.60
DEBT_ELEVATED = 0.40
PE_BUBBLE_MULTIPLE = 1.5
PE_RICH_MULTIPLE = 1.2
PE_DISCOUNT_MULTIPLE = 0.7
MARGIN_STRONG = 0.15
MARGIN_WEAK = 0.02
UPSIDE_STRONG = 20.0
UPSIDE_MODERATE = 10.0
DOWNSIDE_ALERT = -10.0
FILING_SILENCE_DAYS = 180
CURRENT_RATIO_WEAK = 1.0
CURRENT_RATIO_STRONG = 2.0
RUNWAY_CRITICAL_MONTHS = 12.0
DILUTION_HEAVY_PCT = 8.0
DILUTION_MILD_PCT = 3.0
GROWTH_STRONG_PCT = 12.0
GROWTH_NEGATIVE_PCT = -3.0
DCF_UPSIDE_STRONG = 30.0
DCF_UPSIDE_MODERATE = 12.0
DRAWDOWN_SEVERE_PCT = 45.0

MIN_CONFIDENCE = 0.50

FUNDAMENTAL = "fundamental"
MARKET = "market"


@dataclass(frozen=True)
class RuleOutcome:
    name: str
    axis: str  # "risk" ou "opportunity"
    points: float
    evidence: str
    evaluated: bool
    weight: float
    group: str = FUNDAMENTAL


@dataclass
class ScoreResult:
    risk_score: float
    opportunity_score: float
    net_score: float
    recommendation: str
    confidence: float
    outcomes: list[RuleOutcome] = field(default_factory=list)
    resilience_score: float | None = None
    resilience_parts: dict[str, float | None] = field(default_factory=dict)

    @property
    def risk_factors(self) -> list[str]:
        return [
            f"{o.name} — {o.evidence}"
            for o in self.outcomes
            if o.axis == "risk" and o.evaluated and o.points > 0
        ]

    @property
    def opportunity_factors(self) -> list[str]:
        return [
            f"{o.name} — {o.evidence}"
            for o in self.outcomes
            if o.axis == "opportunity" and o.evaluated and o.points > 0
        ]

    @property
    def missing_inputs(self) -> list[str]:
        return [f"{o.name} — {o.evidence}" for o in self.outcomes if not o.evaluated]

    def to_dict(self) -> dict[str, object]:
        return {
            "risk_score": self.risk_score,
            "opportunity_score": self.opportunity_score,
            "net_score": self.net_score,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "resilience_score": self.resilience_score,
            "resilience_parts": self.resilience_parts,
            "risk_factors": self.risk_factors,
            "opportunity_factors": self.opportunity_factors,
            "missing_inputs": self.missing_inputs,
        }


Rule = Callable[[Metrics], RuleOutcome]


def _skip(name: str, axis: str, weight: float, reason: str, group: str = FUNDAMENTAL) -> RuleOutcome:
    return RuleOutcome(name, axis, 0.0, reason, evaluated=False, weight=weight, group=group)


def _hit(
    name: str, axis: str, weight: float, points: float, evidence: str, group: str = FUNDAMENTAL
) -> RuleOutcome:
    return RuleOutcome(name, axis, points, evidence, evaluated=True, weight=weight, group=group)


# --- Règles de risque : bilan --------------------------------------------

def rule_leverage(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Levier financier", "risk", 1.5
    if m.debt_to_assets is None:
        return _skip(name, axis, weight, "passif ou actif total absent du XBRL")
    ratio = m.debt_to_assets
    label = f"passif/actif = {ratio:.0%}"
    if ratio > DEBT_HIGH:
        return _hit(name, axis, weight, 18.0, f"{label} (> {DEBT_HIGH:.0%})")
    if ratio > DEBT_ELEVATED:
        return _hit(name, axis, weight, 8.0, f"{label} (> {DEBT_ELEVATED:.0%})")
    return _hit(name, axis, weight, 0.0, f"{label} — soutenable")


def rule_valuation(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Valorisation vs comparables", "risk", 1.5
    if m.pe_ratio is None or m.pe_sector is None:
        return _skip(name, axis, weight, "PE indisponible (BPA ou prix manquant)")
    ratio = m.pe_ratio / m.pe_sector
    label = f"PE {m.pe_ratio:.1f} vs référence {m.pe_sector:.1f} ({m.pe_source})"
    if ratio > PE_BUBBLE_MULTIPLE:
        return _hit(name, axis, weight, 15.0, f"{label} → prime de {ratio - 1:.0%}")
    if ratio > PE_RICH_MULTIPLE:
        return _hit(name, axis, weight, 6.0, f"{label} → prime de {ratio - 1:.0%}")
    return _hit(name, axis, weight, 0.0, f"{label} — dans la norme")


def rule_profitability(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Rentabilité", "risk", 1.5
    if m.profit_margin is None:
        return _skip(name, axis, weight, "résultat net ou chiffre d'affaires absent")
    margin = m.profit_margin
    if margin < 0:
        return _hit(name, axis, weight, 20.0, f"marge nette {margin:.1%} — pertes")
    if margin < MARGIN_WEAK:
        return _hit(name, axis, weight, 8.0, f"marge nette {margin:.1%} — très faible")
    return _hit(name, axis, weight, 0.0, f"marge nette {margin:.1%}")


def rule_liquidity(m: Metrics) -> RuleOutcome:
    """Test de liquidité du §4 : l'entreprise tient-elle ses échéances ?"""
    name, axis, weight = "Liquidité générale", "risk", 1.2
    if m.current_ratio is None:
        return _skip(name, axis, weight, "actif ou passif courant absent du XBRL")
    ratio = m.current_ratio
    if ratio < CURRENT_RATIO_WEAK:
        return _hit(name, axis, weight, 14.0, f"ratio de liquidité {ratio:.2f} (< 1)")
    if ratio < 1.3:
        return _hit(name, axis, weight, 5.0, f"ratio de liquidité {ratio:.2f} — tendu")
    return _hit(name, axis, weight, 0.0, f"ratio de liquidité {ratio:.2f}")


def rule_cash_runway(m: Metrics) -> RuleOutcome:
    """Test « assez de cash pour 12 mois ? » du §4."""
    name, axis, weight = "Autonomie de trésorerie", "risk", 1.0
    if m.free_cash_flow is None:
        return _skip(name, axis, weight, "flux de trésorerie disponible indisponible")
    if m.free_cash_flow >= 0:
        return _hit(
            name, axis, weight, 0.0,
            f"flux de trésorerie disponible positif ({m.free_cash_flow:,.0f})".replace(",", " "),
        )
    if m.cash is None:
        return _skip(name, axis, weight, "trésorerie absente : autonomie non calculable")
    months = m.cash_runway_months
    if months is None:
        return _skip(name, axis, weight, "autonomie non calculable")
    if months < RUNWAY_CRITICAL_MONTHS:
        return _hit(name, axis, weight, 18.0, f"consommation de cash : {months:.0f} mois d'autonomie")
    if months < 24:
        return _hit(name, axis, weight, 7.0, f"{months:.0f} mois d'autonomie")
    return _hit(name, axis, weight, 0.0, f"{months:.0f} mois d'autonomie")


def rule_dilution(m: Metrics) -> RuleOutcome:
    """Test de dilution du §4 : nombre d'actions + item 8-K 3.02."""
    name, axis, weight = "Dilution", "risk", 1.0
    growth = m.share_count_growth_pct
    filings_signal = bool(m.dilution_filings)

    if growth is None and not m.filings_available:
        return _skip(name, axis, weight, "série du nombre d'actions et dépôts indisponibles")
    if growth is None:
        if filings_signal:
            return _hit(
                name, axis, weight, 8.0,
                f"{len(m.dilution_filings)} dépôt(s) 8-K item 3.02 (émission non enregistrée)",
            )
        return _skip(name, axis, weight, "série du nombre d'actions absente du XBRL")

    label = f"nombre d'actions {growth:+.1f} % sur un exercice"
    if filings_signal:
        label += f", {len(m.dilution_filings)} 8-K item 3.02"
    if growth > DILUTION_HEAVY_PCT:
        return _hit(name, axis, weight, 15.0, label)
    if growth > DILUTION_MILD_PCT or filings_signal:
        return _hit(name, axis, weight, 6.0, label)
    if growth < -1.0:
        return _hit(name, axis, weight, 0.0, f"{label} — rachats d'actions")
    return _hit(name, axis, weight, 0.0, label)


def rule_disclosure(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Transparence réglementaire", "risk", 1.0
    if not m.filings_available:
        return _skip(name, axis, weight, "appel EDGAR en échec — absence non vérifiable")
    if not m.filings:
        return _hit(name, axis, weight, 12.0, "aucun dépôt SEC récent trouvé")
    days = m.days_since_last_filing
    if days is None:
        return _hit(name, axis, weight, 4.0, "dépôts présents mais non datés")
    if days > FILING_SILENCE_DAYS:
        return _hit(name, axis, weight, 10.0, f"dernier dépôt il y a {days} jours")
    return _hit(name, axis, weight, 0.0, f"dernier dépôt il y a {days} jours")


def rule_insider_selling(m: Metrics) -> RuleOutcome:
    """Volet vendeur du test de gouvernance (§4), à partir des Form 4 lus."""
    name, axis, weight = "Ventes d'initiés", "risk", 1.2
    activity = m.insider
    if activity is None or not activity.available:
        return _skip(name, axis, weight, "aucun Form 4 exploitable")
    verdict = activity.verdict()
    if verdict == "VENTE_GROUPEE":
        return _hit(
            name, axis, weight, 14.0,
            f"{activity.distinct_sellers} initiés vendeurs, net "
            f"{activity.net_value:,.0f}".replace(",", " "),
        )
    if verdict == "VENTE":
        return _hit(
            name, axis, weight, 6.0,
            f"{len(activity.sells)} vente(s) d'initiés sur {activity.forms_read} Form 4",
        )
    return _hit(name, axis, weight, 0.0, f"pas de vente d'initiés dominante ({verdict})")


def rule_downside_trend(m: Metrics) -> RuleOutcome:
    """Position de marché dégradée : tendance et perte depuis les sommets."""
    name, axis, weight, group = "Tendance de marché", "risk", 1.0, MARKET
    view = m.technical
    if view is None or not view.has_signal:
        return _skip(name, axis, weight, "historique de cours insuffisant", group)
    if view.signal == "BAISSIER":
        return _hit(
            name, axis, weight, 12.0,
            f"tendance baissière (cours < SMA50 < SMA200, momentum "
            f"{view.momentum_20d_pct:+.1f} %)",
            group,
        )
    if view.max_drawdown_pct and view.max_drawdown_pct > DRAWDOWN_SEVERE_PCT:
        return _hit(
            name, axis, weight, 6.0,
            f"perte maximale historique de {view.max_drawdown_pct:.0f} %",
            group,
        )
    return _hit(name, axis, weight, 0.0, f"tendance {view.signal.lower()}", group)


# --- Règles d'opportunité -------------------------------------------------

def rule_upside(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Potentiel vs PE de référence", "opportunity", 2.0
    if m.upside_pe_pct is None:
        return _skip(name, axis, weight, "prix cible non calculable (BPA ≤ 0 ou prix absent)")
    upside = m.upside_pe_pct
    label = f"écart au prix cible {m.target_price_pe} {m.currency} : {upside:+.1f} %"
    if upside > UPSIDE_STRONG:
        return _hit(name, axis, weight, 20.0, label)
    if upside > UPSIDE_MODERATE:
        return _hit(name, axis, weight, 10.0, label)
    if upside < DOWNSIDE_ALERT:
        return _hit(name, axis, weight, -12.0, label)
    return _hit(name, axis, weight, 0.0, label)


def rule_dcf_upside(m: Metrics) -> RuleOutcome:
    """Marge de sécurité issue du DCF (§7 : « prix < valeur intrinsèque »)."""
    name, axis, weight = "Marge de sécurité (DCF)", "opportunity", 1.8
    if not m.dcf.available or m.dcf.upside_pct is None:
        reason = m.dcf.warnings[-1] if m.dcf.warnings else "DCF non calculable"
        return _skip(name, axis, weight, reason)
    upside = m.dcf.upside_pct
    label = (
        f"valeur DCF {m.dcf.value_per_share} {m.currency} "
        f"(fourchette {m.dcf.low_per_share}–{m.dcf.high_per_share}) : {upside:+.1f} %"
    )
    if upside > DCF_UPSIDE_STRONG:
        return _hit(name, axis, weight, 18.0, label)
    if upside > DCF_UPSIDE_MODERATE:
        return _hit(name, axis, weight, 9.0, label)
    if upside < -25.0:
        return _hit(name, axis, weight, -10.0, label)
    return _hit(name, axis, weight, 0.0, label)


def rule_quality(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Qualité opérationnelle", "opportunity", 1.5
    if m.profit_margin is None:
        return _skip(name, axis, weight, "marge nette indisponible")
    if m.profit_margin > MARGIN_STRONG:
        return _hit(name, axis, weight, 12.0, f"marge nette {m.profit_margin:.1%}")
    if m.profit_margin > MARGIN_WEAK:
        return _hit(name, axis, weight, 4.0, f"marge nette {m.profit_margin:.1%}")
    return _hit(name, axis, weight, 0.0, f"marge nette {m.profit_margin:.1%}")


def rule_growth(m: Metrics) -> RuleOutcome:
    """Test de croissance du §4 : le chiffre d'affaires progresse-t-il ?"""
    name, axis, weight = "Croissance du chiffre d'affaires", "opportunity", 1.5
    if m.revenue_growth_yoy_pct is None:
        return _skip(
            name, axis, weight,
            m.revenue_growth_note or "moins de deux exercices annuels disponibles",
        )
    growth = m.revenue_growth_yoy_pct
    label = f"{growth:+.1f} % sur un exercice"
    if m.revenue_cagr_pct is not None:
        label += f", TCAC {m.revenue_cagr_pct:+.1f} %"
    if growth > GROWTH_STRONG_PCT:
        return _hit(name, axis, weight, 14.0, label)
    if growth > 0:
        return _hit(name, axis, weight, 5.0, label)
    if growth < GROWTH_NEGATIVE_PCT:
        return _hit(name, axis, weight, -8.0, label)
    return _hit(name, axis, weight, 0.0, label)


def rule_discount(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Décote de valorisation", "opportunity", 1.0
    if m.pe_ratio is None or m.pe_sector is None:
        return _skip(name, axis, weight, "PE indisponible")
    ratio = m.pe_ratio / m.pe_sector
    if ratio < PE_DISCOUNT_MULTIPLE:
        return _hit(
            name, axis, weight, 10.0, f"PE {m.pe_ratio:.1f} = {ratio:.0%} de la référence"
        )
    return _hit(name, axis, weight, 0.0, f"PE à {ratio:.0%} de la référence")


def rule_catalyst(m: Metrics) -> RuleOutcome:
    """Catalyseurs : items 8-K d'alerte, et non simple présence d'un dépôt."""
    name, axis, weight = "Catalyseurs réglementaires", "opportunity", 1.2
    if not m.filings_available:
        return _skip(name, axis, weight, "flux EDGAR indisponible")
    if m.alert_filings:
        described = "; ".join(
            ", ".join(f.item_labels() or f.items) for f in m.alert_filings[:3]
        )
        return _hit(
            name, axis, weight, 10.0,
            f"{len(m.alert_filings)} 8-K à item d'alerte — {described}",
        )
    weightsum = sum(f.signal_weight for f in m.filings[:15])
    if weightsum >= 6:
        return _hit(name, axis, weight, 4.0, "activité de dépôt soutenue, sans item d'alerte")
    return _hit(name, axis, weight, 0.0, "aucun catalyseur réglementaire récent")


def rule_insider_buying(m: Metrics) -> RuleOutcome:
    """« SI Form 4 ET achat d'initié → SIGNAL BULLISH » — enfin calculable."""
    name, axis, weight = "Achats d'initiés", "opportunity", 1.5
    activity = m.insider
    if activity is None or not activity.available:
        return _skip(name, axis, weight, "aucun Form 4 exploitable")
    verdict = activity.verdict()
    if verdict == "ACHAT_GROUPE":
        return _hit(
            name, axis, weight, 16.0,
            f"{activity.distinct_buyers} initiés acheteurs sur le marché, net "
            f"{activity.net_value:,.0f}".replace(",", " "),
        )
    if verdict == "ACHAT_ISOLE":
        return _hit(
            name, axis, weight, 7.0,
            f"{len(activity.buys)} achat(s) d'initié sur le marché",
        )
    if verdict == "NEUTRE_REMUNERATION":
        return _hit(
            name, axis, weight, 0.0,
            f"{activity.forms_read} Form 4 : uniquement de la rémunération, aucun achat de marché",
        )
    return _hit(name, axis, weight, 0.0, f"pas d'achat d'initié dominant ({verdict})")


def rule_momentum(m: Metrics) -> RuleOutcome:
    """Signal technique — la règle exacte mesurée par le backtest."""
    name, axis, weight, group = "Momentum technique", "opportunity", 1.2, MARKET
    view = m.technical
    if view is None or not view.has_signal:
        return _skip(
            name, axis, weight,
            f"historique de cours insuffisant ({view.history_points if view else 0} séances)",
            group,
        )
    label = (
        f"signal {view.signal}, momentum 20 séances {view.momentum_20d_pct:+.1f} %, "
        f"RSI {view.rsi_14:.0f}"
    )
    if view.signal == "HAUSSIER":
        return _hit(name, axis, weight, 10.0, label, group)
    if view.signal == "BAISSIER":
        return _hit(name, axis, weight, -8.0, label, group)
    return _hit(name, axis, weight, 0.0, label, group)


RULES: Sequence[Rule] = (
    rule_leverage,
    rule_valuation,
    rule_profitability,
    rule_liquidity,
    rule_cash_runway,
    rule_dilution,
    rule_disclosure,
    rule_insider_selling,
    rule_downside_trend,
    rule_upside,
    rule_dcf_upside,
    rule_quality,
    rule_growth,
    rule_discount,
    rule_catalyst,
    rule_insider_buying,
    rule_momentum,
)

BASELINE = 50.0


def market_position_score(metrics: Metrics) -> float | None:
    """Composante « position marché » du score de résilience (0-100)."""
    view = metrics.technical
    if view is None or not view.has_signal:
        return None
    score = 50.0
    if view.signal == "HAUSSIER":
        score += 18
    elif view.signal == "BAISSIER":
        score -= 18
    if view.distance_from_high_pct is not None:
        # Proche des plus hauts = position de force ; -50 % = position dégradée.
        score += max(-15.0, min(10.0, view.distance_from_high_pct / 3.0))
    if view.max_drawdown_pct is not None and view.max_drawdown_pct > DRAWDOWN_SEVERE_PCT:
        score -= 8
    if view.volatility_annual_pct is not None and view.volatility_annual_pct > 60:
        score -= 6
    return round(max(0.0, min(100.0, score)), 1)


def compute(
    metrics: Metrics,
    rules: Sequence[Rule] = RULES,
    macro_score: float | None = None,
) -> ScoreResult:
    """Applique les règles et retourne un résultat traçable."""
    outcomes = [rule(metrics) for rule in rules]

    risk = BASELINE
    opportunity = BASELINE
    for outcome in outcomes:
        if not outcome.evaluated:
            continue
        if outcome.axis == "risk":
            risk += outcome.points
        else:
            opportunity += outcome.points

    risk = _clamp(risk)
    opportunity = _clamp(opportunity)
    net = opportunity - risk

    total_weight = sum(o.weight for o in outcomes) or 1.0
    evaluated_weight = sum(o.weight for o in outcomes if o.evaluated)
    confidence = round(evaluated_weight / total_weight, 3)

    result = ScoreResult(
        risk_score=round(risk, 1),
        opportunity_score=round(opportunity, 1),
        net_score=round(net, 1),
        recommendation=_recommend(net, opportunity, confidence),
        confidence=confidence,
        outcomes=outcomes,
    )
    _attach_resilience(result, metrics, macro_score)
    return result


def _attach_resilience(
    result: ScoreResult, metrics: Metrics, macro_score: float | None
) -> None:
    """Résilience = 50 % fondamentaux + 25 % marché + 25 % macro (§4 du guide).

    Les composantes absentes ne sont pas remplacées par une valeur neutre : les
    poids sont renormalisés sur ce qui a pu être mesuré, et la composition est
    exposée dans ``resilience_parts``.
    """
    fundamental_outcomes = [
        o for o in result.outcomes if o.group == FUNDAMENTAL and o.evaluated
    ]
    fundamental = None
    if fundamental_outcomes:
        fund_risk = _clamp(
            BASELINE + sum(o.points for o in fundamental_outcomes if o.axis == "risk")
        )
        fund_opp = _clamp(
            BASELINE + sum(o.points for o in fundamental_outcomes if o.axis == "opportunity")
        )
        fundamental = round(_clamp((fund_opp + (100.0 - fund_risk)) / 2.0), 1)

    market = market_position_score(metrics)

    result.resilience_parts = {
        "fondamentaux": fundamental,
        "position_marche": market,
        "macro": round(macro_score, 1) if macro_score is not None else None,
    }

    weights = {"fondamentaux": 0.5, "position_marche": 0.25, "macro": 0.25}
    available = {
        key: value for key, value in result.resilience_parts.items() if value is not None
    }
    if not available:
        result.resilience_score = None
        return
    total = sum(weights[key] for key in available)
    result.resilience_score = round(
        sum(value * weights[key] for key, value in available.items()) / total, 1
    )


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _recommend(net: float, opportunity: float, confidence: float) -> str:
    if confidence < MIN_CONFIDENCE:
        return "INSUFFICIENT_DATA"
    if net >= 25 and opportunity >= 65:
        return "STRONG_BUY"
    if net >= 10 and opportunity >= 55:
        return "BUY"
    if net >= -10:
        return "HOLD"
    if net >= -25:
        return "REDUCE"
    return "SELL"
