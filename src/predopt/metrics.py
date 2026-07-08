"""Métriques de rentabilité et de risque d'un pari ou d'un combiné.

Toutes les métriques sont exprimées **par unité misée** (mise = 1) :

- gain net en cas de victoire : ``payout − 1`` ;
- perte en cas de défaite : ``−1`` ;
- espérance (EV) : ``p·payout − 1`` ;
- variance : ``p·(1−p)·payout²`` ;
- ratio de Sharpe (par pari) : ``EV / écart-type`` ;
- critère de Kelly : fraction de bankroll qui maximise la croissance
  logarithmique espérée, ``f* = (p·payout − 1) / (payout − 1)``.
"""

from __future__ import annotations

import math
from typing import Sequence

from .models import Combo, Leg
from .probability import correlation_haircut


def expected_value(prob: float, payout: float) -> float:
    """Espérance de gain net par unité misée."""
    return prob * payout - 1.0


def variance(prob: float, payout: float) -> float:
    """Variance du gain net par unité misée (loi de Bernoulli mise à l'échelle)."""
    return prob * (1.0 - prob) * payout * payout


def sharpe_ratio(prob: float, payout: float) -> float:
    """EV / écart-type. 0 si la variance est nulle."""
    var = variance(prob, payout)
    if var <= 0.0:
        return 0.0
    return expected_value(prob, payout) / math.sqrt(var)


def kelly_fraction(prob: float, payout: float, cap: float = 1.0) -> float:
    """Fraction de Kelly f* = EV / (payout − 1), bornée à [0, cap].

    Négative (donc 0 après borne) si le pari a une EV négative : on ne mise pas.
    """
    b = payout - 1.0
    if b <= 0.0:
        return 0.0
    f = expected_value(prob, payout) / b
    return min(max(f, 0.0), cap)


def expected_log_growth(prob: float, payout: float, fraction: float) -> float:
    """Croissance logarithmique espérée de la bankroll en misant ``fraction``.

    E[log(1 + f·X)] avec X = gain net par unité. Maximisée en f = Kelly.
    """
    if fraction <= 0.0:
        return 0.0
    if fraction >= 1.0:
        return -math.inf  # tout perdre est possible ⇒ croissance log = −∞
    b = payout - 1.0
    return prob * math.log(1.0 + fraction * b) + (1.0 - prob) * math.log(1.0 - fraction)


def build_combo(
    legs: Sequence[Leg],
    haircut: float = 0.0,
    kelly_cap: float = 1.0,
) -> Combo:
    """Construit un :class:`Combo` avec toutes ses métriques.

    Hypothèse d'indépendance entre jambes, corrigée par un éventuel
    malus de corrélation ``haircut`` (voir :func:`correlation_haircut`).
    """
    if not legs:
        raise ValueError("un combiné doit avoir au moins une jambe")
    markets = {leg.market_id for leg in legs}
    if len(markets) != len(legs):
        raise ValueError("un combiné ne peut pas contenir deux jambes du même marché")

    log_p = sum(leg.log_prob for leg in legs)
    log_o = sum(leg.log_odds for leg in legs)
    prob = correlation_haircut(math.exp(log_p), len(legs), haircut)
    payout = math.exp(log_o)
    ev = expected_value(prob, payout)
    var = variance(prob, payout)
    return Combo(
        legs=tuple(legs),
        prob=prob,
        payout=payout,
        ev=ev,
        variance=var,
        sharpe=sharpe_ratio(prob, payout),
        kelly=kelly_fraction(prob, payout, cap=kelly_cap),
    )


def combo_score(combo: Combo, objective: str = "ev") -> float:
    """Score de classement d'un combiné selon l'objectif choisi.

    - ``ev``      : espérance de gain pure (agressif).
    - ``sharpe``  : rendement ajusté du risque (équilibré).
    - ``log_growth`` : croissance log espérée à Kelly fractionné 50 %
      (croissance de bankroll à long terme, prudent).
    - ``prob``    : probabilité de victoire (très prudent, ignore la cote).
    """
    if objective == "ev":
        return combo.ev
    if objective == "sharpe":
        return combo.sharpe
    if objective == "log_growth":
        return expected_log_growth(combo.prob, combo.payout, 0.5 * combo.kelly)
    if objective == "prob":
        return combo.prob
    raise ValueError(f"objectif inconnu : {objective}")
