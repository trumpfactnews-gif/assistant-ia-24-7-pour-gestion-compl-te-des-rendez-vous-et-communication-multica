"""Modèles de données : marchés prédictifs, issues et jambes de pari.

Un *marché* (Market) est une question posée sur une plateforme de prédiction
(ex. Polymarket) avec plusieurs *issues* (Outcome) achetables. Chaque issue
possède un prix entre 0 et 1 qui représente la probabilité implicite du marché.

Une *jambe* (Leg) est une issue candidate à un pari, enrichie de la probabilité
estimée par le modèle (après dé-vig et pondération statistique) et de sa cote
décimale. Les combinés (parlays) assemblent plusieurs jambes de marchés
distincts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MarketType(str, Enum):
    """Type de marché prédictif."""

    BINARY = "binary"          # Oui / Non
    CATEGORICAL = "categorical"  # Multi-options (élections, vainqueur d'un tournoi…)


@dataclass(frozen=True)
class Outcome:
    """Une issue achetable d'un marché.

    Attributes:
        name: libellé de l'issue (ex. "Oui", "Candidat A").
        price: prix du contrat sur la plateforme, dans ]0, 1[.
            Sur Polymarket, un contrat payé 1 $ si l'issue se réalise.
        model_prob: probabilité estimée par une source externe (modèle,
            expert, sondage). Optionnelle.
        hist_wins: nombre de succès observés dans les données historiques
            pour des situations comparables. Optionnel.
        hist_trials: nombre d'observations historiques comparables. Optionnel.
    """

    name: str
    price: float
    model_prob: Optional[float] = None
    hist_wins: Optional[float] = None
    hist_trials: Optional[float] = None

    def __post_init__(self) -> None:
        if not (0.0 < self.price < 1.0):
            raise ValueError(f"price doit être dans ]0,1[, reçu {self.price}")
        if self.model_prob is not None and not (0.0 < self.model_prob < 1.0):
            raise ValueError(f"model_prob doit être dans ]0,1[, reçu {self.model_prob}")
        if (self.hist_wins is None) != (self.hist_trials is None):
            raise ValueError("hist_wins et hist_trials doivent être fournis ensemble")
        if self.hist_trials is not None:
            if self.hist_trials <= 0 or not (0 <= self.hist_wins <= self.hist_trials):
                raise ValueError("données historiques incohérentes")


@dataclass(frozen=True)
class Market:
    """Un marché prédictif avec ses issues."""

    id: str
    question: str
    type: MarketType
    outcomes: tuple[Outcome, ...]
    category: str = "general"
    liquidity: Optional[float] = None

    def __post_init__(self) -> None:
        if len(self.outcomes) < 2:
            raise ValueError(f"marché {self.id}: au moins 2 issues requises")
        if self.type is MarketType.BINARY and len(self.outcomes) != 2:
            raise ValueError(f"marché {self.id}: un marché binaire a exactement 2 issues")
        names = [o.name for o in self.outcomes]
        if len(set(names)) != len(names):
            raise ValueError(f"marché {self.id}: issues en double")


@dataclass(frozen=True)
class Leg:
    """Une jambe de pari : une issue d'un marché, prête à être combinée.

    Attributes:
        market_id: identifiant du marché d'origine.
        market_question: question du marché (pour l'affichage).
        outcome: libellé de l'issue pariée.
        category: catégorie du marché (sert au malus de corrélation).
        prob: probabilité de gain estimée (après dé-vig + pondération).
        odds: cote décimale (payout brut par unité misée) = 1 / prix.
        price: prix d'achat du contrat sur la plateforme.
    """

    market_id: str
    market_question: str
    outcome: str
    category: str
    prob: float
    odds: float
    price: float

    def __post_init__(self) -> None:
        if not (0.0 < self.prob < 1.0):
            raise ValueError(f"prob doit être dans ]0,1[, reçu {self.prob}")
        if self.odds <= 1.0:
            raise ValueError(f"odds doit être > 1, reçu {self.odds}")

    @property
    def ev(self) -> float:
        """Espérance de gain par unité misée : p·cote − 1."""
        return self.prob * self.odds - 1.0

    @property
    def log_prob(self) -> float:
        return math.log(self.prob)

    @property
    def log_odds(self) -> float:
        return math.log(self.odds)

    @property
    def log_ev_factor(self) -> float:
        """log(p·cote) — additive sur les jambes d'un combiné indépendant."""
        return math.log(self.prob * self.odds)

    def label(self) -> str:
        return f"{self.market_question} → {self.outcome}"


@dataclass
class Combo:
    """Un combiné (parlay) de 1 à N jambes de marchés distincts.

    Toutes les métriques supposent les jambes indépendantes, éventuellement
    corrigées par un malus de corrélation appliqué en amont sur ``prob``.
    """

    legs: tuple[Leg, ...]
    prob: float          # probabilité que TOUTES les jambes gagnent
    payout: float        # cote décimale combinée (produit des cotes)
    ev: float            # espérance par unité misée : prob·payout − 1
    variance: float      # variance du gain net par unité misée
    sharpe: float        # EV / écart-type (ratio rendement/risque)
    kelly: float         # fraction de Kelly optimale de la bankroll
    score: float = 0.0   # score utilisé pour le classement
    rank: int = 0
    extras: dict = field(default_factory=dict)

    @property
    def n_legs(self) -> int:
        return len(self.legs)

    @property
    def gain_net(self) -> float:
        """Gain net par unité misée en cas de victoire."""
        return self.payout - 1.0
