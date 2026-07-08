"""Moteur combinatoire : recherche des meilleurs combinés à très grande échelle.

Problème : avec n jambes candidates et des combinés de k jambes, l'espace de
recherche Σₖ C(n, k) explose vite — C(300, 5) ≈ 19,6 milliards. L'énumération
brute est impossible en temps réel.

Solution : recherche **branch-and-bound** en profondeur avec bornes
optimistes. Les métriques clés d'un combiné indépendant sont *séparables en
log* :

- ``log(prob) = Σ log(pᵢ)``
- ``log(EV factor) = Σ log(pᵢ·coteᵢ)`` (l'EV vaut ``exp(Σ) − 1``, monotone)

En triant les jambes par poids décroissant, la meilleure complétion possible
d'un préfixe se lit dans un tableau de sommes cumulées : si même la
complétion la plus optimiste ne peut ni battre le K-ième meilleur score
connu ni satisfaire les contraintes (prob. minimale, cote minimale), la
branche entière — et les milliards de combinaisons qu'elle contient — est
éliminée d'un coup.

Résultat : les objectifs ``ev`` et ``prob`` sont optimisés **exactement**
sur tout l'espace en n'explorant qu'une fraction infime des nœuds. Les
objectifs non séparables (``sharpe``, ``log_growth``) sont résolus par
sur-échantillonnage : on collecte un pool élargi de candidats via les deux
surrogates exacts, puis on reclasse le pool avec l'objectif exact.
"""

from __future__ import annotations

import heapq
import itertools
import math
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .metrics import build_combo, combo_score
from .models import Combo, Leg


@dataclass
class SearchStats:
    """Statistiques d'une recherche : couverture et travail effectif."""

    space_size: int = 0        # nb total de combinaisons dans l'espace couvert
    nodes_visited: int = 0     # nœuds de l'arbre de recherche réellement visités
    combos_evaluated: int = 0  # combinés complets évalués
    elapsed_s: float = 0.0

    @property
    def pruning_ratio(self) -> float:
        """Fraction de l'espace éliminée sans évaluation explicite."""
        if self.space_size == 0:
            return 0.0
        return 1.0 - min(self.combos_evaluated / self.space_size, 1.0)


def search_space_size(n_legs: int, min_legs: int, max_legs: int) -> int:
    """Taille de l'espace de recherche : Σₖ C(n, k) pour k ∈ [min, max]."""
    return sum(math.comb(n_legs, k) for k in range(min_legs, max_legs + 1))


# Objectifs séparables en log → recherche exacte par branch-and-bound.
_EXACT_OBJECTIVES = {"ev", "prob"}
# Objectifs reclassés exactement sur un pool sur-échantillonné.
_RERANK_OBJECTIVES = {"sharpe", "log_growth"}


class CombinationEngine:
    """Recherche les meilleurs combinés parmi un ensemble de jambes.

    Args:
        legs: jambes candidates (plusieurs jambes d'un même marché sont
            permises dans le pool ; un combiné n'en prendra jamais deux).
        haircut: malus de corrélation appliqué à la probabilité jointe,
            voir :func:`predopt.probability.correlation_haircut`.
        kelly_cap: plafond de la fraction de Kelly retournée.
    """

    def __init__(
        self,
        legs: Sequence[Leg],
        haircut: float = 0.0,
        kelly_cap: float = 1.0,
    ) -> None:
        if not legs:
            raise ValueError("aucune jambe candidate")
        self.legs = list(legs)
        self.haircut = haircut
        self.kelly_cap = kelly_cap

    # ------------------------------------------------------------------ API

    def search(
        self,
        min_legs: int = 1,
        max_legs: int = 3,
        top: int = 20,
        objective: str = "ev",
        min_prob: float = 0.0,
        min_payout: float = 1.0,
        oversample: int = 20,
    ) -> tuple[list[Combo], SearchStats]:
        """Renvoie les ``top`` meilleurs combinés selon ``objective``.

        Args:
            min_legs / max_legs: bornes du nombre de jambes par combiné.
            top: nombre de résultats retournés.
            objective: ``ev`` | ``prob`` | ``sharpe`` | ``log_growth``.
            min_prob: probabilité de victoire minimale (après malus).
            min_payout: cote combinée minimale.
            oversample: facteur de sur-échantillonnage du pool pour les
                objectifs non séparables.
        """
        if min_legs < 1 or max_legs < min_legs:
            raise ValueError("bornes de jambes invalides")
        if max_legs > len(self.legs):
            max_legs = len(self.legs)
        if objective not in _EXACT_OBJECTIVES | _RERANK_OBJECTIVES:
            raise ValueError(f"objectif inconnu : {objective}")

        t0 = time.perf_counter()
        stats = SearchStats(space_size=search_space_size(len(self.legs), min_legs, max_legs))

        if objective in _EXACT_OBJECTIVES:
            surrogates = [objective]
            pool_size = top
        else:
            # Pool élargi collecté via les deux surrogates exacts, puis
            # reclassement exact — les bons combinés sharpe/log_growth sont
            # soit à forte EV, soit à forte probabilité.
            surrogates = ["ev", "prob"]
            pool_size = max(top * oversample, 200)

        candidate_sets: dict[frozenset[int], tuple[int, ...]] = {}
        for k in range(min_legs, max_legs + 1):
            for surrogate in surrogates:
                for indices in self._top_by_surrogate(
                    k, pool_size, surrogate, min_prob, min_payout, stats
                ):
                    candidate_sets.setdefault(frozenset(indices), indices)

        combos: list[Combo] = []
        for indices in candidate_sets.values():
            combo = build_combo(
                [self.legs[i] for i in indices],
                haircut=self.haircut,
                kelly_cap=self.kelly_cap,
            )
            stats.combos_evaluated += 1
            if combo.prob < min_prob or combo.payout < min_payout:
                continue
            combo.score = combo_score(combo, objective)
            combos.append(combo)

        combos.sort(key=lambda c: c.score, reverse=True)
        combos = combos[:top]
        for rank, combo in enumerate(combos, start=1):
            combo.rank = rank
        stats.elapsed_s = time.perf_counter() - t0
        return combos, stats

    def brute_force(
        self,
        min_legs: int = 1,
        max_legs: int = 3,
        top: int = 20,
        objective: str = "ev",
        min_prob: float = 0.0,
        min_payout: float = 1.0,
    ) -> list[Combo]:
        """Référence exhaustive (petites instances / tests uniquement)."""
        combos: list[Combo] = []
        n = len(self.legs)
        for k in range(min_legs, min(max_legs, n) + 1):
            for indices in itertools.combinations(range(n), k):
                legs = [self.legs[i] for i in indices]
                if len({leg.market_id for leg in legs}) != k:
                    continue
                combo = build_combo(legs, haircut=self.haircut, kelly_cap=self.kelly_cap)
                if combo.prob < min_prob or combo.payout < min_payout:
                    continue
                combo.score = combo_score(combo, objective)
                combos.append(combo)
        combos.sort(key=lambda c: c.score, reverse=True)
        combos = combos[:top]
        for rank, combo in enumerate(combos, start=1):
            combo.rank = rank
        return combos

    # ------------------------------------------------- branch-and-bound core

    def _top_by_surrogate(
        self,
        k: int,
        top: int,
        surrogate: str,
        min_prob: float,
        min_payout: float,
        stats: SearchStats,
    ) -> list[tuple[int, ...]]:
        """Top-``top`` ensembles de ``k`` jambes par poids séparable exact.

        DFS include/skip sur les jambes triées par poids décroissant, avec :

        - borne d'optimalité : somme cumulée des meilleurs poids restants ;
        - borne de faisabilité prob. : somme des k meilleurs log(p) globaux ;
        - borne de faisabilité cote : somme des k meilleurs log(cote) globaux ;
        - exclusivité : au plus une jambe par marché.
        """
        n = len(self.legs)
        if k > n:
            return []

        if surrogate == "ev":
            weights = [leg.log_ev_factor for leg in self.legs]
        else:  # "prob"
            weights = [leg.log_prob for leg in self.legs]

        order = sorted(range(n), key=lambda i: weights[i], reverse=True)
        w = [weights[i] for i in order]
        lp = [self.legs[order[i]].log_prob for i in range(n)]
        lo = [self.legs[order[i]].log_odds for i in range(n)]
        mid = [self.legs[order[i]].market_id for i in range(n)]

        # Sommes cumulées des poids triés : meilleure complétion de r jambes
        # à partir de la position i = pre_w[i+r] − pre_w[i].
        pre_w = [0.0] * (n + 1)
        for i in range(n):
            pre_w[i + 1] = pre_w[i] + w[i]

        # Bornes globales (indépendantes de la position, donc optimistes) :
        # somme des r plus grands log(p) et log(cote) de tout le pool.
        best_lp = sorted((leg.log_prob for leg in self.legs), reverse=True)
        best_lo = sorted((leg.log_odds for leg in self.legs), reverse=True)
        pre_best_lp = [0.0] * (n + 1)
        pre_best_lo = [0.0] * (n + 1)
        for i in range(n):
            pre_best_lp[i + 1] = pre_best_lp[i] + best_lp[i]
            pre_best_lo[i + 1] = pre_best_lo[i] + best_lo[i]

        # Seuils en log, corrigés du malus de corrélation (le malus réduit la
        # probabilité finale, la somme des log(p) doit donc viser plus haut).
        log_min_prob = -math.inf
        if min_prob > 0.0:
            log_min_prob = math.log(min_prob)
            if self.haircut > 0.0 and k > 1:
                log_min_prob -= (k - 1) * math.log(1.0 - self.haircut)
        log_min_payout = math.log(min_payout) if min_payout > 1.0 else -math.inf

        # Tas-min des top candidats : (poids, tiebreak, indices d'origine).
        heap: list[tuple[float, int, tuple[int, ...]]] = []
        counter = itertools.count()
        chosen: list[int] = []

        def dfs(start: int, r: int, sum_w: float, sum_lp: float, sum_lo: float) -> None:
            stats.nodes_visited += 1
            if r == 0:
                # Contraintes exactes à la feuille : un combiné infaisable ne
                # doit pas entrer dans le tas (il évincerait des candidats
                # faisables avant d'être filtré au reclassement final).
                if sum_lp < log_min_prob or sum_lo < log_min_payout:
                    return
                item = (sum_w, next(counter), tuple(order[j] for j in chosen))
                if len(heap) < top:
                    heapq.heappush(heap, item)
                else:
                    heapq.heappushpop(heap, item)
                return
            # Bornes de faisabilité : contraintes inatteignables depuis ce nœud.
            if sum_lp + pre_best_lp[r] < log_min_prob:
                return
            if sum_lo + pre_best_lo[r] < log_min_payout:
                return
            for j in range(start, n - r + 1):
                # Borne d'optimalité : la meilleure complétion depuis j est la
                # tranche w[j..j+r-1] ; les poids étant triés décroissants, si
                # elle échoue ici, elle échoue pour toutes les positions > j.
                if len(heap) == top and sum_w + (pre_w[j + r] - pre_w[j]) <= heap[0][0]:
                    break
                # Exclusivité : au plus une jambe par marché.
                if any(mid[c] == mid[j] for c in chosen):
                    continue
                chosen.append(j)
                dfs(j + 1, r - 1, sum_w + w[j], sum_lp + lp[j], sum_lo + lo[j])
                chosen.pop()

        dfs(0, k, 0.0, 0.0, 0.0)
        return [indices for _, _, indices in heap]
