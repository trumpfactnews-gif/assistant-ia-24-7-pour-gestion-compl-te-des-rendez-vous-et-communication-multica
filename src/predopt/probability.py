"""Calcul de probabilités : prix implicites, dé-vig, pondération statistique.

Chaîne de traitement pour chaque marché :

1. **Probabilité implicite** — le prix d'un contrat est une probabilité brute,
   mais la somme des prix d'un marché dépasse souvent 1 (marge / « vig » de la
   plateforme, spread des carnets d'ordres).
2. **Dé-vig** — on retire cette marge pour obtenir des probabilités qui
   somment à 1 (méthode proportionnelle ou méthode de la puissance, moins
   biaisée pour les issues extrêmes).
3. **Pondération statistique** — on fusionne la probabilité de marché avec
   une estimation externe (modèle, historique) :
   - lissage bayésien Beta des fréquences historiques,
   - mélange en log-odds pondéré par la quantité d'information disponible.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

# Bornes de sécurité pour éviter log(0) et les probabilités dégénérées.
_EPS = 1e-9


def clamp_prob(p: float, eps: float = 1e-6) -> float:
    """Contraint une probabilité dans [eps, 1-eps]."""
    return min(max(p, eps), 1.0 - eps)


def implied_probs(prices: Sequence[float]) -> list[float]:
    """Probabilités implicites brutes (= prix), avant dé-vig."""
    if any(not (0.0 < p < 1.0) for p in prices):
        raise ValueError("chaque prix doit être dans ]0,1[")
    return list(prices)


def overround(prices: Sequence[float]) -> float:
    """Marge du marché : somme des prix − 1 (0 ⇒ marché sans marge)."""
    return sum(prices) - 1.0


def devig_proportional(prices: Sequence[float]) -> list[float]:
    """Dé-vig proportionnel : normalise les prix pour qu'ils somment à 1.

    Méthode standard, exacte quand la marge est répartie uniformément.
    """
    probs = implied_probs(prices)
    total = sum(probs)
    if total <= 0:
        raise ValueError("somme des prix nulle ou négative")
    return [p / total for p in probs]


def devig_power(prices: Sequence[float], tol: float = 1e-10, max_iter: int = 200) -> list[float]:
    """Dé-vig « power » : trouve k tel que Σ p_i^k = 1.

    Corrige le biais favori/outsider mieux que la normalisation
    proportionnelle : la marge est retirée davantage des issues improbables,
    ce qui reflète le biais longshot observé empiriquement sur les marchés.
    Résolution par dichotomie sur k (Σ p^k est décroissante en k).
    """
    probs = implied_probs(prices)
    total = sum(probs)
    if abs(total - 1.0) < tol:
        return probs
    # Σ p^k = 1 : k > 1 si la somme dépasse 1, k < 1 sinon.
    lo, hi = (1.0, 64.0) if total > 1.0 else (1e-6, 1.0)

    def s(k: float) -> float:
        return sum(p ** k for p in probs)

    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if s(mid) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    k = (lo + hi) / 2.0
    out = [p ** k for p in probs]
    norm = sum(out)  # micro-renormalisation résiduelle
    return [p / norm for p in out]


def devig(prices: Sequence[float], method: str = "power") -> list[float]:
    """Retire la marge du marché. ``method`` ∈ {"proportional", "power"}."""
    if method == "proportional":
        return devig_proportional(prices)
    if method == "power":
        return devig_power(prices)
    raise ValueError(f"méthode de dé-vig inconnue : {method}")


def beta_shrink(
    wins: float,
    trials: float,
    prior_prob: float,
    prior_strength: float = 10.0,
) -> float:
    """Lissage bayésien Beta d'une fréquence historique.

    Le prior Beta(a, b) est centré sur ``prior_prob`` (typiquement la
    probabilité de marché dé-viggée) avec un poids équivalent à
    ``prior_strength`` observations. Avec peu de données, l'estimation reste
    proche du marché ; avec beaucoup, elle converge vers la fréquence
    observée. Évite les probabilités 0/1 absurdes des petits échantillons.
    """
    if trials < 0 or not (0 <= wins <= trials):
        raise ValueError("wins/trials incohérents")
    prior_prob = clamp_prob(prior_prob)
    a = prior_prob * prior_strength
    b = (1.0 - prior_prob) * prior_strength
    return (wins + a) / (trials + a + b)


def blend_log_odds(p_market: float, p_model: float, model_weight: float) -> float:
    """Mélange deux probabilités en log-odds, pondéré par ``model_weight`` ∈ [0,1].

    Le mélange en log-odds (plutôt qu'en probabilité) est cohérent avec
    l'agrégation d'experts et se comporte bien près de 0 et 1.
    """
    if not (0.0 <= model_weight <= 1.0):
        raise ValueError("model_weight doit être dans [0,1]")
    p_market = clamp_prob(p_market)
    p_model = clamp_prob(p_model)
    lo_market = math.log(p_market / (1.0 - p_market))
    lo_model = math.log(p_model / (1.0 - p_model))
    lo = (1.0 - model_weight) * lo_market + model_weight * lo_model
    return 1.0 / (1.0 + math.exp(-lo))


def estimate_outcome_prob(
    p_devig: float,
    model_prob: Optional[float] = None,
    hist_wins: Optional[float] = None,
    hist_trials: Optional[float] = None,
    model_weight: float = 0.5,
    hist_prior_strength: float = 10.0,
) -> float:
    """Probabilité finale d'une issue : marché ⊕ modèle ⊕ historique.

    1. Point de départ : probabilité de marché dé-viggée ``p_devig``.
    2. Si des données historiques existent, on calcule leur estimation
       lissée (prior = marché) et on la fusionne avec un poids croissant
       en fonction du volume d'observations : w = n / (n + prior_strength).
    3. Si une probabilité de modèle existe, fusion en log-odds avec
       ``model_weight``.
    """
    p = clamp_prob(p_devig)
    if hist_trials is not None and hist_wins is not None and hist_trials > 0:
        p_hist = beta_shrink(hist_wins, hist_trials, p, hist_prior_strength)
        w_hist = hist_trials / (hist_trials + hist_prior_strength)
        p = blend_log_odds(p, p_hist, w_hist)
    if model_prob is not None:
        p = blend_log_odds(p, model_prob, model_weight)
    return clamp_prob(p)


def correlation_haircut(joint_prob: float, n_legs: int, haircut: float) -> float:
    """Malus de corrélation heuristique sur la probabilité jointe d'un combiné.

    Les métriques de combiné supposent l'indépendance des jambes ; en
    pratique des marchés d'une même catégorie peuvent être corrélés
    négativement pour le parieur (surestimation de la probabilité jointe).
    On applique p' = p × (1 − haircut)^(n−1), pénalité nulle pour un pari
    simple et croissante avec le nombre de jambes.
    """
    if not (0.0 <= haircut < 1.0):
        raise ValueError("haircut doit être dans [0,1[")
    if n_legs <= 1 or haircut == 0.0:
        return joint_prob
    return max(joint_prob * (1.0 - haircut) ** (n_legs - 1), _EPS)
