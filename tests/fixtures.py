"""Jeux de données figés et double du client HTTP, pour des tests hors ligne.

Certaines charges utiles sont volontairement malformées (colonnes de longueurs
inégales, valeurs non numériques, unités inattendues, nom de document tentant
une traversée) : le pipeline doit les absorber sans exception.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta

from osint_financial.errors import HttpError

TICKER_MAP = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}

SUBMISSIONS = {
    "sicDescription": "Electronic Computers",
    "filings": {
        "recent": {
            "form": ["8-K", "10-Q", "4", "SC 13D", "8-K", "INVALIDFORM"],
            "filingDate": ["2026-07-01", "2026-05-02", "pas-une-date"],  # colonne plus courte
            "accessionNumber": [
                "0000320193-26-000064",
                "0000320193-26-000052",
                "0000320193-26-000041",
                "0000320193-26-000030",
                "0000320193-26-000021",
                "0000320193-26-000010",
            ],
            "primaryDocument": [
                "aapl-8k.htm",
                "../../../etc/passwd",  # tentative de traversée
                "form4.xml",
                "sc13d.htm",
                "aapl-8k-2.htm",
                "x.htm",
            ],
            "primaryDocDescription": ["Item 8.01 Other Events"],
            "items": ["1.01,9.01", "", "", "", "3.02", ""],
        }
    },
}


def _usd(entries):
    return {"units": {"USD": entries}}


FACTS = {
    "facts": {
        "us-gaap": {
            "Assets": _usd([
                {"val": 340_000_000_000, "end": "2024-09-28", "form": "10-K"},
                {"val": 350_000_000_000, "end": "2025-09-27", "form": "10-K"},
            ]),
            "Liabilities": _usd([
                {"val": 280_000_000_000, "end": "2024-09-28", "form": "10-K"},
                {"val": 290_000_000_000, "end": "2025-09-27", "form": "10-K"},
            ]),
            "AssetsCurrent": _usd([{"val": 140_000_000_000, "end": "2025-09-27", "form": "10-K"}]),
            "LiabilitiesCurrent": _usd([
                {"val": 120_000_000_000, "end": "2025-09-27", "form": "10-K"}
            ]),
            "Revenues": _usd([
                {"val": 320_000_000_000, "end": "2022-09-24", "form": "10-K"},
                {"val": 350_000_000_000, "end": "2023-09-30", "form": "10-K"},
                {"val": 370_000_000_000, "end": "2024-09-28", "form": "10-K"},
                {"val": 400_000_000_000, "end": "2025-09-27", "form": "10-K"},
                {"val": "corrompu", "end": "2025-12-31", "form": "10-Q"},  # ignoré
            ]),
            "NetIncomeLoss": _usd([{"val": 100_000_000_000, "end": "2025-09-27", "form": "10-K"}]),
            "EarningsPerShareDiluted": {
                "units": {
                    "USD/shares": [{"val": 6.5, "end": "2025-09-27", "form": "10-K"}],
                    "pure": [{"val": 999.0, "end": "2026-01-01", "form": "10-K"}],  # unité ignorée
                }
            },
            "CashAndCashEquivalentsAtCarryingValue": _usd([
                {"val": 30_000_000_000, "end": "2025-09-27", "form": "10-K"}
            ]),
            "LongTermDebt": _usd([{"val": 90_000_000_000, "end": "2025-09-27", "form": "10-K"}]),
            "NetCashProvidedByUsedInOperatingActivities": _usd([
                {"val": 110_000_000_000, "end": "2024-09-28", "form": "10-K"},
                {"val": 120_000_000_000, "end": "2025-09-27", "form": "10-K"},
            ]),
            "PaymentsToAcquirePropertyPlantAndEquipment": _usd([
                {"val": 11_000_000_000, "end": "2025-09-27", "form": "10-K"}
            ]),
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {
                    "shares": [
                        {"val": 15_800_000_000, "end": "2024-09-28", "form": "10-K"},
                        {"val": 15_400_000_000, "end": "2025-09-27", "form": "10-K"},
                    ]
                }
            },
        }
    }
}

FORM4_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ownershipDocument>
  <issuer><issuerCik>0000320193</issuerCik></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isOfficer>1</isOfficer><officerTitle>Chief Financial Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-06-15</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>10000</value></transactionShares>
        <transactionPricePerShare><value>150.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-06-10</value></transactionDate>
      <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>50000</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""

#: Document hostile : entité externe pointant vers un fichier local (XXE).
FORM4_XXE = b"""<?xml version="1.0"?>
<!DOCTYPE ownershipDocument [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<ownershipDocument><reportingOwner>&xxe;</reportingOwner></ownershipDocument>
"""

#: Document hostile : expansion récursive d'entités (« billion laughs »).
FORM4_BOMB = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<ownershipDocument>&lol2;</ownershipDocument>
"""


def trending_closes(
    count: int = 600,
    drift: float = 0.0012,
    start: float = 100.0,
    amplitude: float = 2.0,
    period: float = 2.5,
) -> list[float]:
    """Série déterministe : tendance exponentielle + oscillation courte.

    L'oscillation est plus rapide que la fenêtre de momentum : elle produit de
    vraies séances de baisse (donc un RSI réaliste, pas saturé à 100) tout en
    s'annulant sur 20 séances, si bien que le momentum garde le signe de la
    tendance. Le test porte ainsi sur la règle, pas sur la phase du sinus.
    """
    return [
        round(start * math.exp(drift * i) + amplitude * math.sin(i / period), 4)
        for i in range(count)
    ]


def declining_closes(count: int = 600) -> list[float]:
    """Symétrique baissier de :func:`trending_closes`."""
    return trending_closes(count=count, drift=-0.0012, start=300.0)


def chart_payload(closes: list[float], end: date | None = None) -> dict:
    """Réponse Yahoo ``/v8/finance/chart`` pour une série de clôtures."""
    end = end or date(2026, 7, 24)
    epoch = date(1970, 1, 1)
    stamps = [
        (end - timedelta(days=len(closes) - 1 - i) - epoch).days * 86400
        for i in range(len(closes))
    ]
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": closes[-1],
                        "regularMarketTime": stamps[-1],
                        "currency": "USD",
                        "chartPreviousClose": closes[-2] if len(closes) > 1 else closes[-1],
                    },
                    "timestamp": stamps,
                    "indicators": {"quote": [{"close": closes}]},
                }
            ]
        }
    }


class FakeHttp:
    """Double de ``HttpClient`` : sert des réponses figées, sinon échoue.

    Les routes sont testées dans l'ordre d'insertion : placer les motifs les
    plus spécifiques en premier.
    """

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def _match(self, url: str):
        self.calls.append(url)
        for fragment, payload in self.routes.items():
            if fragment in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise HttpError(f"route non simulée : {url}")

    def get_json(self, url: str):
        payload = self._match(url)
        if isinstance(payload, (bytes, str)):
            raise HttpError("réponse non JSON")
        return payload

    def get_text(self, url: str, accept: str = "text/plain") -> str:
        payload = self._match(url)
        if isinstance(payload, str):
            return payload
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return json.dumps(payload)

    def get_bytes(self, url: str, accept: str = "application/json") -> bytes:
        payload = self._match(url)
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, str):
            return payload.encode("utf-8")
        return json.dumps(payload).encode("utf-8")

    def post_json(self, url: str, payload: dict, headers: dict | None = None):
        return self._match(url)


def full_routes(closes: list[float] | None = None) -> dict[str, object]:
    """Toutes les sources disponibles et cohérentes."""
    closes = closes if closes is not None else trending_closes()
    history = chart_payload(closes)
    return {
        "company_tickers.json": TICKER_MAP,
        "submissions/CIK": SUBMISSIONS,
        "companyfacts/CIK": FACTS,
        "form4.xml": FORM4_XML,
        "range=1d": chart_payload(closes[-2:]),
        "finance/chart": history,
    }
