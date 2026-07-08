"""Tests du moteur combinatoire : exactitude vs force brute, contraintes, échelle."""

import random

import pytest

from predopt.engine import CombinationEngine, search_space_size
from predopt.models import Leg


def random_legs(n, seed=0, n_markets=None):
    """Pool de jambes aléatoires ; ``n_markets`` < n force des marchés partagés."""
    rng = random.Random(seed)
    n_markets = n_markets or n
    legs = []
    for i in range(n):
        market = f"m{i % n_markets}"
        price = rng.uniform(0.05, 0.9)
        prob = min(max(price + rng.gauss(0, 0.08), 0.02), 0.97)
        legs.append(
            Leg(
                market_id=market,
                market_question=f"Q {market}",
                outcome=f"o{i}",
                category="test",
                prob=prob,
                odds=1.0 / price,
                price=price,
            )
        )
    return legs


def combo_key(combo):
    return frozenset((leg.market_id, leg.outcome) for leg in combo.legs)


def test_search_space_size():
    assert search_space_size(10, 1, 2) == 10 + 45
    assert search_space_size(300, 5, 5) == 19_582_837_560


@pytest.mark.parametrize("objective", ["ev", "prob"])
def test_exact_objectives_match_brute_force(objective):
    """Sur les objectifs séparables, l'élagage doit être exact."""
    legs = random_legs(14, seed=1)
    engine = CombinationEngine(legs)
    fast, _ = engine.search(min_legs=1, max_legs=3, top=10, objective=objective)
    slow = engine.brute_force(min_legs=1, max_legs=3, top=10, objective=objective)
    assert [c.score for c in fast] == pytest.approx([c.score for c in slow])
    # Mêmes ensembles au score près (l'ordre des ex æquo peut différer).
    assert {combo_key(c) for c in fast} == {combo_key(c) for c in slow}


@pytest.mark.parametrize("objective", ["ev", "prob"])
def test_exact_objectives_with_constraints_match_brute_force(objective):
    legs = random_legs(12, seed=2)
    engine = CombinationEngine(legs, haircut=0.05)
    kwargs = dict(min_legs=2, max_legs=3, top=8, objective=objective,
                  min_prob=0.05, min_payout=3.0)
    fast, _ = engine.search(**kwargs)
    slow = engine.brute_force(**kwargs)
    assert [c.score for c in fast] == pytest.approx([c.score for c in slow])


@pytest.mark.parametrize("objective", ["sharpe", "log_growth"])
def test_rerank_objectives_close_to_brute_force(objective):
    """Objectifs non séparables : le pool sur-échantillonné doit retrouver le vrai top."""
    legs = random_legs(12, seed=3)
    engine = CombinationEngine(legs)
    fast, _ = engine.search(min_legs=1, max_legs=3, top=5, objective=objective)
    slow = engine.brute_force(min_legs=1, max_legs=3, top=5, objective=objective)
    assert fast[0].score == pytest.approx(slow[0].score)
    assert {combo_key(c) for c in fast} == {combo_key(c) for c in slow}


def test_one_leg_per_market():
    # 10 jambes réparties sur 4 marchés seulement.
    legs = random_legs(10, seed=4, n_markets=4)
    engine = CombinationEngine(legs)
    combos, _ = engine.search(min_legs=2, max_legs=4, top=30, objective="ev")
    assert combos
    for combo in combos:
        market_ids = [leg.market_id for leg in combo.legs]
        assert len(set(market_ids)) == len(market_ids)


def test_constraints_respected():
    legs = random_legs(15, seed=5)
    engine = CombinationEngine(legs, haircut=0.04)
    combos, _ = engine.search(
        min_legs=2, max_legs=4, top=20, objective="ev", min_prob=0.10, min_payout=2.5
    )
    for combo in combos:
        assert combo.prob >= 0.10
        assert combo.payout >= 2.5
        assert 2 <= combo.n_legs <= 4


def test_ranks_and_sorted_scores():
    legs = random_legs(10, seed=6)
    combos, _ = CombinationEngine(legs).search(max_legs=2, top=10)
    assert [c.rank for c in combos] == list(range(1, len(combos) + 1))
    scores = [c.score for c in combos]
    assert scores == sorted(scores, reverse=True)


def test_large_scale_pruning_billions():
    """350 jambes, combinés de 5 : ~42 milliards de combinaisons couvertes
    en explorant une fraction infime de l'arbre, en quelques secondes."""
    legs = random_legs(350, seed=7)
    engine = CombinationEngine(legs)
    combos, stats = engine.search(min_legs=5, max_legs=5, top=20, objective="ev")
    assert stats.space_size > 40_000_000_000
    assert len(combos) == 20
    assert stats.nodes_visited < 5_000_000  # élagage massif
    assert stats.pruning_ratio > 0.9999
    # Vérification d'optimalité : le meilleur combiné EV est forcément composé
    # des 5 meilleures jambes par p·cote (marchés tous distincts ici).
    best_by_factor = sorted(legs, key=lambda l: l.prob * l.odds, reverse=True)[:5]
    assert combo_key(combos[0]) == frozenset(
        (l.market_id, l.outcome) for l in best_by_factor
    )


def test_max_legs_clamped_to_pool_size():
    legs = random_legs(3, seed=8)
    combos, _ = CombinationEngine(legs).search(min_legs=1, max_legs=10, top=50)
    assert max(c.n_legs for c in combos) <= 3


def test_empty_pool_rejected():
    with pytest.raises(ValueError):
        CombinationEngine([])


def test_invalid_args():
    legs = random_legs(5)
    engine = CombinationEngine(legs)
    with pytest.raises(ValueError):
        engine.search(min_legs=0)
    with pytest.raises(ValueError):
        engine.search(min_legs=3, max_legs=2)
    with pytest.raises(ValueError):
        engine.search(objective="magie")
