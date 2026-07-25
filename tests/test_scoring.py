"""Tests du moteur de scoring — bugs logiques de ``calculate_scores`` et
comportement des règles ajoutées (croissance, liquidité, dilution, initiés,
DCF, momentum, résilience)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from osint_financial import scoring  # noqa: E402
from osint_financial.metrics import Metrics, _safe_ratio, sector_from_sic  # noqa: E402
from osint_financial.sources.forms import InsiderActivity, InsiderTransaction  # noqa: E402
from osint_financial.technical import TechnicalView  # noqa: E402
from osint_financial.valuation import DcfResult  # noqa: E402


def base_metrics(**overrides) -> Metrics:
    metrics = Metrics(ticker="TEST", company_name="Test Corp")
    metrics.pe_sector = 18.0
    for key, value in overrides.items():
        setattr(metrics, key, value)
    return metrics


def full_metrics(**overrides) -> Metrics:
    """Métriques où toutes les règles sont évaluables (confiance 100 %)."""
    view = TechnicalView(
        symbol="TEST",
        signal="HAUSSIER",
        price=100.0,
        sma_50=95.0,
        sma_200=90.0,
        rsi_14=60.0,
        momentum_20d_pct=4.0,
        momentum_60d_pct=9.0,
        volatility_annual_pct=28.0,
        max_drawdown_pct=20.0,
        distance_from_high_pct=-3.0,
        history_points=600,
    )
    dcf = DcfResult(value_per_share=130.0, low_per_share=110.0, high_per_share=150.0, upside_pct=30.0)
    metrics = base_metrics(
        price=100.0,
        eps=6.0,
        pe_ratio=16.0,
        debt_to_assets=0.35,
        profit_margin=0.20,
        current_ratio=1.8,
        free_cash_flow=1_000_000.0,
        cash=500_000.0,
        revenue_growth_yoy_pct=14.0,
        revenue_cagr_pct=11.0,
        share_count_growth_pct=0.5,
        target_price_pe=108.0,
        upside_pe_pct=8.0,
        filings_available=True,
        days_since_last_filing=12,
        technical=view,
        dcf=dcf,
        insider=_insider(buys=2, owners=("A", "B")),
    )
    for key, value in overrides.items():
        setattr(metrics, key, value)
    return metrics


def _insider(buys: int = 0, sells: int = 0, owners: tuple[str, ...] = ("A",)) -> InsiderActivity:
    activity = InsiderActivity(forms_read=max(1, buys + sells))
    for index in range(buys):
        activity.transactions.append(
            InsiderTransaction(
                owner=owners[index % len(owners)], is_officer=True, is_director=False,
                officer_title="CFO", code="P", transaction_date=None, shares=1000.0,
                price_per_share=100.0, acquired=True,
            )
        )
    for index in range(sells):
        activity.transactions.append(
            InsiderTransaction(
                owner=owners[index % len(owners)], is_officer=True, is_director=False,
                officer_title="CFO", code="S", transaction_date=None, shares=1000.0,
                price_per_share=100.0, acquired=False,
            )
        )
    return activity


class TestMissingData(unittest.TestCase):
    """Bug n°1 : aucune donnée produisait quand même un « HOLD » assuré."""

    def test_absence_totale_de_donnees(self) -> None:
        result = scoring.compute(base_metrics())
        self.assertEqual(result.recommendation, "INSUFFICIENT_DATA")
        self.assertLess(result.confidence, scoring.MIN_CONFIDENCE)
        self.assertTrue(result.missing_inputs)
        self.assertIsNone(result.resilience_score)

    def test_confiance_croit_avec_la_couverture(self) -> None:
        partiel = scoring.compute(base_metrics(profit_margin=0.2))
        complet = scoring.compute(full_metrics())
        self.assertGreater(complet.confidence, partiel.confidence)
        self.assertEqual(complet.confidence, 1.0)


class TestFalsyValues(unittest.TestCase):
    """Bug n°2 : ``if debt and debt > 0.5`` confondait 0.0 et None."""

    def test_dette_nulle_est_evaluee(self) -> None:
        outcome = scoring.rule_leverage(base_metrics(debt_to_assets=0.0))
        self.assertTrue(outcome.evaluated)
        self.assertEqual(outcome.points, 0.0)

    def test_dette_absente_est_ignoree(self) -> None:
        self.assertFalse(scoring.rule_leverage(base_metrics(debt_to_assets=None)).evaluated)

    def test_marge_nulle_evaluee(self) -> None:
        outcome = scoring.rule_profitability(base_metrics(profit_margin=0.0))
        self.assertTrue(outcome.evaluated)
        self.assertGreater(outcome.points, 0.0)


class TestDivisionGuards(unittest.TestCase):
    def test_prix_nul(self) -> None:
        self.assertIsNone(_safe_ratio(10.0, 0.0))

    def test_valeurs_absentes(self) -> None:
        self.assertIsNone(_safe_ratio(None, 5.0))
        self.assertIsNone(_safe_ratio(5.0, None))

    def test_nan(self) -> None:
        self.assertIsNone(_safe_ratio(float("nan"), 1.0))


class TestFilingSemantics(unittest.TestCase):
    """Bug n°3 : « zéro filing » et « appel SEC en échec » confondus."""

    def test_echec_sec_ne_penalise_pas(self) -> None:
        outcome = scoring.rule_disclosure(base_metrics(filings_available=False, filings=[]))
        self.assertFalse(outcome.evaluated)
        self.assertEqual(outcome.points, 0.0)

    def test_absence_reelle_penalise(self) -> None:
        outcome = scoring.rule_disclosure(base_metrics(filings_available=True, filings=[]))
        self.assertTrue(outcome.evaluated)
        self.assertGreater(outcome.points, 0.0)


class TestNewRules(unittest.TestCase):
    """Règles rendues calculables : croissance, liquidité, dilution, initiés."""

    def test_croissance(self) -> None:
        forte = scoring.rule_growth(base_metrics(revenue_growth_yoy_pct=20.0))
        recul = scoring.rule_growth(base_metrics(revenue_growth_yoy_pct=-8.0))
        absente = scoring.rule_growth(base_metrics())
        self.assertGreater(forte.points, 0)
        self.assertLess(recul.points, 0)
        self.assertFalse(absente.evaluated)

    def test_liquidite(self) -> None:
        tendue = scoring.rule_liquidity(base_metrics(current_ratio=0.8))
        saine = scoring.rule_liquidity(base_metrics(current_ratio=2.4))
        self.assertGreater(tendue.points, saine.points)

    def test_autonomie_de_tresorerie(self) -> None:
        critique = scoring.rule_cash_runway(
            base_metrics(free_cash_flow=-1_200_000.0, cash=600_000.0, cash_runway_months=6.0)
        )
        self.assertGreater(critique.points, 10)
        positif = scoring.rule_cash_runway(base_metrics(free_cash_flow=500_000.0))
        self.assertEqual(positif.points, 0.0)

    def test_dilution(self) -> None:
        lourde = scoring.rule_dilution(
            base_metrics(share_count_growth_pct=12.0, filings_available=True)
        )
        rachats = scoring.rule_dilution(
            base_metrics(share_count_growth_pct=-4.0, filings_available=True)
        )
        self.assertGreater(lourde.points, 0)
        self.assertEqual(rachats.points, 0.0)

    def test_achat_groupe_dinities(self) -> None:
        groupe = scoring.rule_insider_buying(
            base_metrics(insider=_insider(buys=2, owners=("A", "B")))
        )
        isole = scoring.rule_insider_buying(base_metrics(insider=_insider(buys=1)))
        self.assertGreater(groupe.points, isole.points)

    def test_remuneration_seule_ne_vaut_pas_signal(self) -> None:
        activity = InsiderActivity(forms_read=3)
        activity.transactions.append(
            InsiderTransaction(
                owner="A", is_officer=True, is_director=False, officer_title="CEO",
                code="A", transaction_date=None, shares=1000.0, price_per_share=0.0,
                acquired=True,
            )
        )
        outcome = scoring.rule_insider_buying(base_metrics(insider=activity))
        self.assertTrue(outcome.evaluated)
        self.assertEqual(outcome.points, 0.0)
        self.assertIn("rémunération", outcome.evidence)

    def test_ventes_groupees(self) -> None:
        outcome = scoring.rule_insider_selling(
            base_metrics(insider=_insider(sells=3, owners=("A", "B", "C")))
        )
        self.assertGreater(outcome.points, 10)

    def test_dcf_upside(self) -> None:
        fort = scoring.rule_dcf_upside(
            base_metrics(dcf=DcfResult(value_per_share=200.0, upside_pct=45.0))
        )
        surevalue = scoring.rule_dcf_upside(
            base_metrics(dcf=DcfResult(value_per_share=50.0, upside_pct=-40.0))
        )
        indisponible = scoring.rule_dcf_upside(base_metrics())
        self.assertGreater(fort.points, 0)
        self.assertLess(surevalue.points, 0)
        self.assertFalse(indisponible.evaluated)


class TestResilience(unittest.TestCase):
    """Score de résilience : 50 % fondamentaux + 25 % marché + 25 % macro."""

    def test_ponderation_complete(self) -> None:
        result = scoring.compute(full_metrics(), macro_score=80.0)
        parts = result.resilience_parts
        self.assertIsNotNone(parts["fondamentaux"])
        self.assertIsNotNone(parts["position_marche"])
        self.assertEqual(parts["macro"], 80.0)
        expected = (
            parts["fondamentaux"] * 0.5
            + parts["position_marche"] * 0.25
            + parts["macro"] * 0.25
        )
        self.assertAlmostEqual(result.resilience_score, round(expected, 1), places=1)

    def test_renormalisation_si_composante_absente(self) -> None:
        """Sans macro, les poids restants sont renormalisés — pas de valeur neutre."""
        result = scoring.compute(full_metrics(), macro_score=None)
        parts = result.resilience_parts
        self.assertIsNone(parts["macro"])
        expected = (parts["fondamentaux"] * 0.5 + parts["position_marche"] * 0.25) / 0.75
        self.assertAlmostEqual(result.resilience_score, round(expected, 1), places=1)

    def test_position_marche_absente_sans_historique(self) -> None:
        self.assertIsNone(scoring.market_position_score(base_metrics()))


class TestBoundsAndDeterminism(unittest.TestCase):
    def test_scores_bornes(self) -> None:
        view = TechnicalView(
            symbol="TEST", signal="BAISSIER", price=1.0, sma_50=2.0, sma_200=3.0,
            rsi_14=20.0, momentum_20d_pct=-30.0, momentum_60d_pct=-50.0,
            volatility_annual_pct=90.0, max_drawdown_pct=80.0,
            distance_from_high_pct=-70.0, history_points=600,
        )
        extreme = full_metrics(
            debt_to_assets=0.99,
            profit_margin=-0.9,
            pe_ratio=900.0,
            upside_pe_pct=-90.0,
            target_price_pe=1.8,
            current_ratio=0.4,
            free_cash_flow=-5_000_000.0,
            cash=100_000.0,
            cash_runway_months=0.2,
            share_count_growth_pct=40.0,
            revenue_growth_yoy_pct=-30.0,
            technical=view,
            dcf=DcfResult(value_per_share=0.4, upside_pct=-95.0),
            insider=_insider(sells=4, owners=("A", "B", "C", "D")),
        )
        result = scoring.compute(extreme, macro_score=10.0)
        self.assertEqual(result.risk_score, 100.0)
        self.assertGreaterEqual(result.opportunity_score, 0.0)
        self.assertEqual(result.recommendation, "SELL")
        self.assertLess(result.resilience_score, 40.0)

    def test_deterministe(self) -> None:
        metrics = full_metrics()
        self.assertEqual(scoring.compute(metrics).to_dict(), scoring.compute(metrics).to_dict())

    def test_tracabilite_des_facteurs(self) -> None:
        result = scoring.compute(base_metrics(debt_to_assets=0.8, profit_margin=0.2))
        self.assertTrue(any("passif/actif" in factor for factor in result.risk_factors))


class TestSectorMapping(unittest.TestCase):
    def test_mapping(self) -> None:
        self.assertEqual(sector_from_sic("Services-Prepackaged Software"), "technology")
        self.assertEqual(sector_from_sic("Crude Petroleum & Natural Gas"), "energy")
        self.assertEqual(sector_from_sic(None), "default")
        self.assertEqual(sector_from_sic("Something Unmapped"), "default")


if __name__ == "__main__":
    unittest.main(verbosity=2)
