"""Tests du moteur de scoring — bugs logiques de ``calculate_scores``."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osint_financial import scoring  # noqa: E402
from osint_financial.metrics import Metrics, _safe_ratio, sector_from_sic  # noqa: E402


def base_metrics(**overrides) -> Metrics:
    metrics = Metrics(ticker="TEST", company_name="Test Corp")
    metrics.pe_sector = 18.0
    for key, value in overrides.items():
        setattr(metrics, key, value)
    return metrics


class TestMissingData(unittest.TestCase):
    """Bug n°1 : aucune donnée produisait quand même un « HOLD » assuré."""

    def test_absence_totale_de_donnees(self) -> None:
        result = scoring.compute(base_metrics())
        self.assertEqual(result.recommendation, "INSUFFICIENT_DATA")
        self.assertLess(result.confidence, scoring.MIN_CONFIDENCE)
        self.assertTrue(result.missing_inputs)

    def test_confiance_croit_avec_la_couverture(self) -> None:
        partiel = scoring.compute(base_metrics(profit_margin=0.2))
        complet = scoring.compute(
            base_metrics(
                debt_to_assets=0.3,
                profit_margin=0.2,
                pe_ratio=15.0,
                price=100.0,
                eps=6.0,
                target_price_pe=108.0,
                upside_pe_pct=8.0,
                cash=1e6,
                long_term_debt=1e6,
                filings_available=True,
                days_since_last_filing=10,
                filings=[],
            )
        )
        self.assertGreater(complet.confidence, partiel.confidence)


class TestFalsyValues(unittest.TestCase):
    """Bug n°2 : ``if debt and debt > 0.5`` confondait 0.0 et None."""

    def test_dette_nulle_est_evaluee(self) -> None:
        outcome = scoring.rule_leverage(base_metrics(debt_to_assets=0.0))
        self.assertTrue(outcome.evaluated)
        self.assertEqual(outcome.points, 0.0)

    def test_dette_absente_est_ignoree(self) -> None:
        outcome = scoring.rule_leverage(base_metrics(debt_to_assets=None))
        self.assertFalse(outcome.evaluated)

    def test_marge_nulle_evaluee(self) -> None:
        outcome = scoring.rule_profitability(base_metrics(profit_margin=0.0))
        self.assertTrue(outcome.evaluated)
        self.assertGreater(outcome.points, 0.0)


class TestDivisionGuards(unittest.TestCase):
    """Bug n°3 : ``(target - price) / price`` sans garde."""

    def test_prix_nul(self) -> None:
        self.assertIsNone(_safe_ratio(10.0, 0.0))

    def test_valeurs_absentes(self) -> None:
        self.assertIsNone(_safe_ratio(None, 5.0))
        self.assertIsNone(_safe_ratio(5.0, None))

    def test_nan(self) -> None:
        self.assertIsNone(_safe_ratio(float("nan"), 1.0))


class TestFilingSemantics(unittest.TestCase):
    """Bug n°4 : « zéro filing » et « appel SEC en échec » confondus."""

    def test_echec_sec_ne_penalise_pas(self) -> None:
        outcome = scoring.rule_disclosure(base_metrics(filings_available=False, filings=[]))
        self.assertFalse(outcome.evaluated)
        self.assertEqual(outcome.points, 0.0)

    def test_absence_reelle_penalise(self) -> None:
        outcome = scoring.rule_disclosure(base_metrics(filings_available=True, filings=[]))
        self.assertTrue(outcome.evaluated)
        self.assertGreater(outcome.points, 0.0)


class TestBoundsAndDeterminism(unittest.TestCase):
    def test_scores_bornes(self) -> None:
        extreme = base_metrics(
            debt_to_assets=0.99,
            profit_margin=-0.9,
            pe_ratio=900.0,
            price=100.0,
            eps=0.1,
            upside_pe_pct=-90.0,
            target_price_pe=1.8,
            cash=0.0,
            long_term_debt=1e9,
            filings_available=True,
            filings=[],
        )
        result = scoring.compute(extreme)
        self.assertGreaterEqual(result.risk_score, 0.0)
        self.assertLessEqual(result.risk_score, 100.0)
        self.assertGreaterEqual(result.opportunity_score, 0.0)
        self.assertLessEqual(result.opportunity_score, 100.0)
        self.assertEqual(result.recommendation, "SELL")

    def test_deterministe(self) -> None:
        metrics = base_metrics(debt_to_assets=0.35, profit_margin=0.18, pe_ratio=14.0)
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
