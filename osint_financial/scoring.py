"""Moteur de scoring explicite, déterministe et auditable.

Défauts corrigés du ``calculate_scores`` d'origine :

1. **Données manquantes = données neutres.** Les scores partaient de 50 et
   restaient à 50 si aucune source ne répondait. Une entreprise dont on ne sait
   rien recevait donc « HOLD » avec la même assurance visuelle qu'une analyse
   complète. Ici chaque règle non évaluable est comptabilisée, et un indice de
   confiance conditionne la recommandation : sous 50 % de couverture, la sortie
   est ``INSUFFICIENT_DATA``.
2. **``if debt and debt > 0.5``.** Le test de véracité masquait le cas
   ``debt == 0`` (sain) et surtout ne distinguait pas ``None`` de ``0.0``.
3. **Division par zéro.** ``(target_pe - price) / price`` n'était pas protégé.
4. **Aucune traçabilité.** Impossible de savoir quelle règle avait produit
   quel point. Chaque règle retourne désormais son intitulé, ses points et la
   preuve chiffrée qui la déclenche.
5. **Seuils magiques dispersés.** Ils sont regroupés en constantes nommées.
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

MIN_CONFIDENCE = 0.50


@dataclass(frozen=True)
class RuleOutcome:
    name: str
    axis: str  # "risk" ou "opportunity"
    points: float
    evidence: str
    evaluated: bool
    weight: float


@dataclass
class ScoreResult:
    risk_score: float
    opportunity_score: float
    net_score: float
    recommendation: str
    confidence: float
    outcomes: list[RuleOutcome] = field(default_factory=list)

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
            "risk_factors": self.risk_factors,
            "opportunity_factors": self.opportunity_factors,
            "missing_inputs": self.missing_inputs,
        }


Rule = Callable[[Metrics], RuleOutcome]


def _skip(name: str, axis: str, weight: float, reason: str) -> RuleOutcome:
    return RuleOutcome(name, axis, 0.0, reason, evaluated=False, weight=weight)


def _hit(name: str, axis: str, weight: float, points: float, evidence: str) -> RuleOutcome:
    return RuleOutcome(name, axis, points, evidence, evaluated=True, weight=weight)


# --- Règles de risque -----------------------------------------------------

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
    name, axis, weight = "Valorisation vs secteur", "risk", 1.5
    if m.pe_ratio is None or m.pe_sector is None:
        return _skip(name, axis, weight, "PE indisponible (BPA ou prix manquant)")
    ratio = m.pe_ratio / m.pe_sector
    label = f"PE {m.pe_ratio:.1f} vs médiane {m.sector} {m.pe_sector:.0f}"
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


def rule_liquidity(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Coussin de trésorerie", "risk", 1.0
    if m.cash is None or m.long_term_debt is None:
        return _skip(name, axis, weight, "trésorerie ou dette long terme absente")
    if m.long_term_debt <= 0:
        return _hit(name, axis, weight, 0.0, "pas de dette long terme déclarée")
    coverage = m.cash / m.long_term_debt
    if coverage < 0.15:
        return _hit(name, axis, weight, 10.0, f"trésorerie = {coverage:.0%} de la dette LT")
    return _hit(name, axis, weight, 0.0, f"trésorerie = {coverage:.0%} de la dette LT")


# --- Règles d'opportunité -------------------------------------------------

def rule_upside(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Potentiel vs PE sectoriel", "opportunity", 2.0
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


def rule_quality(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Qualité opérationnelle", "opportunity", 1.5
    if m.profit_margin is None:
        return _skip(name, axis, weight, "marge nette indisponible")
    if m.profit_margin > MARGIN_STRONG:
        return _hit(name, axis, weight, 12.0, f"marge nette {m.profit_margin:.1%}")
    if m.profit_margin > MARGIN_WEAK:
        return _hit(name, axis, weight, 4.0, f"marge nette {m.profit_margin:.1%}")
    return _hit(name, axis, weight, 0.0, f"marge nette {m.profit_margin:.1%}")


def rule_discount(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Décote de valorisation", "opportunity", 1.0
    if m.pe_ratio is None or m.pe_sector is None:
        return _skip(name, axis, weight, "PE indisponible")
    ratio = m.pe_ratio / m.pe_sector
    if ratio < PE_DISCOUNT_MULTIPLE:
        return _hit(
            name, axis, weight, 10.0, f"PE {m.pe_ratio:.1f} = {ratio:.0%} de la médiane sectorielle"
        )
    return _hit(name, axis, weight, 0.0, f"PE à {ratio:.0%} de la médiane sectorielle")


def rule_catalyst(m: Metrics) -> RuleOutcome:
    name, axis, weight = "Catalyseurs réglementaires", "opportunity", 1.0
    if not m.filings_available:
        return _skip(name, axis, weight, "flux EDGAR indisponible")
    weightsum = sum(f.signal_weight for f in m.filings[:15])
    if weightsum >= 6:
        return _hit(name, axis, weight, 8.0, f"{len(m.strong_signals)} dépôt(s) à fort signal")
    if weightsum >= 3:
        return _hit(name, axis, weight, 4.0, "activité de dépôt notable")
    return _hit(name, axis, weight, 0.0, "aucun catalyseur réglementaire récent")


RULES: Sequence[Rule] = (
    rule_leverage,
    rule_valuation,
    rule_profitability,
    rule_disclosure,
    rule_liquidity,
    rule_upside,
    rule_quality,
    rule_discount,
    rule_catalyst,
)

BASELINE = 50.0


def compute(metrics: Metrics, rules: Sequence[Rule] = RULES) -> ScoreResult:
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

    recommendation = _recommend(net, opportunity, confidence)

    return ScoreResult(
        risk_score=round(risk, 1),
        opportunity_score=round(opportunity, 1),
        net_score=round(net, 1),
        recommendation=recommendation,
        confidence=confidence,
        outcomes=outcomes,
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
