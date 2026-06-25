"""Tests du dépôt communautaire (signalements + blocage agrégé)."""

import pytest

from sentinelle.db.repository import normalize_domain


def test_number_blocked_after_threshold(repo):
    # Seuil de test = 2 rapporteurs distincts.
    r1 = repo.add_report("number", "+1 514-555-0199", category="bank_fraud", reporter_id="userA")
    assert r1["blocked"] is False
    assert repo.is_number_blocked("(514) 555-0199") is False  # même numéro, formats variés

    r2 = repo.add_report("number", "5145550199", reporter_id="userB")
    assert r2["report_count"] == 2
    assert r2["blocked"] is True
    assert repo.is_number_blocked("+15145550199") is True


def test_same_reporter_does_not_double_count(repo):
    repo.add_report("number", "+15145550111", reporter_id="sameUser")
    res = repo.add_report("number", "+15145550111", reporter_id="sameUser")
    assert res["report_count"] == 1
    assert res["blocked"] is False


def test_domain_report_and_normalization(repo):
    repo.add_report("domain", "http://evil-site.xyz/login?x=1", reporter_id="a")
    res = repo.add_report("domain", "https://evil-site.xyz/other", reporter_id="b")
    assert res["blocked"] is True
    assert repo.is_domain_blocked("evil-site.xyz") is True
    assert repo.is_domain_blocked("www.evil-site.xyz") is True  # sous-domaine -> même domaine


def test_number_is_masked_not_stored_raw(repo):
    repo.add_report("number", "+15145550199", reporter_id="a")
    info = repo.lookup_number("+15145550199")
    assert info["display"] == "+1514***0199"
    assert "5550199" not in info["display"]  # le numéro complet n'est jamais exposé


def test_invalid_target_type(repo):
    with pytest.raises(ValueError):
        repo.add_report("courriel", "test@example.com", reporter_id="a")


def test_invalid_phone_rejected(repo):
    with pytest.raises(ValueError):
        repo.add_report("number", "   ", reporter_id="a")


def test_stats(repo):
    repo.add_report("number", "+15145550199", reporter_id="a")
    repo.add_report("number", "+15145550199", reporter_id="b")  # bloqué
    repo.add_report("domain", "http://x.top", reporter_id="a")  # 1 seul -> non bloqué
    stats = repo.get_stats()
    assert stats["total_reports"] == 3
    assert stats["blocked_numbers"] == 1
    assert stats["blocked_domains"] == 0
    assert stats["tracked_domains"] == 1


def test_normalize_domain_helper():
    assert normalize_domain("https://www.Evil-Site.XYZ/login") == "evil-site.xyz"
    assert normalize_domain("foo.cra-arc.gc.ca") == "cra-arc.gc.ca"
