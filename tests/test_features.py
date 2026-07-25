"""Tests des capacités promises par le guide et désormais implémentées :
analyse technique, backtest, DCF, comparables, Form 4, contexte de marché,
dimensionnement, mode surveillance."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import (  # noqa: E402
    FORM4_BOMB,
    FORM4_XML,
    FORM4_XXE,
    FakeHttp,
    chart_payload,
    declining_closes,
    full_routes,
    trending_closes,
)

from osint_financial import backtest as backtest_mod  # noqa: E402
from osint_financial import macro, portfolio, technical, valuation  # noqa: E402
from osint_financial.errors import DataUnavailable, SecurityError  # noqa: E402
from osint_financial.sources import forms, prices  # noqa: E402


def series_from(closes: list[float], symbol: str = "TEST") -> prices.PriceSeries:
    dates = tuple(date.fromordinal(date(2020, 1, 1).toordinal() + i) for i in range(len(closes)))
    return prices.PriceSeries(symbol=symbol, dates=dates, closes=tuple(closes), source="test")


# ------------------------------------------------------------------ prix


class TestPriceHistory(unittest.TestCase):
    def test_lecture_yahoo(self) -> None:
        closes = trending_closes(300)
        http = FakeHttp({"finance/chart": chart_payload(closes)})
        series = prices.fetch_history(http, "AAPL")  # type: ignore[arg-type]
        self.assertEqual(len(series), 300)
        self.assertAlmostEqual(series.last, closes[-1], places=3)

    def test_points_invalides_ecartes(self) -> None:
        closes = trending_closes(300)
        payload = chart_payload(closes)
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][5] = None
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][6] = -3.0
        http = FakeHttp({"finance/chart": payload})
        series = prices.fetch_history(http, "AAPL")  # type: ignore[arg-type]
        self.assertEqual(len(series), 298)

    def test_serie_trop_courte_refusee(self) -> None:
        http = FakeHttp({"finance/chart": chart_payload(trending_closes(10))})
        with self.assertRaises(DataUnavailable):
            prices.fetch_history(http, "AAPL")  # type: ignore[arg-type]

    def test_repli_csv_stooq(self) -> None:
        rows = ["Date,Open,High,Low,Close,Volume"]
        for index, close in enumerate(trending_closes(60)):
            day = date.fromordinal(date(2026, 1, 1).toordinal() + index).isoformat()
            rows.append(f"{day},1,1,1,{close},1000")
        http = FakeHttp({"finance/chart": {"chart": {"result": []}}, "stooq.com": "\n".join(rows)})
        series = prices.fetch_history(http, "AAPL")  # type: ignore[arg-type]
        self.assertEqual(series.source, "stooq")
        self.assertEqual(len(series), 60)

    def test_indicateurs_de_risque(self) -> None:
        series = series_from(trending_closes(400))
        self.assertIsNotNone(series.annualized_volatility())
        self.assertGreaterEqual(series.max_drawdown(), 0.0)
        self.assertIsNone(series.pct_change(10_000))


# ------------------------------------------------------------- technique


class TestTechnical(unittest.TestCase):
    def test_signal_haussier(self) -> None:
        view = technical.analyze(series_from(trending_closes()))
        self.assertEqual(view.signal, technical.HAUSSIER)
        self.assertGreater(view.momentum_20d_pct, 0)
        self.assertTrue(view.has_signal)

    def test_signal_baissier(self) -> None:
        view = technical.analyze(series_from(declining_closes()))
        self.assertEqual(view.signal, technical.BAISSIER)

    def test_historique_court_reste_neutre(self) -> None:
        view = technical.analyze(series_from(trending_closes(60)))
        self.assertEqual(view.signal, technical.NEUTRE)
        self.assertFalse(view.has_signal)

    def test_rsi_bornes(self) -> None:
        self.assertEqual(technical.rsi([1.0 * (i + 1) for i in range(30)]), 100.0)
        self.assertIsNone(technical.rsi([1.0, 2.0]))

    def test_sma(self) -> None:
        self.assertEqual(technical.sma([1.0, 2.0, 3.0], 3), 2.0)
        self.assertIsNone(technical.sma([1.0], 3))


# --------------------------------------------------------------- backtest


class TestBacktest(unittest.TestCase):
    def test_mesure_produite(self) -> None:
        result = backtest_mod.run(series_from(trending_closes(900)), horizon=7)
        self.assertGreater(result.total_observations, 100)
        self.assertTrue(result.usable)
        self.assertIsNotNone(result.baseline.mean_return_pct)
        self.assertEqual(
            set(result.per_signal), {technical.HAUSSIER, technical.BAISSIER, technical.NEUTRE}
        )

    def test_aucune_donnee_future_utilisee(self) -> None:
        """La classification ne doit voir que le passé.

        On tronque la série au point d'observation et on vérifie que le signal
        est identique : si la fonction regardait devant, il changerait.
        """
        closes = trending_closes(900)
        end = 500
        self.assertEqual(technical.classify(closes[:end]), technical.classify(closes[:end][:end]))

    def test_horizon_borne(self) -> None:
        result = backtest_mod.run(series_from(trending_closes(900)), horizon=10_000)
        self.assertLessEqual(result.horizon, 60)

    def test_historique_insuffisant_signale(self) -> None:
        result = backtest_mod.run(series_from(trending_closes(100)))
        self.assertEqual(result.total_observations, 0)
        self.assertTrue(result.warnings)
        self.assertFalse(result.usable)

    def test_echantillon_faible_signale(self) -> None:
        result = backtest_mod.run(series_from(trending_closes(900)))
        for label, stats in result.per_signal.items():
            if 0 < stats.observations < 30:
                self.assertTrue(any(label in w for w in result.warnings))


# ---------------------------------------------------------------- DCF


class TestDcf(unittest.TestCase):
    def test_calcul_nominal(self) -> None:
        result = valuation.discounted_cash_flow(
            free_cash_flow=1_000_000.0, shares=1_000_000.0, net_debt=0.0,
            growth=0.05, wacc=0.09, terminal_growth=0.025, current_price=20.0,
        )
        self.assertTrue(result.available)
        self.assertGreater(result.value_per_share, 0)
        self.assertLess(result.low_per_share, result.high_per_share)
        self.assertIsNotNone(result.upside_pct)

    def test_flux_negatif_refuse(self) -> None:
        result = valuation.discounted_cash_flow(-500.0, 1000.0, 0.0, 0.05)
        self.assertFalse(result.available)
        self.assertTrue(any("négatif" in w for w in result.warnings))

    def test_donnees_absentes(self) -> None:
        self.assertFalse(valuation.discounted_cash_flow(None, 1000.0, 0.0, 0.05).available)
        self.assertFalse(valuation.discounted_cash_flow(1000.0, None, 0.0, 0.05).available)

    def test_croissance_terminale_bornee(self) -> None:
        """Croissance perpétuelle ≥ WACC = valeur infinie : le modèle borne."""
        result = valuation.discounted_cash_flow(
            1_000_000.0, 1_000_000.0, 0.0, growth=0.05, wacc=0.06, terminal_growth=0.30
        )
        self.assertTrue(result.available)
        self.assertLess(result.assumptions.terminal_growth, result.assumptions.wacc)

    def test_dette_nette_deduite(self) -> None:
        sans = valuation.discounted_cash_flow(1e6, 1e6, 0.0, 0.05)
        avec = valuation.discounted_cash_flow(1e6, 1e6, 5_000_000.0, 0.05)
        self.assertGreater(sans.value_per_share, avec.value_per_share)

    def test_croissance_implicite(self) -> None:
        rate, note = valuation.implied_growth([100.0, 110.0, 121.0, 133.1])
        self.assertAlmostEqual(rate, 0.10, places=2)
        self.assertIn("TCAC", note)

    def test_croissance_implicite_sans_historique(self) -> None:
        rate, note = valuation.implied_growth([100.0])
        self.assertEqual(rate, valuation.DEFAULT_GROWTH)
        self.assertIn("insuffisant", note)

    def test_croissance_aberrante_bornee(self) -> None:
        rate, note = valuation.implied_growth([1.0, 100.0, 10_000.0])
        self.assertLessEqual(rate, valuation.GROWTH_CAP)
        self.assertIn("ramené", note)


class TestPeers(unittest.TestCase):
    def test_mediane_de_comparables(self) -> None:
        result = valuation.peer_median_pe({"A": 10.0, "B": 20.0, "C": 30.0})
        self.assertEqual(result.median_pe, 20.0)
        self.assertIn("3 comparables", result.source)

    def test_valeurs_aberrantes_ecartees(self) -> None:
        result = valuation.peer_median_pe({"A": -5.0, "B": 400.0, "C": None, "D": 15.0})
        self.assertEqual(result.peers_failed, ["A", "B", "C"])
        self.assertIsNone(result.median_pe)  # moins de 3 exploitables

    def test_repli_documente(self) -> None:
        result = valuation.peer_median_pe({"A": 12.0})
        self.assertIsNone(result.median_pe)
        self.assertIn("repli", result.source)


# ---------------------------------------------------------------- Form 4


class TestForm4(unittest.TestCase):
    def test_parsing_achat(self) -> None:
        transactions = forms.parse_form4(FORM4_XML)
        self.assertEqual(len(transactions), 2)
        buy = transactions[0]
        self.assertTrue(buy.is_open_market_buy)
        self.assertEqual(buy.owner, "DOE JANE")
        self.assertEqual(buy.officer_title, "Chief Financial Officer")
        self.assertEqual(buy.value, 1_500_000.0)
        # L'attribution (code A) n'est ni un achat ni une vente de marché.
        self.assertFalse(transactions[1].is_open_market_buy)

    def test_xxe_refuse(self) -> None:
        """Entité externe : lecture de fichier local / SSRF."""
        with self.assertRaises(SecurityError):
            forms.parse_form4(FORM4_XXE)

    def test_bombe_dentites_refusee(self) -> None:
        with self.assertRaises(SecurityError):
            forms.parse_form4(FORM4_BOMB)

    def test_xml_invalide(self) -> None:
        with self.assertRaises(DataUnavailable):
            forms.parse_form4(b"<ownershipDocument>")

    def test_url_xml_brute(self) -> None:
        url = forms.raw_xml_url("0000320193", "0000320193-26-000041", "xslF345X03/wf-form4_1.xml")
        self.assertEqual(
            url,
            "https://www.sec.gov/Archives/edgar/data/320193/000032019326000041/wf-form4_1.xml",
        )

    def test_url_refusee_si_document_hostile(self) -> None:
        for document in ["../../../etc/passwd", "a/b/c.xml", "doc.htm", "x" * 200 + ".xml"]:
            self.assertIsNone(
                forms.raw_xml_url("0000320193", "0000320193-26-000041", document), msg=document
            )

    def test_verdicts(self) -> None:
        empty = forms.InsiderActivity()
        self.assertEqual(empty.verdict(), "INCONNU")

        activity = forms.InsiderActivity(forms_read=2)
        activity.transactions.extend(forms.parse_form4(FORM4_XML))
        self.assertEqual(activity.verdict(), "ACHAT_ISOLE")
        self.assertFalse(activity.compensation_only)

    def test_collecte_isole_les_echecs(self) -> None:
        routes = full_routes()
        routes["form4.xml"] = b"<ownershipDocument>"
        http = FakeHttp(routes)
        filings = [
            forms_stub("4", "0000320193-26-000041", "form4.xml"),
            forms_stub("4", "0000320193-26-000042", "form4.xml"),
        ]
        activity = forms.collect_insider_activity(http, "0000320193", filings)  # type: ignore[arg-type]
        self.assertEqual(activity.forms_read, 0)
        self.assertEqual(activity.forms_failed, 2)
        self.assertTrue(activity.warnings)


def forms_stub(form: str, accession: str, document: str):
    from osint_financial.sources.sec import Filing

    return Filing(
        form=form, filed_at=None, accession=accession, primary_document=document,
        description="", url=None,
    )


# ----------------------------------------------------------------- macro


class TestMacro(unittest.TestCase):
    def _http(self, index: list[float], vix: float, rates: list[float]) -> FakeHttp:
        return FakeHttp({
            "%5EGSPC": chart_payload(index),
            "%5EVIX": chart_payload([vix] * 300),
            "%5ETNX": chart_payload(rates),
        })

    def test_regime_favorable(self) -> None:
        regime = macro.assess(self._http(trending_closes(400), 12.0, trending_closes(400, drift=-0.001)))  # type: ignore[arg-type]
        self.assertTrue(regime.available)
        self.assertEqual(regime.regime, macro.FAVORABLE)
        self.assertTrue(regime.index_above_sma200)
        self.assertEqual(regime.vix_state, "calme")

    def test_regime_defavorable(self) -> None:
        regime = macro.assess(self._http(declining_closes(400), 32.0, trending_closes(400, drift=0.002)))  # type: ignore[arg-type]
        self.assertEqual(regime.regime, macro.DEFAVORABLE)
        self.assertEqual(regime.vix_state, "stress")

    def test_sources_absentes(self) -> None:
        regime = macro.assess(FakeHttp({}))  # type: ignore[arg-type]
        self.assertFalse(regime.available)
        self.assertTrue(regime.warnings)
        self.assertEqual(regime.score, 50.0)


# ------------------------------------------------------------- portefeuille


class TestPortfolio(unittest.TestCase):
    def test_aucune_position_si_pas_dachat(self) -> None:
        for recommendation in ("HOLD", "REDUCE", "SELL", "INSUFFICIENT_DATA"):
            plan = portfolio.build_plan(recommendation, 1.0, 100.0, 25.0)
            self.assertEqual(plan.suggested_weight_pct, 0.0)

    def test_plafond_respecte(self) -> None:
        plan = portfolio.build_plan("STRONG_BUY", 1.0, 100.0, 5.0)
        self.assertLessEqual(plan.suggested_weight_pct, portfolio.MAX_POSITION_PCT)

    def test_volatilite_reduit_la_taille(self) -> None:
        calme = portfolio.build_plan("STRONG_BUY", 1.0, 100.0, 25.0)
        agitee = portfolio.build_plan("STRONG_BUY", 1.0, 100.0, 75.0)
        self.assertGreater(calme.suggested_weight_pct, agitee.suggested_weight_pct)

    def test_confiance_reduit_la_taille(self) -> None:
        sure = portfolio.build_plan("BUY", 1.0, 100.0, 25.0)
        incertaine = portfolio.build_plan("BUY", 0.6, 100.0, 25.0)
        self.assertGreater(sure.suggested_weight_pct, incertaine.suggested_weight_pct)

    def test_niveaux_de_sortie(self) -> None:
        plan = portfolio.build_plan("BUY", 1.0, 200.0, 25.0)
        self.assertEqual(plan.stop_loss_price, 180.0)
        self.assertEqual(plan.partial_take_profit_price, 300.0)

    def test_allocation_de_reference(self) -> None:
        self.assertAlmostEqual(sum(portfolio.ALL_WEATHER.values()), 100.0, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
