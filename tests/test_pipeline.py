"""Test de bout en bout hors ligne : parsing → scoring → rapport → base."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import (  # noqa: E402
    FACTS,
    SUBMISSIONS,
    TICKER_MAP,
    FakeHttp,
    chart_payload,
    full_routes,
    trending_closes,
)

from osint_financial import metrics as metrics_mod, scoring  # noqa: E402
from osint_financial.database import DatabaseManager  # noqa: E402
from osint_financial.metrics import CollectOptions  # noqa: E402
from osint_financial.report import generate_html_report, write_atomic  # noqa: E402
from osint_financial.sources.sec import SecClient  # noqa: E402


class TestPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.http = FakeHttp(full_routes())
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
        self.assertAlmostEqual(self.data.current_ratio, 1.167, places=2)

    def test_flux_de_tresorerie_et_dette_nette(self) -> None:
        self.assertEqual(self.data.free_cash_flow, 109_000_000_000)
        self.assertEqual(self.data.net_debt, 60_000_000_000)
        self.assertIsNone(self.data.cash_runway_months)  # flux positif

    def test_croissance_annuelle(self) -> None:
        # 370 Md → 400 Md
        self.assertAlmostEqual(self.data.revenue_growth_yoy_pct, 8.11, places=1)
        self.assertIsNotNone(self.data.revenue_cagr_pct)
        self.assertIn("TCAC", self.data.revenue_growth_note or "")

    def test_dilution_negative_signale_des_rachats(self) -> None:
        # 15,8 Md → 15,4 Md actions
        self.assertLess(self.data.share_count_growth_pct, 0)

    def test_items_8k_lus(self) -> None:
        eight_k = [f for f in self.data.filings if f.form == "8-K"]
        self.assertEqual(eight_k[0].items, ("1.01", "9.01"))
        self.assertTrue(eight_k[0].is_alert)
        self.assertTrue(any(f.is_dilution for f in self.data.filings))
        self.assertTrue(self.data.alert_filings)
        self.assertTrue(self.data.dilution_filings)

    def test_form4_lu_et_agrege(self) -> None:
        insider = self.data.insider
        self.assertIsNotNone(insider)
        self.assertTrue(insider.available)
        self.assertEqual(len(insider.buys), 1)  # seul le code P compte
        self.assertEqual(len(insider.sells), 0)
        self.assertEqual(insider.buy_value, 1_500_000.0)
        self.assertEqual(insider.verdict(), "ACHAT_ISOLE")

    def test_technique_et_prix(self) -> None:
        view = self.data.technical
        self.assertIsNotNone(view)
        self.assertTrue(view.has_signal)
        self.assertEqual(view.signal, "HAUSSIER")  # série en tendance haussière
        self.assertIsNotNone(view.rsi_14)
        self.assertIsNotNone(self.data.price)
        self.assertIn("historique", self.data.price_source)

    def test_dcf_calcule(self) -> None:
        dcf = self.data.dcf
        self.assertTrue(dcf.available)
        self.assertGreater(dcf.value_per_share, 0)
        self.assertLessEqual(dcf.low_per_share, dcf.value_per_share)
        self.assertGreaterEqual(dcf.high_per_share, dcf.value_per_share)
        self.assertIsNotNone(dcf.assumptions)
        self.assertIsNotNone(dcf.upside_pct)

    def test_colonnes_inegales_tolerees(self) -> None:
        self.assertEqual(len(self.data.filings), 6)
        self.assertIsNone(self.data.filings[2].filed_at)  # « pas-une-date »

    def test_url_de_filing_refusee_si_document_suspect(self) -> None:
        traversal = self.data.filings[1]
        self.assertEqual(traversal.primary_document, "../../../etc/passwd")
        self.assertIsNone(traversal.url)
        self.assertTrue(self.data.filings[0].url.startswith("https://www.sec.gov/Archives/"))

    def test_scoring_complet(self) -> None:
        result = scoring.compute(self.data, macro_score=62.0)
        self.assertGreaterEqual(result.confidence, 0.9)
        self.assertNotEqual(result.recommendation, "INSUFFICIENT_DATA")
        self.assertIsNotNone(result.resilience_score)
        self.assertEqual(
            set(result.resilience_parts), {"fondamentaux", "position_marche", "macro"}
        )
        self.assertEqual(result.resilience_parts["macro"], 62.0)

    def test_rapport_et_persistance(self) -> None:
        result = scoring.compute(self.data)
        html = generate_html_report(self.data, result)
        self.assertIn("Apple Inc.", html)
        self.assertIn("Valorisation par les flux", html)
        self.assertIn("Transactions d'initiés", html)

        out = Path("/tmp/osint-pipeline/AAPL/AAPL_report.html")
        write_atomic(out, html)
        self.assertTrue(out.is_file())
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(out.parent.glob(".tmp-*")))

        db = DatabaseManager(Path("/tmp/osint-pipeline/db.sqlite"))
        row_id = db.save_analysis(
            "AAPL", self.data.to_dict(), result.to_dict(),
            company_name=self.data.company_name, cik=self.data.cik,
            price=self.data.price, currency=self.data.currency,
        )
        self.assertGreater(row_id, 0)
        self.assertEqual(db.list_analyses("AAPL")[0].recommendation, result.recommendation)


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
        self.assertIsNone(data.technical)
        self.assertTrue(any("cotation indisponible" in w for w in data.warnings))
        result = scoring.compute(data)
        self.assertLess(result.confidence, 1.0)
        self.assertGreater(result.confidence, 0.0)

    def test_sec_indisponible(self) -> None:
        http = FakeHttp({"finance/chart": chart_payload(trending_closes())})
        data = metrics_mod.collect(http, "AAPL", SecClient(http))  # type: ignore[arg-type]
        result = scoring.compute(data)
        self.assertEqual(result.recommendation, "INSUFFICIENT_DATA")
        self.assertTrue(any("SEC indisponible" in w for w in data.warnings))

    def test_prix_nul_ne_plante_pas(self) -> None:
        routes = full_routes()
        routes["range=1d"] = {"chart": {"result": [{"meta": {"regularMarketPrice": 0}}]}}
        routes["finance/chart"] = {"chart": {"result": [{"meta": {"regularMarketPrice": 0}}]}}
        http = FakeHttp(routes)
        data = metrics_mod.collect(http, "AAPL", SecClient(http))  # type: ignore[arg-type]
        self.assertIsNone(data.price)
        self.assertIsNone(data.pe_ratio)

    def test_form4_illisible_non_fatal(self) -> None:
        routes = full_routes()
        routes["form4.xml"] = b"<ownershipDocument><nonDerivativeTable>"  # XML tronqué
        http = FakeHttp(routes)
        data = metrics_mod.collect(http, "AAPL", SecClient(http))  # type: ignore[arg-type]
        self.assertIsNotNone(data.insider)
        self.assertFalse(data.insider.available)
        self.assertEqual(data.insider.forms_failed, 1)

    def test_options_desactivent_les_appels(self) -> None:
        http = FakeHttp(full_routes())
        options = CollectOptions(history=False, insiders=False, macro=False)
        data = metrics_mod.collect(http, "AAPL", SecClient(http), options)  # type: ignore[arg-type]
        self.assertIsNone(data.technical)
        self.assertIsNone(data.insider)
        self.assertFalse(any("form4" in call for call in http.calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
