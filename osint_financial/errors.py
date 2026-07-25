"""Hiérarchie d'exceptions.

Le script d'origine n'avait aucune gestion d'erreur : la moindre coupure réseau
remontait une trace complète (avec URL et parfois jeton) et laissait des états
partiels sur disque. Ici chaque couche lève une erreur typée, et la CLI décide
seule de ce qui est fatal.
"""

from __future__ import annotations


class OsintError(Exception):
    """Erreur de base du paquet."""


class ConfigError(OsintError):
    """Configuration absente ou invalide (clé, chemin, User-Agent SEC)."""


class ValidationError(OsintError):
    """Entrée utilisateur refusée (ticker, chemin, URL)."""


class HttpError(OsintError):
    """Échec réseau après épuisement des tentatives."""


class SecurityError(OsintError):
    """Violation d'une contrainte de sécurité (hôte hors allowlist, quota, ...)."""


class DataUnavailable(OsintError):
    """Source interrogée avec succès mais sans donnée exploitable."""
