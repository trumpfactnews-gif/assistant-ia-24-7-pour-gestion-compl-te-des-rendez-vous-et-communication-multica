"""Analyse technique et signal directionnel à 7 séances.

Le guide promettait « Direction du prix (7j) via analyse technique + momentum ».
La version précédente n'avait aucune série de prix, donc aucune de ces mesures.

Le signal produit ici est **une règle fixe et publiée**, pas une intuition :
c'est exactement cette règle qui est ensuite mesurée par
:mod:`~osint_financial.backtest`. Un signal qu'on ne peut pas backtester n'est
pas un signal, c'est une opinion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .sources.prices import PriceSeries

HAUSSIER = "HAUSSIER"
BAISSIER = "BAISSIER"
NEUTRE = "NEUTRE"

SMA_FAST = 50
SMA_SLOW = 200
MOMENTUM_DAYS = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 75.0
RSI_OVERSOLD = 25.0

#: Historique minimal pour émettre un signal (la SMA lente doit exister).
MIN_HISTORY = SMA_SLOW + MOMENTUM_DAYS


def sma(values: Sequence[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(values: Sequence[float], period: int = RSI_PERIOD) -> float | None:
    """RSI de Wilder (moyenne lissée), sur les clôtures."""
    if len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for previous, current in zip(values[-period - 1 : -1], values[-period:]):
        delta = current - previous
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def classify(closes: Sequence[float]) -> str:
    """Règle directionnelle — **c'est elle qui est backtestée**.

    HAUSSIER : cours > SMA50 > SMA200, momentum 20 séances positif, RSI < 75.
    BAISSIER : cours < SMA50 < SMA200, momentum 20 séances négatif.
    NEUTRE   : tout le reste, y compris historique insuffisant.
    """
    if len(closes) < MIN_HISTORY:
        return NEUTRE
    fast = sma(closes, SMA_FAST)
    slow = sma(closes, SMA_SLOW)
    strength = rsi(closes)
    if fast is None or slow is None or strength is None:
        return NEUTRE

    past = closes[-1 - MOMENTUM_DAYS]
    if past <= 0:
        return NEUTRE
    momentum = (closes[-1] - past) / past
    price = closes[-1]

    if price > fast > slow and momentum > 0 and strength < RSI_OVERBOUGHT:
        return HAUSSIER
    if price < fast < slow and momentum < 0:
        return BAISSIER
    return NEUTRE


@dataclass
class TechnicalView:
    symbol: str
    signal: str = NEUTRE
    price: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    rsi_14: float | None = None
    momentum_20d_pct: float | None = None
    momentum_60d_pct: float | None = None
    volatility_annual_pct: float | None = None
    max_drawdown_pct: float | None = None
    distance_from_high_pct: float | None = None
    history_points: int = 0
    as_of: str | None = None
    source: str | None = None

    @property
    def has_signal(self) -> bool:
        return self.history_points >= MIN_HISTORY

    def to_dict(self) -> dict[str, object]:
        return {
            "signal": self.signal,
            "sma_50": self.sma_50,
            "sma_200": self.sma_200,
            "rsi_14": self.rsi_14,
            "momentum_20d_pct": self.momentum_20d_pct,
            "momentum_60d_pct": self.momentum_60d_pct,
            "volatility_annual_pct": self.volatility_annual_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "distance_from_high_pct": self.distance_from_high_pct,
            "history_points": self.history_points,
            "as_of": self.as_of,
            "source": self.source,
        }


def analyze(series: PriceSeries) -> TechnicalView:
    closes = series.closes
    view = TechnicalView(
        symbol=series.symbol,
        price=series.last,
        history_points=len(closes),
        as_of=series.last_date.isoformat(),
        source=series.source,
    )
    view.signal = classify(closes)
    view.sma_50 = _round(sma(closes, SMA_FAST))
    view.sma_200 = _round(sma(closes, SMA_SLOW))
    view.rsi_14 = _round(rsi(closes))
    view.momentum_20d_pct = _round(series.pct_change(MOMENTUM_DAYS))
    view.momentum_60d_pct = _round(series.pct_change(60))

    volatility = series.annualized_volatility()
    view.volatility_annual_pct = _round(volatility * 100.0) if volatility is not None else None
    drawdown = series.max_drawdown()
    view.max_drawdown_pct = _round(drawdown * 100.0) if drawdown is not None else None

    high = max(closes[-252:]) if closes else 0.0
    if high > 0:
        view.distance_from_high_pct = _round((series.last - high) / high * 100.0)
    return view


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)
