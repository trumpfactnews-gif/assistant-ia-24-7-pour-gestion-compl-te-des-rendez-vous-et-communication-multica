"""Tests du chargement/génération de marchés et de la conversion en jambes."""

import json

import pytest

from predopt.data import generate_sample_markets, load_markets, markets_to_legs, save_markets
from predopt.models import MarketType


def test_generate_is_reproducible():
    a = generate_sample_markets(n_markets=10, seed=123)
    b = generate_sample_markets(n_markets=10, seed=123)
    assert [m.id for m in a] == [m.id for m in b]
    assert [o.price for m in a for o in m.outcomes] == [o.price for m in b for o in m.outcomes]


def test_generate_structure():
    markets = generate_sample_markets(n_markets=30, seed=1)
    assert len(markets) == 30
    for m in markets:
        assert len(m.outcomes) >= 2
        if m.type is MarketType.BINARY:
            assert len(m.outcomes) == 2
        for o in m.outcomes:
            assert 0 < o.price < 1


def test_save_load_roundtrip(tmp_path):
    markets = generate_sample_markets(n_markets=8, seed=9)
    path = tmp_path / "markets.json"
    save_markets(markets, path)
    loaded = load_markets(path)
    assert [m.id for m in loaded] == [m.id for m in markets]
    for orig, back in zip(markets, loaded):
        assert back.type == orig.type
        assert back.category == orig.category
        for o1, o2 in zip(orig.outcomes, back.outcomes):
            assert o2.price == pytest.approx(o1.price, abs=1e-6)
            assert o2.hist_trials == o1.hist_trials


def test_load_minimal_market(tmp_path):
    path = tmp_path / "min.json"
    path.write_text(json.dumps({
        "markets": [{
            "id": "x",
            "question": "Test ?",
            "type": "binary",
            "outcomes": [{"name": "Oui", "price": 0.6}, {"name": "Non", "price": 0.45}],
        }]
    }), encoding="utf-8")
    markets = load_markets(path)
    assert markets[0].outcomes[0].model_prob is None


def test_markets_to_legs_basic():
    markets = generate_sample_markets(n_markets=20, seed=2)
    legs = markets_to_legs(markets)
    assert legs
    for leg in legs:
        assert 0 < leg.prob < 1
        assert leg.odds == pytest.approx(1.0 / leg.price)


def test_markets_to_legs_min_ev_filter():
    markets = generate_sample_markets(n_markets=40, seed=3)
    all_legs = markets_to_legs(markets)
    pos_legs = markets_to_legs(markets, min_leg_ev=0.0)
    assert len(pos_legs) < len(all_legs)
    assert all(leg.ev >= 0.0 for leg in pos_legs)


def test_markets_to_legs_max_odds_filter():
    markets = generate_sample_markets(n_markets=40, seed=4)
    legs = markets_to_legs(markets, max_odds=5.0)
    assert all(leg.odds <= 5.0 for leg in legs)
