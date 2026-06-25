"""Détection heuristique à base de règles.

Applique les règles de `patterns.py` à un message et produit :
* une liste de signaux déclenchés ;
* un score heuristique (0..100) ;
* la catégorie d'arnaque la plus probable.

Les heuristiques sont rapides, explicables et fonctionnent sans modèle entraîné.
Elles constituent le socle ; le classifieur ML vient ensuite affiner le score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .patterns import RULES, Rule

# Détection d'une LIVRAISON de code à usage unique légitime (≠ demande de code).
# Un SMS qui *fournit* un code et dit de *ne pas le partager* est l'inverse d'un
# hameçonnage : on neutralise alors le signal « demande d'identifiants ».
_OTP_DELIVERED = re.compile(
    r"(?:votre |your )?(?:code|otp|nip|mot de passe).{0,25}?(?:est|is|:)\s*\d{4,8}",
    re.IGNORECASE,
)
_DONT_SHARE = re.compile(
    r"ne (?:le |les )?(?:partagez|communiquez|divulguez)|"
    r"do(?:n't| not) share|never share",
    re.IGNORECASE,
)


@dataclass
class HeuristicSignal:
    code: str
    category: str
    weight: float
    label: dict
    evidence: str


@dataclass
class HeuristicResult:
    score: int  # 0..100
    category: str  # meilleure catégorie ou "none"
    signals: list[HeuristicSignal]


def _match(rule: Rule, text: str) -> HeuristicSignal | None:
    m = rule.regex.search(text)
    if not m:
        return None
    evidence = m.group(0).strip()
    return HeuristicSignal(
        code=rule.code,
        category=rule.category,
        weight=rule.weight,
        label=rule.label,
        evidence=evidence,
    )


def _combine(weights: list[float]) -> int:
    """Combine des poids [0,1] en un score [0,100].

    On utilise une combinaison probabiliste « bruyant-OU » (noisy-OR) :
    chaque signal réduit la probabilité d'innocence. Ainsi, plusieurs signaux
    faibles s'accumulent sans jamais dépasser 100, et un signal fort domine.
    """
    prob_innocent = 1.0
    for w in weights:
        prob_innocent *= (1.0 - min(max(w, 0.0), 0.99))
    return round((1.0 - prob_innocent) * 100)


def evaluate(text: str) -> HeuristicResult:
    """Évalue un message texte et renvoie le résultat heuristique."""
    if not text or not text.strip():
        return HeuristicResult(score=0, category="none", signals=[])

    signals: list[HeuristicSignal] = []
    for rule in RULES:
        sig = _match(rule, text)
        if sig is not None:
            signals.append(sig)

    # Livraison d'OTP légitime : on retire le faux signal « demande d'identifiants ».
    if _OTP_DELIVERED.search(text) and _DONT_SHARE.search(text):
        signals = [s for s in signals if s.code != "credential_request"]

    if not signals:
        return HeuristicResult(score=0, category="none", signals=[])

    score = _combine([s.weight for s in signals])

    # Catégorie : celle dont les signaux spécifiques cumulent le plus de poids.
    category_weights: dict[str, float] = {}
    for s in signals:
        if s.category != "generic":
            category_weights[s.category] = category_weights.get(s.category, 0.0) + s.weight
    category = max(category_weights, key=category_weights.get) if category_weights else "none"

    return HeuristicResult(score=score, category=category, signals=signals)
