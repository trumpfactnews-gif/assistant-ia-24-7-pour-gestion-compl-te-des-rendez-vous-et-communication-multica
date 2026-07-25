"""Valorisation : DCF et prix cible par multiple sectoriel.

Le guide annonçait « Prix cibles (PE et DCF) » et « upside DCF » ; seul le PE
était calculé, et contre une table de multiples codée en dur. Ce module comble
les deux manques :

* un **DCF explicite** à partir du flux de trésorerie disponible tiré du XBRL
  (flux d'exploitation moins investissements corporels), avec toutes les
  hypothèses nommées, bornées et exposées dans le rapport ;
* un **PE de comparables** calculé sur un panier de sociétés fourni par
  l'utilisateur, avec repli documenté sur la table statique.

Un DCF est un modèle d'hypothèses, pas une mesure. Trois scénarios (prudent,
central, optimiste) sont donc produits ensemble : un DCF à un seul chiffre
donne une fausse impression de précision.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

# Bornes de sécurité sur les hypothèses : au-delà, le modèle ne veut plus rien
# dire (croissance perpétuelle > coût du capital = valeur infinie).
MIN_WACC = 0.04
MAX_WACC = 0.20
DEFAULT_WACC = 0.09
DEFAULT_TERMINAL_GROWTH = 0.025
MAX_TERMINAL_GROWTH = 0.035
DEFAULT_HORIZON_YEARS = 5
GROWTH_FLOOR = -0.05
GROWTH_CAP = 0.20
DEFAULT_GROWTH = 0.04


@dataclass(frozen=True)
class DcfAssumptions:
    free_cash_flow: float
    growth: float
    wacc: float
    terminal_growth: float
    years: int
    net_debt: float
    shares: float

    def to_dict(self) -> dict[str, object]:
        return {
            "free_cash_flow": round(self.free_cash_flow, 2),
            "growth_pct": round(self.growth * 100, 2),
            "wacc_pct": round(self.wacc * 100, 2),
            "terminal_growth_pct": round(self.terminal_growth * 100, 2),
            "years": self.years,
            "net_debt": round(self.net_debt, 2),
            "shares": round(self.shares, 0),
        }


@dataclass
class DcfResult:
    value_per_share: float | None = None
    low_per_share: float | None = None
    high_per_share: float | None = None
    enterprise_value: float | None = None
    equity_value: float | None = None
    assumptions: DcfAssumptions | None = None
    upside_pct: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.value_per_share is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "value_per_share": self.value_per_share,
            "low_per_share": self.low_per_share,
            "high_per_share": self.high_per_share,
            "enterprise_value": self.enterprise_value,
            "equity_value": self.equity_value,
            "upside_pct": self.upside_pct,
            "assumptions": self.assumptions.to_dict() if self.assumptions else None,
            "warnings": self.warnings,
        }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def implied_growth(revenue_series: list[float]) -> tuple[float, str]:
    """Croissance annuelle composée du chiffre d'affaires, bornée.

    Retourne ``(taux, justification)``. Sans historique suffisant, on retombe
    sur une hypothèse prudente explicite plutôt que sur un chiffre inventé.
    """
    usable = [v for v in revenue_series if v > 0]
    if len(usable) < 3:
        return DEFAULT_GROWTH, "historique insuffisant : hypothèse par défaut de 4 %/an"
    periods = len(usable) - 1
    cagr = (usable[-1] / usable[0]) ** (1.0 / periods) - 1.0
    bounded = _clamp(cagr, GROWTH_FLOOR, GROWTH_CAP)
    note = f"TCAC du chiffre d'affaires sur {periods} exercices : {cagr * 100:.1f} %"
    if bounded != cagr:
        note += f", ramené à {bounded * 100:.1f} % (bornes de prudence)"
    return bounded, note


def discounted_cash_flow(
    free_cash_flow: float | None,
    shares: float | None,
    net_debt: float,
    growth: float,
    wacc: float = DEFAULT_WACC,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    years: int = DEFAULT_HORIZON_YEARS,
    current_price: float | None = None,
) -> DcfResult:
    """DCF à deux étages (projection explicite + valeur terminale de Gordon)."""
    result = DcfResult()

    if free_cash_flow is None or shares is None:
        result.warnings.append("flux de trésorerie disponible ou nombre d'actions indisponible")
        return result
    if free_cash_flow <= 0:
        result.warnings.append(
            f"flux de trésorerie disponible négatif ({free_cash_flow:,.0f}) : DCF non applicable"
        )
        return result
    if shares <= 0:
        result.warnings.append("nombre d'actions invalide")
        return result

    wacc = _clamp(wacc, MIN_WACC, MAX_WACC)
    terminal_growth = _clamp(terminal_growth, 0.0, MAX_TERMINAL_GROWTH)
    if terminal_growth >= wacc - 0.01:
        terminal_growth = wacc - 0.02
        result.warnings.append(
            "croissance terminale ramenée sous le coût du capital (contrainte du modèle)"
        )
    years = int(_clamp(float(years), 3, 10))
    growth = _clamp(growth, GROWTH_FLOOR, GROWTH_CAP)

    def evaluate(g: float) -> float:
        present = 0.0
        cash = free_cash_flow
        for year in range(1, years + 1):
            cash = cash * (1.0 + g)
            present += cash / ((1.0 + wacc) ** year)
        terminal = cash * (1.0 + terminal_growth) / (wacc - terminal_growth)
        return present + terminal / ((1.0 + wacc) ** years)

    enterprise = evaluate(growth)
    equity = enterprise - net_debt
    if equity <= 0:
        result.warnings.append(
            "valeur des capitaux propres négative après déduction de la dette nette"
        )

    result.enterprise_value = round(enterprise, 2)
    result.equity_value = round(equity, 2)
    result.value_per_share = round(equity / shares, 2)
    # Scénarios : croissance ±5 points, plancher et plafond conservés.
    result.low_per_share = round((evaluate(_clamp(growth - 0.05, GROWTH_FLOOR, GROWTH_CAP)) - net_debt) / shares, 2)
    result.high_per_share = round((evaluate(_clamp(growth + 0.05, GROWTH_FLOOR, GROWTH_CAP)) - net_debt) / shares, 2)
    result.assumptions = DcfAssumptions(
        free_cash_flow=free_cash_flow,
        growth=growth,
        wacc=wacc,
        terminal_growth=terminal_growth,
        years=years,
        net_debt=net_debt,
        shares=shares,
    )

    if current_price and current_price > 0 and result.value_per_share is not None:
        result.upside_pct = round(
            (result.value_per_share - current_price) / current_price * 100.0, 2
        )
    return result


@dataclass
class PeerValuation:
    """PE médian d'un panier de comparables réellement mesurés."""

    median_pe: float | None = None
    peers_used: list[tuple[str, float]] = field(default_factory=list)
    peers_failed: list[str] = field(default_factory=list)
    source: str = "table sectorielle statique"

    def to_dict(self) -> dict[str, object]:
        return {
            "median_pe": self.median_pe,
            "source": self.source,
            "peers_used": [{"ticker": t, "pe": pe} for t, pe in self.peers_used],
            "peers_failed": self.peers_failed,
        }


def peer_median_pe(measured: dict[str, float | None]) -> PeerValuation:
    """Médiane des PE de comparables, en ignorant les valeurs aberrantes.

    Un PE négatif (pertes) ou supérieur à 150 ne renseigne pas sur la
    valorisation relative : il est écarté et le titre est listé comme non
    exploitable, pas silencieusement oublié.
    """
    valuation = PeerValuation()
    for ticker, pe in measured.items():
        if pe is None or pe <= 0 or pe > 150:
            valuation.peers_failed.append(ticker)
            continue
        valuation.peers_used.append((ticker, round(pe, 2)))

    if len(valuation.peers_used) >= 3:
        valuation.median_pe = round(statistics.median(pe for _, pe in valuation.peers_used), 2)
        valuation.source = f"médiane de {len(valuation.peers_used)} comparables"
    elif valuation.peers_used:
        valuation.source = (
            f"seulement {len(valuation.peers_used)} comparable(s) exploitable(s) : "
            "repli sur la table sectorielle"
        )
    return valuation
