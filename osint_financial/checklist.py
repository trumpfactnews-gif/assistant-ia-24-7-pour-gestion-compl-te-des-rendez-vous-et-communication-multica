"""Critères d'entrée et de sortie du §7 du guide, rendus vérifiables.

Le guide énonçait deux règles composites :

* achat — « score_qualité ≥ 70 ET marge_sécurité ≥ 20 % ET sentiment pessimiste
  ET macro favorable ET catalyseur identifié » ;
* vente — « prix > 120 % valeur intrinsèque OU moat détérioré OU bénéfices
  décélèrent ».

Aucune ligne de code ne les évaluait. Elles sont ici décomposées en critères
individuels, chacun avec son état (rempli / non rempli / non mesurable) et sa
preuve chiffrée. Un critère non mesurable n'est **jamais** compté comme rempli :
c'est la différence entre une checklist et un argument de vente.

Le critère « moat détérioré » reste non mesurable : évaluer un avantage
concurrentiel demande une lecture qualitative du 10-K et de la concurrence. Il
est listé comme tel plutôt qu'approximé par un ratio sans rapport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .macro import FAVORABLE, MarketRegime
from .metrics import Metrics
from .scoring import ScoreResult

QUALITY_THRESHOLD = 70.0
MARGIN_OF_SAFETY_PCT = 20.0
OVERVALUATION_PCT = 20.0  # prix > 120 % de la valeur intrinsèque
PESSIMISM_RSI = 45.0
PESSIMISM_DRAWDOWN_PCT = -20.0


@dataclass(frozen=True)
class Criterion:
    label: str
    met: bool | None  # None = non mesurable
    evidence: str

    @property
    def state(self) -> str:
        return {True: "rempli", False: "non rempli", None: "non mesurable"}[self.met]

    def to_dict(self) -> dict[str, object]:
        return {"label": self.label, "state": self.state, "evidence": self.evidence}


@dataclass
class Checklist:
    name: str
    mode: str  # "ET" ou "OU"
    criteria: list[Criterion] = field(default_factory=list)

    @property
    def measurable(self) -> list[Criterion]:
        return [c for c in self.criteria if c.met is not None]

    @property
    def unmeasurable(self) -> list[Criterion]:
        return [c for c in self.criteria if c.met is None]

    @property
    def satisfied(self) -> bool:
        """Conjonction ou disjonction, sur les seuls critères mesurables.

        Une conjonction comportant un critère non mesurable ne peut pas être
        déclarée satisfaite : l'inconnu n'est pas un feu vert.
        """
        if not self.measurable:
            return False
        if self.mode == "ET":
            return not self.unmeasurable and all(c.met for c in self.measurable)
        return any(c.met for c in self.measurable)

    @property
    def score(self) -> str:
        met = sum(1 for c in self.measurable if c.met)
        return f"{met}/{len(self.criteria)}"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "mode": self.mode,
            "satisfied": self.satisfied,
            "score": self.score,
            "criteria": [c.to_dict() for c in self.criteria],
        }


def entry_checklist(
    metrics: Metrics, scores: ScoreResult, regime: MarketRegime | None = None
) -> Checklist:
    """« score_qualité ≥ 70 ET marge_sécurité ≥ 20 % ET pessimisme ET macro ET catalyseur »."""
    checklist = Checklist(name="Critères d'achat (§7)", mode="ET")

    checklist.criteria.append(
        Criterion(
            label=f"Score d'opportunité ≥ {QUALITY_THRESHOLD:.0f}",
            met=scores.opportunity_score >= QUALITY_THRESHOLD,
            evidence=f"score {scores.opportunity_score}/100",
        )
    )

    upside = metrics.dcf.upside_pct if metrics.dcf.available else None
    checklist.criteria.append(
        Criterion(
            label=f"Marge de sécurité ≥ {MARGIN_OF_SAFETY_PCT:.0f} % (DCF)",
            met=None if upside is None else upside >= MARGIN_OF_SAFETY_PCT,
            evidence=(
                f"écart au DCF {upside:+.1f} %" if upside is not None else "DCF non calculable"
            ),
        )
    )

    checklist.criteria.append(_pessimism_criterion(metrics))

    checklist.criteria.append(
        Criterion(
            label="Contexte de marché favorable",
            met=None if regime is None or not regime.available else regime.regime == FAVORABLE,
            evidence=(
                f"régime {regime.regime} (score {regime.score}/100)"
                if regime is not None and regime.available
                else "contexte de marché non évalué"
            ),
        )
    )

    checklist.criteria.append(_catalyst_criterion(metrics))
    return checklist


def _pessimism_criterion(metrics: Metrics) -> Criterion:
    """« Sentiment pessimiste » : mesuré par le prix, faute de source de sentiment.

    Le guide parlait de sentiment de marché sans source pour le quantifier. On
    l'approche par deux marqueurs observables — RSI bas ou repli marqué depuis
    les plus hauts — et on le dit explicitement.
    """
    view = metrics.technical
    if view is None or not view.has_signal:
        return Criterion(
            label="Sentiment pessimiste (approché par le prix)",
            met=None,
            evidence="historique de cours insuffisant",
        )
    oversold = view.rsi_14 is not None and view.rsi_14 < PESSIMISM_RSI
    beaten = (
        view.distance_from_high_pct is not None
        and view.distance_from_high_pct <= PESSIMISM_DRAWDOWN_PCT
    )
    return Criterion(
        label="Sentiment pessimiste (approché par le prix)",
        met=oversold or beaten,
        evidence=(
            f"RSI {view.rsi_14:.0f}, écart au plus haut 52 semaines "
            f"{view.distance_from_high_pct:+.1f} %"
        ),
    )


def _catalyst_criterion(metrics: Metrics) -> Criterion:
    if not metrics.filings_available:
        return Criterion(
            label="Catalyseur identifié",
            met=None,
            evidence="flux EDGAR indisponible",
        )
    insider_buying = (
        metrics.insider is not None
        and metrics.insider.available
        and metrics.insider.verdict() in {"ACHAT_GROUPE", "ACHAT_ISOLE"}
    )
    reasons = []
    if metrics.alert_filings:
        reasons.append(f"{len(metrics.alert_filings)} 8-K à item d'alerte")
    if insider_buying:
        reasons.append("achat d'initié sur le marché")
    return Criterion(
        label="Catalyseur identifié",
        met=bool(reasons),
        evidence=", ".join(reasons) or "aucun catalyseur récent",
    )


def exit_checklist(metrics: Metrics) -> Checklist:
    """« prix > 120 % valeur intrinsèque OU moat détérioré OU bénéfices décélèrent »."""
    checklist = Checklist(name="Critères de vente (§7)", mode="OU")

    upside = metrics.dcf.upside_pct if metrics.dcf.available else None
    checklist.criteria.append(
        Criterion(
            label=f"Cours > {100 + OVERVALUATION_PCT:.0f} % de la valeur intrinsèque",
            met=None if upside is None else upside <= -OVERVALUATION_PCT,
            evidence=(
                f"écart au DCF {upside:+.1f} %" if upside is not None else "DCF non calculable"
            ),
        )
    )

    checklist.criteria.append(
        Criterion(
            label="Avantage concurrentiel détérioré",
            met=None,
            evidence=(
                "non mesurable automatiquement : demande une lecture qualitative "
                "du 10-K et du paysage concurrentiel"
            ),
        )
    )

    growth = metrics.revenue_growth_yoy_pct
    checklist.criteria.append(
        Criterion(
            label="Bénéfices ou revenus en décélération",
            met=None if growth is None else growth < 0 or (metrics.profit_margin or 1) < 0,
            evidence=(
                f"croissance du chiffre d'affaires {growth:+.1f} %"
                + (
                    f", marge nette {metrics.profit_margin:.1%}"
                    if metrics.profit_margin is not None
                    else ""
                )
                if growth is not None
                else "série annuelle indisponible"
            ),
        )
    )
    return checklist
