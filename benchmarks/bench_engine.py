"""Benchmark du moteur combinatoire : balayage taille d'univers × taille de combiné.

Usage :
    PYTHONPATH=src python3 benchmarks/bench_engine.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from predopt.data import generate_sample_markets, markets_to_legs  # noqa: E402
from predopt.engine import CombinationEngine  # noqa: E402

SCENARIOS = [
    # (n_markets, max_legs, objective, min_prob)
    (100, 4, "ev", 0.0),
    (300, 5, "ev", 0.0),
    (300, 5, "ev", 0.10),
    (300, 5, "sharpe", 0.05),
    (500, 6, "ev", 0.0),
    (500, 6, "ev", 0.05),
]


def fmt(n: float) -> str:
    return f"{n:,.0f}".replace(",", " ")


def main() -> None:
    print(f"{'Marchés':>8} {'Jambes':>7} {'k max':>6} {'Objectif':>10} {'P min':>6} "
          f"{'Espace':>22} {'Nœuds':>10} {'Temps':>8} {'Débit équiv./s':>20}")
    for n_markets, max_legs, objective, min_prob in SCENARIOS:
        markets = generate_sample_markets(n_markets=n_markets, seed=7)
        legs = markets_to_legs(markets)
        engine = CombinationEngine(legs, haircut=0.03)
        t0 = time.perf_counter()
        combos, stats = engine.search(
            min_legs=1, max_legs=max_legs, top=50,
            objective=objective, min_prob=min_prob,
        )
        dt = time.perf_counter() - t0
        rate = stats.space_size / dt if dt > 0 else float("inf")
        print(f"{n_markets:>8} {len(legs):>7} {max_legs:>6} {objective:>10} {min_prob:>6.2f} "
              f"{fmt(stats.space_size):>22} {fmt(stats.nodes_visited):>10} {dt:>7.3f}s "
              f"{fmt(rate):>20}")
        assert combos, "le benchmark doit produire des résultats"


if __name__ == "__main__":
    main()
