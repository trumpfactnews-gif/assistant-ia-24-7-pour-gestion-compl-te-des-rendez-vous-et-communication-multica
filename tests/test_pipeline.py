"""Test de bout en bout hors ligne : parsing SEC/marché → scoring → rapport → base.

Le client HTTP est remplacé par un double qui sert des charges utiles figées,
dont certaines volontairement malformées (colonnes de longueurs inégales,
valeurs non numériques, unités inattendues) : l'original supposait des
structures parfaites et levait ``IndexError``/``TypeError`` dessus.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osint_financial import metrics as metrics_mod, scoring  # noqa: E402
from osint_financial.database import DatabaseManager  # noqa: E402
from osint_financial.errors import HttpError  # noqa: E402
from osint_financial.report import generate_html_report, write_atomic  # noqa: E402
from osint_financial.sources.sec import SecClient  # noqa: E402

TICKER_MAP = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}

SUBMISSIONS = {
    "sicDescription": "Electronic Computers",
    "filings": {
        "recent": {
            "form": ["8-K", "10-Q", "4", "SC 13D", "INVALIDFORM"],
            "filingDate": ["2026-07-01", "2026-05-02", "pas-une-date"],  # colonne plus courte
            "accessionNumber": [
                "0000320193-26-000064",
                "0000320193-26-000052",
                "0000320193-26-000041",
                "0000320193-26-000030",
                "0000320193-26-000021",
            ],
            "primaryDocument": [
                "aapl-8k.htm",
                "../../../etc/passwd",  # tentative de traversée dans l'URL
                "form4.xml",
                "sc13d.htm",
                "x.htm",
            ],
            "primaryDocDescription": ["Item 8.01 Other Events"],
        }
    },
}

FACTS = {
    "facts": {
        "us-gaap": {
            "Assets": {"units": {"USD": [
                {"val": 350_000_000_000, "end": "2025-09-27", "form": "10-K"},
                {"val": 340_000_000_000, "end": "2024-09-28", "form": "10-K"},
            ]}},
            "Liabilities": {"units": {"USD": [
                {"val": 290_000_000_000, "end": "2025-09-27", "form": "10-K"},
            ]}},
            "Revenues": {"units": {"USD": [
                {"val": 400_000_000_000, "end": "2025-09-27", "form": "10-K"},
                {"val": "corrompu", "end": "2025-12-31", "form": "10-Q"},  # ignoré
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                {"val": 100_000_000_000, "end": "2025-09-27", "form": "10-K"},
            ]}},
            "EarningsPerShareDiluted": {"units": {
                "USD/shares": [{"val": 6.5, "end": "2025-09-27", "form": "10-K"}],
                "pure": [{"val": 999.0, "end": "2026-01-01", "form": "10-K"}],  # unité ignorée
            }},
            "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [
                {"val": 30_000_000_000, "end": "2025-09-27", "form": "10-K"},
            ]}},
            "LongTermDebt": {"units": {"USD": [
                {"val": 90_000_000_000, "end": "2025-09-27", "form": "10-K"},
            ]}},
        }
    }
}

QUOTE = {
    "chart": {
        "result": [{"meta": {
            "regularMarketPrice": 150.0,
            "regularMarketTime": 1_785_000_000,
            "currency": "USD",
            "chartPreviousClose": 148.0,
        }}]
    }
}


class FakeHttp:
    """Double de :class:`HttpClient` : sert des réponses figées, sinon échoue."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def _match(self, url: str):
        self.calls.append(url)
        for fragment, payload in self.routes.items():
            if fragment in url:
                return payload
        raise HttpError(f"route non simulée : {url}")

    def get_json(self, url: str):
        return self._match(url)

    def get_text(self, url: str, accept: str = "text/plain") -> str:
        payload = self._match(url)
        return payload if isinstance(payload, str) else json.dumps(payload)


def make_http() -> FakeHttp:
    return FakeHttp(
        {
            "company_tickers.json": TICKER_MAP,
            "submissions/CIK": SUBMISSIONS,
            "companyfacts/CIK": FACTS,
            "finance/chart": QUOTE,
        }
    )


class TestPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.http = make_http()
        self.sec = SecClient(self.http)  # type: ignore[arg-type]
        self.data = metrics_mod.collect(self.http, "AAPL", self.sec)  # type: ignore[arg-type]

    def test_identite_et_secteur(self) -> None:
        self.assertEqual(self.data.company_name, "Apple Inc.")
        self.assertEqual(self.data.cik, "0000320193")
        self.assertEqual(self.data.sector, "technology")
        self.assertEqual(self.data.pe_sector, 28.0)

    def test_faits_xbrl(self) -> None:
        self.assertEqual(self.data.assets, 350_000_000_000)
        self.assertEqual(self.data.eps, 6.5)  # l'unité « pure » à 999 est ignorée
        self.assertEqual(self.data.revenue, 400_000_000_000)  # « corrompu » ignoré
        self.assertAlmostEqual(self.data.debt_to_assets, 0.8286, places=3)
        self.assertAlmostEqual(self.data.profit_margin, 0.25, places=3)

    def test_derives_de_prix(self) -> None:
        self.assertEqual(self.data.price, 150.0)
        self.assertAlmostEqual(self.data.pe_ratio, 150.0 / 6.5, places=3)
        self.assertEqual(self.data.target_price_pe, 182.0)
        self.assertAlmostEqual(self.data.upside_pe_pct, 21.33, places=1)

    def test_colonnes_inegales_tolerees(self) -> None:
        # 5 formulaires, 3 dates : aucune exception, dates manquantes = None.
        self.assertEqual(len(self.data.filings), 5)
        self.assertIsNone(self.data.filings[2].filed_at)  # « pas-une-date »

    def test_url_de_filing_refusee_si_document_suspect(self) -> None:
        traversal = self.data.filings[1]
        self.assertEqual(traversal.primary_document, "../../../etc/passwd")
        self.assertIsNone(traversal.url)  # aucune URL construite
        self.assertIsNotNone(self.data.filings[0].url)
        self.assertTrue(self.data.filings[0].url.startswith("https://www.sec.gov/Archives/"))

    def test_scoring_complet(self) -> None:
        result = scoring.compute(self.data)
        self.assertEqual(result.confidence, 1.0)
        self.assertNotEqual(result.recommendation, "INSUFFICIENT_DATA")
        self.assertTrue(result.risk_factors)  # levier > 60 %
        self.assertFalse(result.missing_inputs)

    def test_rapport_et_persistance(self) -> None:
        result = scoring.compute(self.data)
        html = generate_html_report(self.data, result)
        self.assertIn("Apple Inc.", html)
        self.assertIn("0000320193", html)

        out = Path("/tmp/osint-pipeline/AAPL/AAPL_report.html")
        write_atomic(out, html)
        self.assertTrue(out.is_file())
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(out.parent.glob(".tmp-*")))  # aucun résidu

        db = DatabaseManager(Path("/tmp/osint-pipeline/db.sqlite"))
        row_id = db.save_analysis(
            "AAPL", self.data.to_dict(), result.to_dict(),
            company_name=self.data.company_name, cik=self.data.cik,
            price=self.data.price, currency=self.data.currency,
        )
        self.assertGreater(row_id, 0)
        rows = db.list_analyses("AAPL")
        self.assertEqual(rows[0].recommendation, result.recommendation)


class TestPartialFailures(unittest.TestCase):
    """Une source en panne ne doit ni planter ni fabriquer de fausse certitude."""

    def test_marche_indisponible(self) -> None:
        http = FakeHttp({
            "company_tickers.json": TICKER_MAP,
            "submissions/CIK": SUBMISSIONS,
            "companyfacts/CIK": FACTS,
        })
        data = metrics_mod.collect(http, "AAPL", SecClient(http))  # type: ignore[arg-type]
        self.assertIsNone(data.price)
        self.assertIsNone(data.pe_ratio)
        self.assertTrue(any("cotation indisponible" in w for w in data.warnings))
        result = scoring.compute(data)
        self.assertLess(result.confidence, 1.0)
        self.assertGreater(result.confidence, 0.0)

    def test_sec_indisponible(self) -> None:
        http = FakeHttp({"finance/chart": QUOTE})
        data = metrics_mod.collect(http, "AAPL", SecClient(http))  # type: ignore[arg-type]
        result = scoring.compute(data)
        self.assertEqual(result.recommendation, "INSUFFICIENT_DATA")
        self.assertTrue(any("SEC indisponible" in w for w in data.warnings))

    def test_prix_nul_ne_plante_pas(self) -> None:
        broken = {"chart": {"result": [{"meta": {"regularMarketPrice": 0}}]}}
        http = FakeHttp({
            "company_tickers.json": TICKER_MAP,
            "submissions/CIK": SUBMISSIONS,
            "companyfacts/CIK": FACTS,
            "finance/chart": broken,
        })
        data = metrics_mod.collect(http, "AAPL", SecClient(http))  # type: ignore[arg-type]
        self.assertIsNone(data.price)  # 0 rejeté comme prix invalide
        self.assertIsNone(data.pe_ratio)


if __name__ == "__main__":
    unittest.main(verbosity=2)
