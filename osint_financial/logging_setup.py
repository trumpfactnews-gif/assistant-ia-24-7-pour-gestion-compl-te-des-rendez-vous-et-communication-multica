"""Journalisation avec expurgation des secrets.

Faille corrigée : l'original imprimait librement et n'avait aucun filtre. Un
jeton Telegram dans une URL (``https://api.telegram.org/bot<TOKEN>/...``) ou une
clé ``Authorization: Bearer sk-...`` se retrouvait en clair dans la sortie, les
logs CI et les rapports d'erreur.

Ce module installe un filtre qui masque les motifs de secrets connus **et**
toute valeur enregistrée via :func:`register_secret`.
"""

from __future__ import annotations

import logging
import re
import sys

_REDACTED = "«expurgé»"

# Motifs génériques : jeton Telegram, clés « sk-... », en-tête Authorization.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"bot\d{6,}:[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"(?i)(authorization|api[_-]?key|token)\s*[:=]\s*\S+"),
]

_registered: set[str] = set()


def register_secret(value: str | None) -> None:
    """Déclare une valeur à masquer partout dans les logs."""
    if value and len(value) >= 8:
        _registered.add(value)


def redact(text: str) -> str:
    """Retourne ``text`` avec les secrets connus remplacés."""
    for secret in _registered:
        if secret in text:
            text = text.replace(secret, _REDACTED)
    for pattern in _PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - formatage exotique
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg = cleaned
            record.args = ()
        return True


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure le logger racine du paquet (idempotent)."""
    logger = logging.getLogger("osint")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
        handler.addFilter(_RedactingFilter())
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str = "osint") -> logging.Logger:
    return logging.getLogger(name)
