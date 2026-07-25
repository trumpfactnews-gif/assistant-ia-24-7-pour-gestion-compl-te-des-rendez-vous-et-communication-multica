"""Contexte de marché — le volet « macro » du score de résilience.

Le guide annonçait « Score de résilience : 50 % fondamentaux + 25 % position
marché + 25 % macro », sans qu'aucune source ne renseigne les deux derniers
termes. Plutôt que d'inventer un indicateur géopolitique invérifiable, on
mesure le **régime de marché** à partir de séries publiques observables :

* S&P 500 (``^GSPC``) — tendance générale, position vs moyenne 200 séances ;
* VIX (``^VIX``) — volatilité implicite, c'est-à-dire le stress anticipé ;
* rendement du 10 ans US (``^TNX``) — direction des taux, qui conditionne les
  multiples de valorisation.

Ce sont des faits mesurables, pas des opinions. Ce que le guide appelait
« Iran/Chine/UE impact sur ce secteur » n'a pas de source exploitable et reste
hors périmètre : c'est écrit dans le rapport plutôt que simulé.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import OsintError
from .httpclient import HttpClient
from .logging_setup import get_logger
from .sources import prices
from .technical import sma

log = get_logger(__name__)

INDEX_SYMBOL = "^GSPC"
VIX_SYMBOL = "^VIX"
RATES_SYMBOL = "^TNX"

VIX_CALM = 15.0
VIX_STRESS = 25.0

FAVORABLE = "FAVORABLE"
NEUTRE = "NEUTRE"
DEFAVORABLE = "DEFAVORABLE"


@dataclass
class MarketRegime:
    regime: str = NEUTRE
    score: float = 50.0
    index_above_sma200: bool | None = None
    index_momentum_60d_pct: float | None = None
    vix_level: float | None = None
    vix_state: str | None = None
    rates_change_60d_pct: float | None = None
    observations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.index_above_sma200 is not None or self.vix_level is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "regime": self.regime,
            "score": self.score,
            "index_above_sma200": self.index_above_sma200,
            "index_momentum_60d_pct": self.index_momentum_60d_pct,
            "vix_level": self.vix_level,
            "vix_state": self.vix_state,
            "rates_change_60d_pct": self.rates_change_60d_pct,
            "observations": self.observations,
            "warnings": self.warnings,
        }


def assess(http: HttpClient, cache: dict[str, prices.PriceSeries] | None = None) -> MarketRegime:
    """Évalue le régime de marché. Chaque source manquante est signalée."""
    regime = MarketRegime()
    cache = cache if cache is not None else {}

    def series(symbol: str) -> prices.PriceSeries | None:
        if symbol in cache:
            return cache[symbol]
        try:
            fetched = prices.fetch_history(http, symbol, range_="2y")
        except OsintError as exc:
            regime.warnings.append(f"{symbol} indisponible : {exc}")
            return None
        cache[symbol] = fetched
        return fetched

    points = 50.0

    index = series(INDEX_SYMBOL)
    if index is not None:
        average = sma(index.closes, 200)
        if average is not None:
            regime.index_above_sma200 = index.last > average
            if regime.index_above_sma200:
                points += 12
                regime.observations.append("S&P 500 au-dessus de sa moyenne 200 séances")
            else:
                points -= 12
                regime.observations.append("S&P 500 sous sa moyenne 200 séances")
        momentum = index.pct_change(60)
        if momentum is not None:
            regime.index_momentum_60d_pct = round(momentum, 2)
            if momentum > 3:
                points += 6
            elif momentum < -3:
                points -= 6

    vix = series(VIX_SYMBOL)
    if vix is not None:
        regime.vix_level = round(vix.last, 2)
        if vix.last < VIX_CALM:
            regime.vix_state = "calme"
            points += 8
            regime.observations.append(f"VIX à {vix.last:.1f} — volatilité anticipée faible")
        elif vix.last > VIX_STRESS:
            regime.vix_state = "stress"
            points -= 14
            regime.observations.append(f"VIX à {vix.last:.1f} — stress de marché")
        else:
            regime.vix_state = "normal"

    rates = series(RATES_SYMBOL)
    if rates is not None:
        change = rates.pct_change(60)
        if change is not None:
            regime.rates_change_60d_pct = round(change, 2)
            # Une hausse rapide des taux longs comprime les multiples.
            if change > 10:
                points -= 8
                regime.observations.append(
                    f"taux 10 ans US en hausse de {change:.1f} % sur 60 séances"
                )
            elif change < -10:
                points += 5
                regime.observations.append(
                    f"taux 10 ans US en baisse de {abs(change):.1f} % sur 60 séances"
                )

    regime.score = round(max(0.0, min(100.0, points)), 1)
    if regime.score >= 60:
        regime.regime = FAVORABLE
    elif regime.score <= 40:
        regime.regime = DEFAVORABLE
    else:
        regime.regime = NEUTRE

    if not regime.available:
        regime.warnings.append("aucune série de marché disponible : contexte non évalué")
    return regime
