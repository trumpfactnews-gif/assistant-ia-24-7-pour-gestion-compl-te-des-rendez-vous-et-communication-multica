"""Tests des métriques : EV, variance, Sharpe, Kelly, construction de combinés."""

import math

import pytest

from predopt.metrics import (
    build_combo,
    combo_score,
    expected_log_growth,
    expected_value,
    kelly_fraction,
    sharpe_ratio,
    variance,
)
from predopt.models import Leg


def make_leg(market="m1", prob=0.6, odds=2.0, outcome="Oui"):
    return Leg(
        market_id=market,
        market_question=f"Question {market}",
        outcome=outcome,
        category="test",
        prob=prob,
        odds=odds,
        price=1.0 / odds,
    )


def test_expected_value():
    assert expected_value(0.5, 2.0) == pytest.approx(0.0)
    assert expected_value(0.6, 2.0) == pytest.approx(0.2)
    assert expected_value(0.4, 2.0) == pytest.approx(-0.2)


def test_variance_bernoulli():
    # p=0.5, payout=2 : gains ±1 équiprobables → variance 1.
    assert variance(0.5, 2.0) == pytest.approx(1.0)


def test_sharpe_ratio():
    assert sharpe_ratio(0.6, 2.0) == pytest.approx(0.2 / math.sqrt(0.6 * 0.4 * 4.0))
    assert sharpe_ratio(0.5, 2.0) == pytest.approx(0.0)


def test_kelly_known_value():
    # p=0.6, cote 2 (b=1) : f* = (0.6·2 − 1)/1 = 0.2.
    assert kelly_fraction(0.6, 2.0) == pytest.approx(0.2)


def test_kelly_negative_ev_is_zero():
    assert kelly_fraction(0.4, 2.0) == 0.0


def test_kelly_cap():
    assert kelly_fraction(0.9, 5.0, cap=0.25) == 0.25


def test_expected_log_growth_maximized_at_kelly():
    p, payout = 0.6, 2.0
    f_star = kelly_fraction(p, payout)
    g_star = expected_log_growth(p, payout, f_star)
    assert g_star > expected_log_growth(p, payout, f_star / 2)
    assert g_star > expected_log_growth(p, payout, min(f_star * 1.5, 0.99))
    assert expected_log_growth(p, payout, 1.0) == -math.inf


def test_build_combo_single_leg():
    combo = build_combo([make_leg(prob=0.6, odds=2.0)])
    assert combo.prob == pytest.approx(0.6)
    assert combo.payout == pytest.approx(2.0)
    assert combo.ev == pytest.approx(0.2)
    assert combo.kelly == pytest.approx(0.2)


def test_build_combo_multiplies_independent_legs():
    legs = [make_leg("m1", 0.6, 2.0), make_leg("m2", 0.5, 2.2)]
    combo = build_combo(legs)
    assert combo.prob == pytest.approx(0.3)
    assert combo.payout == pytest.approx(4.4)
    assert combo.ev == pytest.approx(0.3 * 4.4 - 1.0)


def test_build_combo_haircut_reduces_prob():
    legs = [make_leg("m1", 0.6, 2.0), make_leg("m2", 0.5, 2.2)]
    plain = build_combo(legs)
    cut = build_combo(legs, haircut=0.05)
    assert cut.prob == pytest.approx(plain.prob * 0.95)
    assert cut.payout == pytest.approx(plain.payout)


def test_build_combo_rejects_same_market():
    with pytest.raises(ValueError):
        build_combo([make_leg("m1", outcome="Oui"), make_leg("m1", prob=0.3, outcome="Non")])


def test_build_combo_rejects_empty():
    with pytest.raises(ValueError):
        build_combo([])


def test_combo_score_objectives():
    combo = build_combo([make_leg(prob=0.6, odds=2.0)])
    assert combo_score(combo, "ev") == pytest.approx(combo.ev)
    assert combo_score(combo, "sharpe") == pytest.approx(combo.sharpe)
    assert combo_score(combo, "prob") == pytest.approx(combo.prob)
    assert combo_score(combo, "log_growth") == pytest.approx(
        expected_log_growth(0.6, 2.0, 0.5 * combo.kelly)
    )
    with pytest.raises(ValueError):
        combo_score(combo, "xyz")
