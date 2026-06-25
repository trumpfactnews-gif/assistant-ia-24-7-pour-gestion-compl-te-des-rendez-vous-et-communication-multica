"""Validation des charges utiles entrantes.

Validation légère et sans dépendance pour garder l'API rapide et le déploiement
simple. Chaque validateur lève `APIError` (400) en cas de problème.
"""

from __future__ import annotations

from typing import Any

from .errors import APIError


def _require_dict(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise APIError("Le corps de la requête doit être un objet JSON.", 400, "invalid_body")
    return payload


def _require_str(payload: dict, key: str, *, max_len: int, required: bool = True) -> str | None:
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise APIError(f"Le champ « {key} » est requis.", 400, "missing_field")
        return None
    if not isinstance(value, str):
        raise APIError(f"Le champ « {key} » doit être une chaîne.", 400, "invalid_field")
    if len(value) > max_len:
        raise APIError(f"Le champ « {key} » dépasse {max_len} caractères.", 400, "field_too_long")
    return value


def validate_analyze(payload: Any, max_message_length: int) -> dict:
    data = _require_dict(payload)
    message = _require_str(data, "message", max_len=max_message_length)
    sender = _require_str(data, "sender", max_len=64, required=False)
    lang = _require_str(data, "lang", max_len=5, required=False)
    if lang is not None and lang not in ("fr", "en"):
        raise APIError("Le champ « lang » doit valoir 'fr' ou 'en'.", 400, "invalid_field")
    return {"message": message, "sender": sender, "lang": lang}


def validate_report(payload: Any) -> dict:
    data = _require_dict(payload)
    target_type = _require_str(data, "type", max_len=16)
    if target_type not in ("number", "domain"):
        raise APIError("Le champ « type » doit valoir 'number' ou 'domain'.", 400, "invalid_field")
    value = _require_str(data, "value", max_len=2048)
    category = _require_str(data, "category", max_len=64, required=False)
    reporter_id = _require_str(data, "reporter_id", max_len=128, required=False)
    message = _require_str(data, "message", max_len=4000, required=False)
    return {
        "type": target_type,
        "value": value,
        "category": category,
        "reporter_id": reporter_id,
        "message": message,
    }


def validate_check_url(payload: Any) -> dict:
    data = _require_dict(payload)
    url = _require_str(data, "url", max_len=2048)
    return {"url": url}
