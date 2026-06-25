"""Tests des heuristiques à base de règles."""

from sentinelle.detection import heuristics


def test_bank_fraud_detected():
    text = ("Desjardins: votre compte a été bloqué. Confirmez votre NIP et "
            "numéro de carte immédiatement.")
    result = heuristics.evaluate(text)
    assert result.score >= 50
    assert result.category == "bank_fraud"
    codes = {s.code for s in result.signals}
    assert "credential_request" in codes


def test_gift_card_is_strong_signal():
    result = heuristics.evaluate("Payez votre amende en carte cadeau Google Play maintenant.")
    assert result.score >= 70
    assert any(s.code == "gift_card" for s in result.signals)


def test_grandparent_scam_category():
    text = "Bonjour grand-maman, c'est moi, j'ai eu un accident, envoie-moi de l'argent."
    result = heuristics.evaluate(text)
    assert result.category == "family_emergency"
    assert result.score >= 50


def test_benign_message_is_low():
    result = heuristics.evaluate("Salut! On se rejoint au resto à 19h ce soir? Hâte de te voir.")
    assert result.score < 25
    assert result.category == "none"


def test_empty_message():
    result = heuristics.evaluate("")
    assert result.score == 0
    assert result.signals == []


def test_english_scam_detected():
    text = "Your CRA tax refund is pending. Reply with your SIN and card number to claim."
    result = heuristics.evaluate(text)
    assert result.score >= 50
    assert result.category == "gov_phishing"


def test_legit_otp_delivery_not_credential_request():
    # Un OTP livré + « ne le partagez pas » ne doit pas compter comme phishing.
    text = "Votre code de vérification RBC est 482913. Ne le partagez avec personne."
    result = heuristics.evaluate(text)
    assert not any(s.code == "credential_request" for s in result.signals)


def test_phishing_asking_for_code_still_flagged():
    # En revanche, demander le code reste un signal de phishing.
    text = "Confirmez votre code de vérification et votre NIP pour débloquer le compte."
    result = heuristics.evaluate(text)
    assert any(s.code == "credential_request" for s in result.signals)


def test_noisy_or_accumulates_without_exceeding_100():
    text = ("URGENT: votre compte sera fermé. Confirmez votre mot de passe, "
            "votre NIP et payez par carte cadeau immédiatement, dernière chance!")
    result = heuristics.evaluate(text)
    assert 0 <= result.score <= 100
    assert result.score >= 90  # plusieurs signaux forts cumulés
