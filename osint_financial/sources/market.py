"""Prix de marché : Yahoo Finance (API chart publique) avec repli Stooq.

L'original importait ``yfinance``, qui *scrape* Yahoo : dépendance lourde,
sortie non typée, et rupture silencieuse à chaque changement de page. Ici on
appelle directement l'endpoint JSON, on valide le type de chaque champ, et on
bascule sur Stooq si Yahoo refuse le trafic.

Le prix seul ne suffit pas : on retourne aussi la devise et l'horodatage, car
un prix sans date est inutilisable pour une décision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..errors import DataUnavailable, OsintError
from ..httpclient import HttpClient
from ..logging_setup import get_logger
from ..validation import validate_ticker

log = get_logger(__name__)


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: float
    currency: str
    as_of: datetime | None
    source: str
    previous_close: float | None = None

    @property
    def daily_change_pct(self) -> float | None:
        if self.previous_close and self.previous_close > 0:
            return (self.price - self.previous_close) / self.previous_close * 100.0
        return None


def _positive_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result <= 0 or result > 1e9:
        return None
    return result


def fetch_quote(http: HttpClient, ticker: str) -> Quote:
    """Retourne la cotation courante, ou lève :class:`DataUnavailable`."""
    ticker = validate_ticker(ticker)
    errors: list[str] = []

    for provider in (_yahoo_quote, _stooq_quote):
        try:
            return provider(http, ticker)
        except OsintError as exc:
            errors.append(f"{provider.__name__}: {exc}")
            log.debug("source de prix en échec — %s", exc)

    raise DataUnavailable(f"aucune cotation pour {ticker} ({' | '.join(errors)})")


def _yahoo_quote(http: HttpClient, ticker: str) -> Quote:
    payload = http.get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
    )
    if not isinstance(payload, dict):
        raise DataUnavailable("réponse Yahoo inattendue")
    chart = payload.get("chart")
    results = chart.get("result") if isinstance(chart, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise DataUnavailable("aucun résultat Yahoo")
    meta = results[0].get("meta")
    if not isinstance(meta, dict):
        raise DataUnavailable("métadonnées Yahoo absentes")

    price = _positive_float(meta.get("regularMarketPrice"))
    if price is None:
        raise DataUnavailable("prix Yahoo absent ou invalide")

    stamp = meta.get("regularMarketTime")
    as_of = None
    if isinstance(stamp, (int, float)) and 0 < stamp < 4e9:
        as_of = datetime.fromtimestamp(float(stamp), tz=timezone.utc)

    currency = meta.get("currency")
    return Quote(
        ticker=ticker,
        price=price,
        currency=currency if isinstance(currency, str) and len(currency) <= 8 else "USD",
        as_of=as_of,
        source="yahoo",
        previous_close=_positive_float(meta.get("chartPreviousClose")),
    )


def _stooq_quote(http: HttpClient, ticker: str) -> Quote:
    symbol = ticker.replace(".", "-").lower()
    text = http.get_text(
        f"https://stooq.com/q/l/?s={symbol}.us&f=sd2t2ohlcv&h&e=csv", accept="text/csv"
    )
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise DataUnavailable("CSV Stooq vide")
    header = [h.strip().lower() for h in lines[0].split(",")]
    row = [v.strip() for v in lines[1].split(",")]
    if len(row) != len(header):
        raise DataUnavailable("CSV Stooq malformé")
    record = dict(zip(header, row))

    price = _positive_float(record.get("close"))
    if price is None:
        raise DataUnavailable("clôture Stooq indisponible")

    as_of = None
    try:
        as_of = datetime.strptime(
            f"{record.get('date', '')} {record.get('time', '00:00:00')}", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    return Quote(ticker=ticker, price=price, currency="USD", as_of=as_of, source="stooq")
