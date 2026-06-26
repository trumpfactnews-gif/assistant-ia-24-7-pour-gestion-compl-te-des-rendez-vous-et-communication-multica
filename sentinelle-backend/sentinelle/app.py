"""Fabrique d'application Flask (application factory)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from flask import Flask, jsonify, request

from .config import Config, load_config
from .db import Repository
from .detection import DetectionEngine
from .detection.classifier import FraudClassifier
from .api.errors import APIError, register_error_handlers
from .api.routes import bp as api_bp


class _RateLimiter:
    """Limiteur de débit à fenêtre glissante, en mémoire (par IP).

    Convient à un nœud unique. À l'échelle horizontale, remplacer par un magasin
    partagé (Redis). Volontairement simple et sans dépendance.
    """

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        window_start = now - 60.0
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < window_start:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False
            hits.append(now)
            return True


def create_app(config: Config | None = None) -> Flask:
    cfg = config or load_config()
    app = Flask(__name__)
    app.config["SENTINELLE_CONFIG"] = cfg

    # --- Dépendances applicatives ----------------------------------------
    repository = Repository(cfg.database_path, cfg.community_block_threshold)
    repository.init()
    classifier = FraudClassifier(cfg.model_path)
    engine = DetectionEngine(classifier, community=repository, ml_weight=cfg.ml_weight)

    app.config["REPOSITORY"] = repository
    app.config["ENGINE"] = engine

    limiter = _RateLimiter(cfg.rate_limit_per_minute)

    # --- Garde-fous (auth, débit, CORS) ----------------------------------
    @app.before_request
    def _guard():
        # Préflight CORS : répondre immédiatement.
        if request.method == "OPTIONS":
            return ("", 204)

        path = request.path
        if not path.startswith("/api/"):
            return None  # /health et hors-API : pas de garde

        # Clé d'API (si configurée).
        if cfg.api_key:
            provided = request.headers.get("X-API-Key", "")
            if provided != cfg.api_key:
                raise APIError("Clé d'API invalide ou manquante.", 401, "unauthorized")

        # Limitation de débit.
        client = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        client = client.split(",")[0].strip()
        if not limiter.allow(client):
            raise APIError("Trop de requêtes, réessayez dans une minute.", 429, "rate_limited")
        return None

    @app.after_request
    def _cors(response):
        response.headers.setdefault("Access-Control-Allow-Origin", cfg.cors_origin)
        response.headers.setdefault(
            "Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        response.headers.setdefault(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        return response

    # --- Enregistrement ---------------------------------------------------
    register_error_handlers(app)
    app.register_blueprint(api_bp)

    @app.get("/")
    def _index():
        return jsonify({
            "service": "Sentinelle API",
            "description": "Détection de fraude par SMS pour les citoyens canadiens",
            "version": "v1",
            "endpoints": [
                "GET  /health",
                "POST /api/v1/analyze",
                "POST /api/v1/report",
                "GET  /api/v1/check-number?number=...",
                "POST /api/v1/check-url",
                "GET  /api/v1/stats",
            ],
        })

    return app
