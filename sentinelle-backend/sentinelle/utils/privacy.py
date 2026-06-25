"""Outils de confidentialité.

Sentinelle traite des données sensibles (numéros de téléphone, messages). Par
respect de la vie privée et pour limiter la surface en cas de fuite, on ne
stocke jamais un numéro de téléphone en clair dans la base communautaire : on
conserve un condensé (hash) salé. Les numéros restent toutefois consultables
fonctionnellement car le hash est déterministe pour un même sel.
"""

from __future__ import annotations

import hashlib
import os
import re

# Sel d'application. En production, surcharger via SENTINELLE_SECRET_KEY pour que
# les condensés ne soient pas devinables à partir d'une rainbow table publique.
_SALT = os.getenv("SENTINELLE_SECRET_KEY", "dev-secret-change-me")

_NON_DIGITS = re.compile(r"[^\d+]")


def normalize_phone(raw: str, default_country_code: str = "1") -> str:
    """Normalise un numéro nord-américain vers le format E.164 (best effort).

    Exemples :
        '(514) 555-0199'  -> '+15145550199'
        '514-555-0199'    -> '+15145550199'
        '1 514 555 0199'  -> '+15145550199'
    """
    if not raw:
        return ""
    cleaned = _NON_DIGITS.sub("", raw.strip())
    if cleaned.startswith("+"):
        return cleaned
    digits = cleaned.lstrip("+")
    if len(digits) == 10:  # numéro local nord-américain
        return f"+{default_country_code}{digits}"
    if len(digits) == 11 and digits.startswith(default_country_code):
        return f"+{digits}"
    # Numéro court (shortcode) ou format inconnu : renvoyer tel quel, sans '+'.
    return digits


def hash_phone(raw: str) -> str:
    """Renvoie un condensé salé et déterministe d'un numéro de téléphone."""
    normalized = normalize_phone(raw)
    if not normalized:
        return ""
    digest = hashlib.sha256(f"{_SALT}:{normalized}".encode("utf-8")).hexdigest()
    return digest


def mask_phone(raw: str) -> str:
    """Renvoie une forme masquée d'un numéro, sûre à afficher / journaliser.

    Exemple : '+15145550199' -> '+1514***0199'
    """
    normalized = normalize_phone(raw)
    if not normalized or len(normalized) < 7:
        return "***"
    return normalized[:5] + "***" + normalized[-4:]


def hash_text(text: str) -> str:
    """Condensé d'un contenu (sert à dédupliquer des signalements identiques
    sans stocker le texte intégral)."""
    if not text:
        return ""
    return hashlib.sha256(f"{_SALT}:{text.strip().lower()}".encode("utf-8")).hexdigest()
