"""Gestion centralisée des erreurs de l'API."""

from __future__ import annotations

from flask import Flask, jsonify


class APIError(Exception):
    """Erreur applicative renvoyée proprement en JSON."""

    def __init__(self, message: str, status: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code

    def to_response(self):
        return jsonify({"error": {"code": self.code, "message": self.message}}), self.status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def _handle_api_error(err: APIError):
        return err.to_response()

    @app.errorhandler(404)
    def _handle_404(_err):
        return jsonify({"error": {"code": "not_found", "message": "Ressource introuvable"}}), 404

    @app.errorhandler(405)
    def _handle_405(_err):
        return jsonify({"error": {"code": "method_not_allowed",
                                  "message": "Méthode non autorisée"}}), 405

    @app.errorhandler(429)
    def _handle_429(_err):
        return jsonify({"error": {"code": "rate_limited",
                                  "message": "Trop de requêtes, réessayez plus tard"}}), 429

    @app.errorhandler(500)
    def _handle_500(_err):  # pragma: no cover - défensif
        return jsonify({"error": {"code": "internal_error",
                                  "message": "Erreur interne du serveur"}}), 500
