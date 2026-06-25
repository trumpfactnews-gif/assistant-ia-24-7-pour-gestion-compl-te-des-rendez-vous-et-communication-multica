"""Tests d'intégration de l'API HTTP."""

from sentinelle.app import create_app

from .conftest import make_config


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.get_json()["service"].startswith("Sentinelle")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["ml_available"] is False  # pas de modèle en test


def test_analyze_fraud(client):
    resp = client.post("/api/v1/analyze", json={
        "message": "ARC: remboursement de 458$ en attente. Réclamez: http://arc-remboursement.top",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_fraud"] is True
    assert body["risk_score"] >= 50
    assert "fr" in body["explanation"]
    assert "en" in body["explanation"]


def test_analyze_benign(client):
    resp = client.post("/api/v1/analyze", json={"message": "On soupe ensemble ce soir?"})
    assert resp.status_code == 200
    assert resp.get_json()["level"] == "safe"


def test_analyze_missing_message(client):
    resp = client.post("/api/v1/analyze", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "missing_field"


def test_report_then_check_number(client):
    payload = {"type": "number", "value": "+15145550199", "category": "bank_fraud"}
    r1 = client.post("/api/v1/report", json={**payload, "reporter_id": "userA"})
    assert r1.status_code == 201
    assert r1.get_json()["blocked"] is False

    r2 = client.post("/api/v1/report", json={**payload, "reporter_id": "userB"})
    assert r2.get_json()["blocked"] is True  # seuil de test = 2

    check = client.get("/api/v1/check-number", query_string={"number": "514-555-0199"})
    assert check.status_code == 200
    body = check.get_json()
    assert body["blocked"] is True
    assert body["report_count"] == 2


def test_check_number_requires_param(client):
    resp = client.get("/api/v1/check-number")
    assert resp.status_code == 400


def test_check_url(client):
    resp = client.post("/api/v1/check-url", json={"url": "http://rbc-secure-login.xyz/verify"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_official"] is False
    assert body["score"] > 0
    assert body["community_blocked"] is False


def test_analyze_uses_community_block(client):
    # Signaler un domaine jusqu'au blocage, puis vérifier qu'analyze le reflète.
    for reporter in ("a", "b"):
        client.post("/api/v1/report",
                    json={"type": "domain", "value": "http://arnaque-xyz.top", "reporter_id": reporter})
    resp = client.post("/api/v1/analyze",
                       json={"message": "Promo http://arnaque-xyz.top/gagnez"})
    body = resp.get_json()
    assert body["risk_score"] >= 90
    assert any(s["code"] == "community_domain" for s in body["signals"])


def test_stats(client):
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    body = resp.get_json()
    for key in ("total_reports", "blocked_numbers", "blocked_domains", "block_threshold"):
        assert key in body


def test_api_key_enforced(tmp_path):
    cfg = make_config(tmp_path, api_key="secret")
    app = create_app(cfg)
    c = app.test_client()
    # Sans clé -> 401
    assert c.get("/api/v1/stats").status_code == 401
    # /health reste public
    assert c.get("/health").status_code == 200
    # Avec la bonne clé -> 200
    ok = c.get("/api/v1/stats", headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
