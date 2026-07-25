"""Dimensionnement de position et cadre d'allocation.

Le §7 du guide énonçait des règles précises — « max 20 % par secteur, max 10 %
par position, stop-loss -10 %, prise de profit partielle +50 % », allocation
All Weather — sans qu'aucune ligne de code ne les applique. Elles sont ici
converties en calcul déterministe.

Deux principes :

* **La volatilité réduit la taille.** Une conviction identique sur un titre
  deux fois plus volatil justifie une position deux fois plus petite ; sinon le
  risque du portefeuille est piloté par le hasard.
* **La confiance de l'analyse plafonne la taille.** Une recommandation issue de
  40 % de données ne mérite pas la même exposition qu'une analyse complète.

Ce sont des règles de gestion du risque, pas une recommandation d'investir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_POSITION_PCT = 10.0
MAX_SECTOR_PCT = 20.0
STOP_LOSS_PCT = -10.0
PARTIAL_TAKE_PROFIT_PCT = 50.0
REFERENCE_VOLATILITY = 0.25  # volatilité annualisée « normale » d'une action

#: Allocation All Weather de référence (§7 du guide).
ALL_WEATHER = {
    "Actions": 30.0,
    "Obligations": 40.0,
    "Or": 15.0,
    "Matières premières": 7.5,
    "Liquidités": 7.5,
}

#: Part de l'enveloppe actions accordée selon la recommandation.
_CONVICTION = {
    "STRONG_BUY": 1.0,
    "BUY": 0.6,
    "HOLD": 0.0,
    "REDUCE": 0.0,
    "SELL": 0.0,
    "INSUFFICIENT_DATA": 0.0,
}


@dataclass
class PositionPlan:
    recommendation: str
    suggested_weight_pct: float = 0.0
    max_weight_pct: float = MAX_POSITION_PCT
    stop_loss_price: float | None = None
    partial_take_profit_price: float | None = None
    volatility_annual_pct: float | None = None
    rationale: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "recommendation": self.recommendation,
            "suggested_weight_pct": self.suggested_weight_pct,
            "max_weight_pct": self.max_weight_pct,
            "stop_loss_price": self.stop_loss_price,
            "partial_take_profit_price": self.partial_take_profit_price,
            "volatility_annual_pct": self.volatility_annual_pct,
            "rationale": self.rationale,
            "rules": self.rules,
            "all_weather_reference": ALL_WEATHER,
        }


def build_plan(
    recommendation: str,
    confidence: float,
    price: float | None,
    volatility_annual_pct: float | None,
) -> PositionPlan:
    """Calcule une taille de position et les niveaux de sortie associés."""
    plan = PositionPlan(recommendation=recommendation, volatility_annual_pct=volatility_annual_pct)
    plan.rules = [
        f"Position maximale : {MAX_POSITION_PCT:.0f} % du portefeuille",
        f"Exposition sectorielle maximale : {MAX_SECTOR_PCT:.0f} %",
        f"Stop-loss : {STOP_LOSS_PCT:.0f} % sous le prix d'entrée",
        f"Prise de profit partielle : +{PARTIAL_TAKE_PROFIT_PCT:.0f} %",
    ]

    conviction = _CONVICTION.get(recommendation, 0.0)
    if conviction == 0.0:
        plan.rationale.append(
            f"Recommandation « {recommendation} » : aucune prise de position suggérée."
        )
    else:
        weight = MAX_POSITION_PCT * conviction

        # Pondération par la confiance de l'analyse.
        confidence = max(0.0, min(1.0, confidence))
        weight *= confidence
        plan.rationale.append(
            f"Conviction {conviction:.0%} × confiance de l'analyse {confidence:.0%}"
        )

        # Pondération par la volatilité relative.
        if volatility_annual_pct and volatility_annual_pct > 0:
            volatility = volatility_annual_pct / 100.0
            adjustment = min(1.5, REFERENCE_VOLATILITY / volatility)
            weight *= adjustment
            plan.rationale.append(
                f"Volatilité annualisée {volatility_annual_pct:.0f} % vs référence "
                f"{REFERENCE_VOLATILITY:.0%} → facteur {adjustment:.2f}"
            )
        else:
            plan.rationale.append("Volatilité inconnue : aucun ajustement de taille appliqué")

        plan.suggested_weight_pct = round(min(MAX_POSITION_PCT, weight), 2)

    if price and price > 0:
        plan.stop_loss_price = round(price * (1 + STOP_LOSS_PCT / 100.0), 2)
        plan.partial_take_profit_price = round(price * (1 + PARTIAL_TAKE_PROFIT_PCT / 100.0), 2)

    return plan
