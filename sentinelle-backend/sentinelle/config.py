"""Configuration centrale de Sentinelle.

Tous les réglages sont surchargeables par variables d'environnement afin de
faciliter le déploiement (Docker, AWS, etc.). Voir `.env.example`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "oui"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Config:
    """Réglages applicatifs, surchargeables via l'environnement."""

    # --- Général -----------------------------------------------------------
    env: str = field(default_factory=lambda: os.getenv("SENTINELLE_ENV", "development"))
    debug: bool = field(default_factory=lambda: _env_bool("SENTINELLE_DEBUG", False))
    secret_key: str = field(
        default_factory=lambda: os.getenv("SENTINELLE_SECRET_KEY", "dev-secret-change-me")
    )

    # --- Base de données ---------------------------------------------------
    # Chemin du fichier SQLite (la communauté : signalements, listes de blocage).
    database_path: str = field(
        default_factory=lambda: os.getenv(
            "SENTINELLE_DB_PATH", str(PROJECT_ROOT / "data" / "sentinelle.db")
        )
    )

    # --- Modèle d'apprentissage automatique -------------------------------
    model_path: str = field(
        default_factory=lambda: os.getenv(
            "SENTINELLE_MODEL_PATH", str(PROJECT_ROOT / "data" / "model.joblib")
        )
    )
    # Poids du classifieur ML dans le score combiné (le reste = heuristiques/URL).
    ml_weight: float = field(
        default_factory=lambda: float(os.getenv("SENTINELLE_ML_WEIGHT", "0.45"))
    )

    # --- Détection ---------------------------------------------------------
    # Nombre de signalements indépendants avant blocage communautaire automatique.
    community_block_threshold: int = field(
        default_factory=lambda: _env_int("SENTINELLE_BLOCK_THRESHOLD", 3)
    )

    # --- API ---------------------------------------------------------------
    api_key: str | None = field(default_factory=lambda: os.getenv("SENTINELLE_API_KEY") or None)
    # Origine CORS autorisée. En production, restreindre à l'origine de la console/app
    # (ex. https://console.sentinelle.ca) au lieu de « * ».
    cors_origin: str = field(default_factory=lambda: os.getenv("SENTINELLE_CORS_ORIGIN", "*"))
    # Limite de débit (requêtes/minute par IP) ; 0 = désactivé.
    rate_limit_per_minute: int = field(
        default_factory=lambda: _env_int("SENTINELLE_RATE_LIMIT", 120)
    )
    max_message_length: int = field(
        default_factory=lambda: _env_int("SENTINELLE_MAX_MESSAGE_LENGTH", 4000)
    )

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}

    def ensure_directories(self) -> None:
        """Crée les dossiers de données nécessaires s'ils n'existent pas."""
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    """Construit la configuration à partir de l'environnement."""
    cfg = Config()
    cfg.ensure_directories()
    return cfg
