"""Routes HTTP de l'API Sentinelle (v1)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..detection.url_analysis import analyze_url
from .errors import APIError
from .schemas import validate_analyze, validate_check_url, validate_report

bp = Blueprint("api", __name__)


def _engine():
    return current_app.config["ENGINE"]


def _repo():
    return current_app.config["REPOSITORY"]


def _cfg():
    return current_app.config["SENTINELLE_CONFIG"]


@bp.get("/health")
def health():
    """Sonde de santé (pour load balancers / orchestrateurs)."""
    return jsonify({
        "status": "ok",
        "service": "sentinelle",
        "ml_available": _engine().classifier.is_available,
    })


@bp.post("/api/v1/analyze")
def analyze():
    """Analyse un message texte et renvoie un verdict de fraude."""
    data = validate_analyze(request.get_json(silent=True), _cfg().max_message_length)
    verdict = _engine().analyze(data["message"], sender=data["sender"], lang=data["lang"])
    return jsonify(verdict.to_dict())


@bp.post("/api/v1/report")
def report():
    """Signale un numéro ou un domaine frauduleux à la communauté."""
    data = validate_report(request.get_json(silent=True))
    try:
        result = _repo().add_report(
            target_type=data["type"],
            raw_value=data["value"],
            category=data["category"],
            reporter_id=data["reporter_id"],
            message=data["message"],
        )
    except ValueError as exc:
        raise APIError(str(exc), 400, "invalid_field") from exc
    return jsonify(result), 201


@bp.get("/api/v1/check-number")
def check_number():
    """Vérifie la réputation communautaire d'un numéro (caller ID)."""
    number = request.args.get("number", "").strip()
    if not number:
        raise APIError("Paramètre « number » requis.", 400, "missing_field")
    return jsonify(_repo().lookup_number(number))


@bp.post("/api/v1/check-url")
def check_url():
    """Analyse anti-hameçonnage d'une URL (réputation + heuristiques)."""
    data = validate_check_url(request.get_json(silent=True))
    finding = analyze_url(data["url"])
    result = finding.to_dict()
    result["community_blocked"] = _repo().is_domain_blocked(finding.registrable_domain)
    return jsonify(result)


@bp.get("/api/v1/stats")
def stats():
    """Statistiques publiques de la communauté."""
    return jsonify(_repo().get_stats())


def _extract_ios_payload() -> tuple[str, str | None]:
    """Extrait (message, expéditeur) de la requête de déféré iOS, de façon
    tolérante : le format exact est défini par Apple et peut évoluer."""
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        msg = data.get("message") or data.get("messageBody") or data.get("text") or ""
        sender = data.get("sender") or data.get("senderIdentifier")
        return (msg.strip() if isinstance(msg, str) else ""), (sender if isinstance(sender, str) else None)
    if request.form:
        msg = request.form.get("message") or request.form.get("messageBody") or request.form.get("text") or ""
        return msg.strip(), request.form.get("sender")
    raw = request.get_data(as_text=True) or ""
    return raw.strip(), None


@bp.post("/api/v1/ios-filter")
def ios_filter():
    """Déféré réseau pour l'extension de filtrage SMS iOS (IdentityLookup).

    Renvoie l'action de filtrage attendue par l'extension :
    `{"action": "junk" | "allow"}`. Mappe le niveau du verdict :
    fraude/suspect → junk ; sinon → allow.
    """
    message, sender = _extract_ios_payload()
    if not message:
        return jsonify({"action": "none"})
    message = message[: _cfg().max_message_length]
    verdict = _engine().analyze(message, sender=sender)
    action = "junk" if verdict.level in ("fraud", "suspicious") else "allow"
    return jsonify({"action": action, "level": verdict.level, "risk_score": verdict.risk_score})
