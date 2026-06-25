"""Tests du moteur de détection (orchestration)."""

import pytest

from sentinelle.detection.classifier import FraudClassifier
from sentinelle.detection.engine import DetectionEngine


class StubCommunity:
    def __init__(self, numbers=(), domains=()):
        self.numbers = set(numbers)
        self.domains = set(domains)

    def is_number_blocked(self, phone):
        return phone in self.numbers

    def is_domain_blocked(self, domain):
        return domain in self.domains


@pytest.fixture
def engine(tmp_path):
    clf = FraudClassifier(str(tmp_path / "no-model.joblib"))  # pas de modèle -> mode heuristique
    return DetectionEngine(clf, community=None, ml_weight=0.45)


def test_clear_fraud_is_flagged(engine):
    v = engine.analyze(
        "Desjardins: votre compte est bloqué. Vérifiez ici: http://desjardins-securite.xyz/login")
    assert v.is_fraud is True
    assert v.risk_score >= 50
    assert v.category == "bank_fraud"
    assert v.recommended_action["fr"]


def test_benign_is_safe(engine):
    v = engine.analyze("Salut, on se voit à 19h au resto ce soir? Hâte!")
    assert v.level == "safe"
    assert v.is_fraud is False


def test_ml_component_absent_without_model(engine):
    v = engine.analyze("test")
    assert v.components["ml"] is None


def test_community_number_block():
    clf = FraudClassifier("/nonexistent/model.joblib")
    eng = DetectionEngine(clf, community=StubCommunity(numbers={"+15145550199"}))
    v = eng.analyze("Bonjour comment ça va", sender="+15145550199")
    assert v.risk_score >= 90
    assert v.level == "fraud"
    assert any(s.code == "community_number" for s in v.signals)


def test_community_domain_block():
    clf = FraudClassifier("/nonexistent/model.joblib")
    eng = DetectionEngine(clf, community=StubCommunity(domains={"evil-block.xyz"}))
    v = eng.analyze("Regarde ce lien http://evil-block.xyz/promo")
    assert v.risk_score >= 90
    assert any(s.code == "community_domain" for s in v.signals)


def test_credential_plus_risky_link_floor(engine):
    # credential (heuristique ~70) + lien raccourci (url 45) -> plancher 85.
    v = engine.analyze("Confirmez votre code de vérification ici: https://bit.ly/abc")
    assert v.risk_score >= 85
    assert v.level == "fraud"


def test_to_dict_serializable(engine):
    v = engine.analyze("Felicitations, vous avez gagné! Cliquez: http://prix.top")
    d = v.to_dict()
    assert "is_fraud" in d
    assert "risk_score" in d
    assert isinstance(d["signals"], list)
    assert d["analyzed_urls"]
