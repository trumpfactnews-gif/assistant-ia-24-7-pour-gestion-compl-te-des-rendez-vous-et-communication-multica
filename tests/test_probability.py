"""Tests du module probability : dé-vig, lissage, mélanges."""

import math

import pytest

from predopt.probability import (
    beta_shrink,
    blend_log_odds,
    correlation_haircut,
    devig,
    devig_power,
    devig_proportional,
    estimate_outcome_prob,
    overround,
)


def test_overround():
    assert overround([0.55, 0.50]) == pytest.approx(0.05)
    assert overround([0.5, 0.5]) == pytest.approx(0.0)


def test_devig_proportional_sums_to_one():
    probs = devig_proportional([0.55, 0.50])
    assert sum(probs) == pytest.approx(1.0)
    assert probs[0] == pytest.approx(0.55 / 1.05)


def test_devig_power_sums_to_one():
    for prices in ([0.55, 0.50], [0.40, 0.35, 0.30], [0.05, 0.97], [0.2, 0.2, 0.2, 0.2, 0.25]):
        probs = devig_power(prices)
        assert sum(probs) == pytest.approx(1.0, abs=1e-8)
        assert all(0 < p < 1 for p in probs)


def test_devig_power_no_vig_is_identity():
    probs = devig_power([0.6, 0.4])
    assert probs[0] == pytest.approx(0.6, abs=1e-8)


def test_devig_power_hits_longshots_harder():
    """La méthode power retire proportionnellement plus de marge aux outsiders."""
    prices = [0.80, 0.25]  # favori + outsider, marge 5 %
    prop = devig_proportional(prices)
    power = devig_power(prices)
    # Réduction relative de l'outsider plus forte en power qu'en proportionnel.
    rel_prop = (prices[1] - prop[1]) / prices[1]
    rel_power = (prices[1] - power[1]) / prices[1]
    assert rel_power > rel_prop


def test_devig_underround():
    """Somme < 1 (rare mais possible en carnet d'ordres) : renormalise vers le haut."""
    probs = devig_power([0.4, 0.5])
    assert sum(probs) == pytest.approx(1.0, abs=1e-8)
    assert probs[0] > 0.4


def test_devig_dispatch():
    assert devig([0.55, 0.5], "proportional") == devig_proportional([0.55, 0.5])
    with pytest.raises(ValueError):
        devig([0.55, 0.5], "inconnu")


def test_devig_rejects_invalid_prices():
    with pytest.raises(ValueError):
        devig_proportional([0.0, 0.5])
    with pytest.raises(ValueError):
        devig_power([1.2, 0.5])


def test_beta_shrink_small_sample_stays_near_prior():
    # 2 succès sur 2 essais : sans lissage p=1, avec lissage reste raisonnable.
    p = beta_shrink(2, 2, prior_prob=0.5, prior_strength=10.0)
    assert 0.5 < p < 0.7


def test_beta_shrink_large_sample_converges_to_frequency():
    p = beta_shrink(700, 1000, prior_prob=0.5, prior_strength=10.0)
    assert p == pytest.approx(0.7, abs=0.01)


def test_beta_shrink_validation():
    with pytest.raises(ValueError):
        beta_shrink(5, 3, 0.5)


def test_blend_log_odds_extremes():
    assert blend_log_odds(0.3, 0.7, 0.0) == pytest.approx(0.3, abs=1e-9)
    assert blend_log_odds(0.3, 0.7, 1.0) == pytest.approx(0.7, abs=1e-9)
    mid = blend_log_odds(0.3, 0.7, 0.5)
    assert 0.3 < mid < 0.7


def test_blend_log_odds_symmetric_at_half():
    # En log-odds, mélange 50/50 de p et 1-p donne 0.5.
    assert blend_log_odds(0.2, 0.8, 0.5) == pytest.approx(0.5, abs=1e-9)


def test_estimate_outcome_prob_market_only():
    assert estimate_outcome_prob(0.42) == pytest.approx(0.42, abs=1e-6)


def test_estimate_outcome_prob_with_history_moves_toward_frequency():
    p = estimate_outcome_prob(0.4, hist_wins=90, hist_trials=100)
    assert p > 0.55  # l'historique (90 %) tire fortement vers le haut


def test_estimate_outcome_prob_with_model():
    p = estimate_outcome_prob(0.4, model_prob=0.6, model_weight=1.0)
    assert p == pytest.approx(0.6, abs=1e-6)


def test_correlation_haircut():
    assert correlation_haircut(0.5, 1, 0.1) == pytest.approx(0.5)
    assert correlation_haircut(0.5, 3, 0.1) == pytest.approx(0.5 * 0.81)
    assert correlation_haircut(0.5, 2, 0.0) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        correlation_haircut(0.5, 2, 1.5)
