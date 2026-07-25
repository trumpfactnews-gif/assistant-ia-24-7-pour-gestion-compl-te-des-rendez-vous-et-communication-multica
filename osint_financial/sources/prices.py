"""Historique de cours quotidien — socle de l'analyse technique et du backtest.

Le pipeline d'origine ne récupérait qu'un prix instantané, ce qui rendait
structurellement impossibles les promesses « direction du prix (7j) »,
« momentum » et « backtesting ». On récupère ici une série quotidienne complète
(Yahoo, repli Stooq), validée point par point.

Sécurité : mêmes contraintes que le reste — hôtes sur allowlist, HTTPS, taille
plafonnée par :class:`~osint_financial.httpclient.HttpClient`. Les symboles
d'indices (``^GSPC``) ne passent pas par ``validate_ticker`` : ce sont des
constantes du code, jamais des entrées utilisateur, et ils sont encodés avant
insertion dans l'URL.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence
from urllib.parse import quote

from ..errors import DataUnavailable, OsintError
from ..httpclient import HttpClient
from ..logging_setup import get_logger

log = get_logger(__name__)

MIN_POINTS = 30
MAX_POINTS = 4000


@dataclass(frozen=True)
class PriceSeries:
    """Série de clôtures quotidiennes, triée par date croissante."""

    symbol: str
    dates: tuple[date, ...]
    closes: tuple[float, ...]
    source: str
    currency: str = "USD"

    def __post_init__(self) -> None:
        if len(self.dates) != len(self.closes):
            raise ValueError("dates et closes de longueurs différentes")

    def __len__(self) -> int:
        return len(self.closes)

    @property
    def last(self) -> float:
        return self.closes[-1]

    @property
    def last_date(self) -> date:
        return self.dates[-1]

    def window(self, n: int) -> tuple[float, ...]:
        return self.closes[-n:] if n > 0 else ()

    def pct_change(self, periods: int) -> float | None:
        """Variation en % sur ``periods`` séances."""
        if periods <= 0 or len(self.closes) <= periods:
            return None
        past = self.closes[-1 - periods]
        if past <= 0:
            return None
        return (self.closes[-1] - past) / past * 100.0

    def daily_returns(self) -> list[float]:
        out: list[float] = []
        for previous, current in zip(self.closes, self.closes[1:]):
            if previous > 0:
                out.append((current - previous) / previous)
        return out

    def annualized_volatility(self) -> float | None:
        """Écart-type annualisé des rendements quotidiens (252 séances)."""
        returns = self.daily_returns()[-252:]
        if len(returns) < 20:
            return None
        return statistics.pstdev(returns) * (252**0.5)

    def max_drawdown(self) -> float | None:
        """Perte maximale depuis un sommet, en fraction (0.25 = -25 %)."""
        if len(self.closes) < 2:
            return None
        peak = self.closes[0]
        worst = 0.0
        for close in self.closes:
            peak = max(peak, close)
            if peak > 0:
                worst = max(worst, (peak - close) / peak)
        return worst


def _clean_points(
    pairs: Sequence[tuple[date | None, float | None]]
) -> tuple[tuple[date, ...], tuple[float, ...]]:
    """Filtre les points invalides et déduplique par date (dernier gagnant)."""
    keep: dict[date, float] = {}
    for day, close in pairs:
        if day is None or close is None:
            continue
        if close != close or close <= 0 or close > 1e9:
            continue
        keep[day] = close
    ordered = sorted(keep.items())[-MAX_POINTS:]
    return tuple(d for d, _ in ordered), tuple(c for _, c in ordered)


def fetch_history(http: HttpClient, symbol: str, range_: str = "2y") -> PriceSeries:
    """Retourne l'historique quotidien, Yahoo d'abord puis Stooq."""
    errors: list[str] = []
    for provider in (_yahoo_history, _stooq_history):
        try:
            series = provider(http, symbol, range_)
            if len(series) < MIN_POINTS:
                raise DataUnavailable(f"série trop courte ({len(series)} points)")
            return series
        except OsintError as exc:
            errors.append(f"{provider.__name__}: {exc}")
            log.debug("historique indisponible — %s", exc)
    raise DataUnavailable(f"aucun historique pour {symbol} ({' | '.join(errors)})")


def _yahoo_history(http: HttpClient, symbol: str, range_: str) -> PriceSeries:
    if range_ not in {"6mo", "1y", "2y", "5y", "10y", "max"}:
        raise DataUnavailable(f"plage non supportée : {range_}")
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(symbol, safe='')}?range={range_}&interval=1d"
    )
    payload = http.get_json(url)
    if not isinstance(payload, dict):
        raise DataUnavailable("réponse Yahoo inattendue")
    chart = payload.get("chart")
    results = chart.get("result") if isinstance(chart, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise DataUnavailable("aucun résultat Yahoo")

    block = results[0]
    stamps = block.get("timestamp")
    indicators = block.get("indicators")
    quotes = indicators.get("quote") if isinstance(indicators, dict) else None
    if not isinstance(stamps, list) or not isinstance(quotes, list) or not quotes:
        raise DataUnavailable("séries Yahoo absentes")
    closes = quotes[0].get("close") if isinstance(quotes[0], dict) else None
    if not isinstance(closes, list):
        raise DataUnavailable("clôtures Yahoo absentes")

    pairs: list[tuple[date | None, float | None]] = []
    for stamp, close in zip(stamps, closes):
        day = None
        if isinstance(stamp, (int, float)) and 0 < stamp < 4e9:
            day = datetime.fromtimestamp(float(stamp), tz=timezone.utc).date()
        value = float(close) if isinstance(close, (int, float)) else None
        pairs.append((day, value))

    dates, values = _clean_points(pairs)
    meta = block.get("meta") if isinstance(block.get("meta"), dict) else {}
    currency = meta.get("currency")
    return PriceSeries(
        symbol=symbol,
        dates=dates,
        closes=values,
        source="yahoo",
        currency=currency if isinstance(currency, str) and len(currency) <= 8 else "USD",
    )


def _stooq_history(http: HttpClient, symbol: str, range_: str) -> PriceSeries:
    if symbol.startswith("^") or "=" in symbol:
        raise DataUnavailable("Stooq ne sert pas ce symbole")
    slug = quote(symbol.replace(".", "-").lower(), safe="")
    text = http.get_text(f"https://stooq.com/q/d/l/?s={slug}.us&i=d", accept="text/csv")
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < MIN_POINTS:
        raise DataUnavailable("CSV Stooq trop court")

    header = [h.strip().lower() for h in lines[0].split(",")]
    try:
        idx_date, idx_close = header.index("date"), header.index("close")
    except ValueError:
        raise DataUnavailable("colonnes Stooq inattendues") from None

    pairs: list[tuple[date | None, float | None]] = []
    for line in lines[1:]:
        row = line.split(",")
        if len(row) <= max(idx_date, idx_close):
            continue
        try:
            day = datetime.strptime(row[idx_date].strip(), "%Y-%m-%d").date()
        except ValueError:
            continue
        try:
            close = float(row[idx_close])
        except ValueError:
            continue
        pairs.append((day, close))

    dates, values = _clean_points(pairs)
    return PriceSeries(symbol=symbol, dates=dates, closes=values, source="stooq")
