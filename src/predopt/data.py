"""Chargement des marchés (JSON) et génération de jeux de données d'exemple.

Format d'entrée JSON::

    {
      "markets": [
        {
          "id": "us-recession-2026",
          "question": "Récession aux USA avant fin 2026 ?",
          "type": "binary",
          "category": "economie",
          "outcomes": [
            {"name": "Oui", "price": 0.32, "model_prob": 0.38,
             "hist_wins": 12, "hist_trials": 40},
            {"name": "Non", "price": 0.70}
          ]
        }
      ]
    }

Les champs ``model_prob``, ``hist_wins``/``hist_trials``, ``category`` et
``liquidity`` sont optionnels. La somme des prix d'un marché peut dépasser 1 :
c'est la marge (vig), retirée par le dé-vig.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional, Sequence

from .models import Leg, Market, MarketType, Outcome
from .probability import devig, estimate_outcome_prob

_CATEGORIES = ("politique", "crypto", "sport", "economie", "science", "culture")


def load_markets(path: str | Path) -> list[Market]:
    """Charge une liste de marchés depuis un fichier JSON."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    markets_raw = raw["markets"] if isinstance(raw, dict) else raw
    markets = []
    for m in markets_raw:
        outcomes = tuple(
            Outcome(
                name=o["name"],
                price=float(o["price"]),
                model_prob=o.get("model_prob"),
                hist_wins=o.get("hist_wins"),
                hist_trials=o.get("hist_trials"),
            )
            for o in m["outcomes"]
        )
        markets.append(
            Market(
                id=str(m["id"]),
                question=m.get("question", str(m["id"])),
                type=MarketType(m.get("type", "binary")),
                outcomes=outcomes,
                category=m.get("category", "general"),
                liquidity=m.get("liquidity"),
            )
        )
    return markets


def save_markets(markets: Sequence[Market], path: str | Path) -> None:
    """Sérialise des marchés au format JSON d'entrée."""
    payload = {
        "markets": [
            {
                "id": m.id,
                "question": m.question,
                "type": m.type.value,
                "category": m.category,
                **({"liquidity": m.liquidity} if m.liquidity is not None else {}),
                "outcomes": [
                    {
                        "name": o.name,
                        "price": round(o.price, 6),
                        **({"model_prob": round(o.model_prob, 6)} if o.model_prob is not None else {}),
                        **(
                            {"hist_wins": o.hist_wins, "hist_trials": o.hist_trials}
                            if o.hist_trials is not None
                            else {}
                        ),
                    }
                    for o in m.outcomes
                ],
            }
            for m in markets
        ]
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def markets_to_legs(
    markets: Sequence[Market],
    devig_method: str = "power",
    model_weight: float = 0.5,
    hist_prior_strength: float = 10.0,
    min_leg_ev: Optional[float] = None,
    max_odds: Optional[float] = None,
) -> list[Leg]:
    """Transforme les marchés en jambes candidates prêtes pour le moteur.

    Pour chaque marché : dé-vig des prix, puis estimation de la probabilité
    finale de chaque issue (marché ⊕ historique ⊕ modèle). Chaque issue
    devient une jambe de cote décimale 1/prix.

    Args:
        min_leg_ev: si fourni, ne garde que les jambes dont l'EV unitaire
            dépasse ce seuil (ex. 0.0 = jambes à espérance positive).
        max_odds: si fourni, écarte les cotes extrêmes (contrats < 1/max_odds,
            souvent illiquides et mal calibrés).
    """
    legs: list[Leg] = []
    for market in markets:
        prices = [o.price for o in market.outcomes]
        devigged = devig(prices, method=devig_method)
        for outcome, p_devig in zip(market.outcomes, devigged):
            prob = estimate_outcome_prob(
                p_devig,
                model_prob=outcome.model_prob,
                hist_wins=outcome.hist_wins,
                hist_trials=outcome.hist_trials,
                model_weight=model_weight,
                hist_prior_strength=hist_prior_strength,
            )
            odds = 1.0 / outcome.price
            if odds <= 1.0:
                continue  # prix ≥ 1 impossible par validation, garde-fou
            if max_odds is not None and odds > max_odds:
                continue
            leg = Leg(
                market_id=market.id,
                market_question=market.question,
                outcome=outcome.name,
                category=market.category,
                prob=prob,
                odds=odds,
                price=outcome.price,
            )
            if min_leg_ev is not None and leg.ev < min_leg_ev:
                continue
            legs.append(leg)
    return legs


def generate_sample_markets(
    n_markets: int = 50,
    seed: int = 42,
    vig: float = 0.02,
    edge_noise: float = 0.08,
    categorical_share: float = 0.3,
) -> list[Market]:
    """Génère un univers de marchés synthétiques réaliste (reproductible).

    Chaque marché possède une « vraie » probabilité cachée ; le prix affiché
    s'en écarte d'un bruit (l'inefficience que l'outil doit détecter) et
    inclut une marge ``vig``. Une partie des marchés reçoit une estimation
    de modèle et des données historiques corrélées à la vraie probabilité.
    """
    rng = random.Random(seed)
    markets: list[Market] = []
    for i in range(n_markets):
        category = rng.choice(_CATEGORIES)
        is_categorical = rng.random() < categorical_share
        n_out = rng.randint(3, 6) if is_categorical else 2

        # Vraies probabilités cachées (Dirichlet via gammas normalisées).
        raws = [rng.gammavariate(1.5, 1.0) for _ in range(n_out)]
        total = sum(raws)
        true_probs = [max(min(r / total, 0.97), 0.03) for r in raws]
        norm = sum(true_probs)
        true_probs = [p / norm for p in true_probs]

        outcomes = []
        for j, p_true in enumerate(true_probs):
            # Prix = vraie prob ± bruit (inefficience) + marge répartie.
            noise = rng.gauss(0.0, edge_noise * p_true * (1.0 - p_true) * 4.0)
            price = min(max(p_true + noise, 0.01), 0.99)
            price = min(max(price * (1.0 + vig), 0.01), 0.99)

            model_prob = None
            if rng.random() < 0.5:
                # Estimation de modèle : bruitée mais centrée sur la vérité.
                mp = p_true + rng.gauss(0.0, 0.04)
                model_prob = min(max(mp, 0.01), 0.99)

            hist_wins = hist_trials = None
            if rng.random() < 0.4:
                hist_trials = rng.randint(10, 300)
                hist_wins = sum(1 for _ in range(hist_trials) if rng.random() < p_true)

            outcomes.append(
                Outcome(
                    name=f"Option {chr(65 + j)}" if is_categorical else ("Oui" if j == 0 else "Non"),
                    price=price,
                    model_prob=model_prob,
                    hist_wins=hist_wins,
                    hist_trials=hist_trials,
                )
            )
        markets.append(
            Market(
                id=f"mkt-{i:04d}",
                question=f"Marché {category} n°{i} se réalise ?",
                type=MarketType.CATEGORICAL if is_categorical else MarketType.BINARY,
                outcomes=tuple(outcomes),
                category=category,
                liquidity=round(rng.uniform(1_000, 500_000), 2),
            )
        )
    return markets
