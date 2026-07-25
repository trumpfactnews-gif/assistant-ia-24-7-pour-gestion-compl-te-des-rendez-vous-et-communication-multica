"""Backtest du signal technique.

Le §8 du guide reconnaissait « Pas de backtesting » tout en promettant au §3 une
« direction du prix (7j) ». C'est la contradiction centrale de l'outil : une
prédiction non mesurée n'a pas de valeur informative.

Ce module mesure la règle exacte de :func:`osint_financial.technical.classify`
sur l'historique disponible : pour chaque séance, on classe l'état du marché,
puis on observe le rendement des ``horizon`` séances **suivantes**. Aucune
donnée future n'entre dans la classification (pas de biais de survie sur la
fenêtre, pas de *look-ahead*).

Limites — énoncées parce qu'elles conditionnent la lecture :

* mesure **en échantillon** sur un seul titre : ce n'est pas une validation
  hors échantillon ;
* pas de frais, pas de slippage, pas de dividendes ;
* les rendements quotidiens se recouvrent (fenêtres glissantes), donc les
  observations ne sont pas indépendantes : le taux de réussite est indicatif,
  pas un test statistique ;
* seul le volet **technique** est backtesté. Le volet fondamental ne l'est pas,
  parce qu'il faudrait des données SEC « telles que connues à la date »
  (les faits XBRL sont retraités a posteriori) — le mesurer sur les données
  actuelles produirait un résultat flatteur et faux.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .technical import BAISSIER, HAUSSIER, MIN_HISTORY, NEUTRE, classify
from .sources.prices import PriceSeries

DEFAULT_HORIZON = 7


@dataclass
class SignalStats:
    signal: str
    observations: int = 0
    mean_return_pct: float | None = None
    median_return_pct: float | None = None
    hit_rate_pct: float | None = None
    worst_pct: float | None = None
    best_pct: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "signal": self.signal,
            "observations": self.observations,
            "mean_return_pct": self.mean_return_pct,
            "median_return_pct": self.median_return_pct,
            "hit_rate_pct": self.hit_rate_pct,
            "worst_pct": self.worst_pct,
            "best_pct": self.best_pct,
        }


@dataclass
class BacktestResult:
    symbol: str
    horizon: int
    total_observations: int = 0
    baseline: SignalStats = field(default_factory=lambda: SignalStats("TOUTES SÉANCES"))
    per_signal: dict[str, SignalStats] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """Vrai si l'échantillon est assez fourni pour être commenté."""
        return self.total_observations >= 100

    def edge_pct(self, signal: str) -> float | None:
        """Écart de rendement moyen entre ce signal et la référence."""
        stats = self.per_signal.get(signal)
        if not stats or stats.mean_return_pct is None or self.baseline.mean_return_pct is None:
            return None
        return round(stats.mean_return_pct - self.baseline.mean_return_pct, 3)

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "horizon": self.horizon,
            "total_observations": self.total_observations,
            "usable": self.usable,
            "baseline": self.baseline.to_dict(),
            "per_signal": {k: v.to_dict() for k, v in self.per_signal.items()},
            "edge": {k: self.edge_pct(k) for k in self.per_signal},
            "warnings": self.warnings,
        }


def _stats(label: str, returns: list[float]) -> SignalStats:
    stats = SignalStats(signal=label, observations=len(returns))
    if not returns:
        return stats
    stats.mean_return_pct = round(statistics.fmean(returns), 3)
    stats.median_return_pct = round(statistics.median(returns), 3)
    stats.hit_rate_pct = round(sum(1 for r in returns if r > 0) / len(returns) * 100.0, 1)
    stats.worst_pct = round(min(returns), 2)
    stats.best_pct = round(max(returns), 2)
    return stats


def run(series: PriceSeries, horizon: int = DEFAULT_HORIZON) -> BacktestResult:
    """Évalue la règle technique sur toute la série disponible."""
    horizon = max(1, min(60, int(horizon)))
    result = BacktestResult(symbol=series.symbol, horizon=horizon)
    closes = series.closes

    if len(closes) < MIN_HISTORY + horizon + 20:
        result.warnings.append(
            f"historique insuffisant ({len(closes)} séances) : "
            f"il en faut au moins {MIN_HISTORY + horizon + 20}"
        )
        return result

    buckets: dict[str, list[float]] = {HAUSSIER: [], BAISSIER: [], NEUTRE: []}
    everything: list[float] = []

    # `end` est exclusif : la classification n'utilise que closes[:end], et le
    # rendement observé porte sur des séances strictement postérieures.
    for end in range(MIN_HISTORY, len(closes) - horizon):
        entry = closes[end - 1]
        exit_price = closes[end - 1 + horizon]
        if entry <= 0:
            continue
        forward = (exit_price - entry) / entry * 100.0
        signal = classify(closes[:end])
        buckets[signal].append(forward)
        everything.append(forward)

    result.total_observations = len(everything)
    result.baseline = _stats("TOUTES SÉANCES", everything)
    result.per_signal = {label: _stats(label, values) for label, values in buckets.items()}

    for label, stats in result.per_signal.items():
        if 0 < stats.observations < 30:
            result.warnings.append(
                f"{label} : seulement {stats.observations} observations, non concluant"
            )
    if not result.usable:
        result.warnings.append(
            "échantillon global insuffisant pour interpréter les écarts"
        )
    return result
