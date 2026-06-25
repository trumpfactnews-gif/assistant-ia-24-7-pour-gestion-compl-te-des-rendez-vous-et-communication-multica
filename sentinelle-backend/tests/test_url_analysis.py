"""Tests de l'analyse anti-hameçonnage des URL."""

from sentinelle.detection import url_analysis as ua


def test_official_domain_is_safe():
    f = ua.analyze_url("https://www.desjardins.com/login")
    assert f.is_official is True
    assert f.score == 0


def test_lookalike_brand_subdomain():
    f = ua.analyze_url("http://desjardins.secure-login.xyz/verifier")
    assert f.is_official is False
    assert f.score >= 55
    codes = {r["code"] for r in f.reasons}
    assert "url_lookalike_brand" in codes


def test_typosquatting_detected():
    f = ua.analyze_url("http://desjardlns.com")
    codes = {r["code"] for r in f.reasons}
    assert "url_typosquat" in codes
    assert f.score >= 55


def test_shortener_flagged():
    f = ua.analyze_url("https://bit.ly/abc123")
    codes = {r["code"] for r in f.reasons}
    assert "url_shortener" in codes


def test_ip_literal_flagged():
    f = ua.analyze_url("http://192.168.10.5/login")
    codes = {r["code"] for r in f.reasons}
    assert "url_ip_literal" in codes


def test_suspicious_tld():
    f = ua.analyze_url("http://random-thing.top")
    codes = {r["code"] for r in f.reasons}
    assert "url_suspicious_tld" in codes


def test_registrable_domain_multilevel_suffix():
    assert ua.registrable_domain("foo.cra-arc.gc.ca") == "cra-arc.gc.ca"
    assert ua.registrable_domain("login.desjardins.com") == "desjardins.com"
    assert ua.registrable_domain("a.b.c.evil.xyz") == "evil.xyz"


def test_extract_urls_ignores_emails():
    text = "Visitez http://test.com et www.exemple.ca/path mais pas fraude@banque.com"
    urls = ua.extract_urls(text)
    assert "http://test.com" in urls
    assert any("exemple.ca" in u for u in urls)
    assert not any("banque.com" in u for u in urls)


def test_userinfo_obfuscation():
    f = ua.analyze_url("http://desjardins.com@evil.xyz/login")
    # Le vrai hôte est evil.xyz, pas desjardins.com.
    assert f.is_official is False
    codes = {r["code"] for r in f.reasons}
    assert "url_userinfo" in codes
