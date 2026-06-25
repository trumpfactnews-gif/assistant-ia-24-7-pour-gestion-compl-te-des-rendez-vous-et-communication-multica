"""Analyse anti-hameçonnage des URL.

Détecte les liens malveillants courants dans les SMS frauduleux :
domaines sosies (« desjardins.secure-login.xyz »), typosquatting
(« desjardlns.com »), raccourcisseurs masquant la destination, TLD abusifs,
adresses IP littérales, homographes (punycode), etc.

Sans dépendance externe : un mini-extracteur de « domaine enregistrable » gère
les suffixes multi-niveaux canadiens (gc.ca, qc.ca…).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .patterns import (
    BRAND_TOKENS,
    OFFICIAL_DOMAINS,
    SUSPICIOUS_TLDS,
    URL_SHORTENERS,
)

# Suffixes publics à deux niveaux que l'on rencontre au Canada / fréquemment.
_MULTI_LEVEL_SUFFIXES = frozenset(
    {
        "gc.ca", "qc.ca", "on.ca", "ab.ca", "bc.ca", "ns.ca",  # Canada
        "co.uk", "org.uk", "gov.uk", "com.au", "co.nz", "co.jp",
    }
)

# Jetons d'apparence « officielle » souvent ajoutés aux domaines sosies.
_LURE_TOKENS = frozenset(
    {"secure", "login", "verify", "verification", "account", "update",
     "confirm", "signin", "service", "support", "alert", "billing", "auth"}
)

_URL_RE = re.compile(
    r"""
    (?P<url>
        (?:https?://)?
        (?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+   # sous-domaines + domaine
        [a-z]{2,24}                                     # TLD
        (?::\d{2,5})?                                   # port éventuel
        (?:/[^\s<>"']*)?                                # chemin éventuel
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_IP_HOST_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


@dataclass
class UrlFinding:
    """Résultat de l'analyse d'une URL."""

    url: str
    host: str
    registrable_domain: str
    is_official: bool
    score: int  # 0..100
    reasons: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "host": self.host,
            "registrable_domain": self.registrable_domain,
            "is_official": self.is_official,
            "score": self.score,
            "reasons": self.reasons,
        }


def _levenshtein(a: str, b: str) -> int:
    """Distance d'édition (implémentation simple, sans dépendance)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def registrable_domain(host: str) -> str:
    """Extrait le domaine enregistrable (eTLD+1) avec gestion des suffixes
    multi-niveaux courants. Heuristique — pas une Public Suffix List complète."""
    host = host.lower().strip(".")
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def extract_urls(text: str) -> list[str]:
    """Renvoie la liste des URL / domaines trouvés dans un texte (dédupliqués,
    en ignorant ce qui ressemble à une adresse courriel)."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _URL_RE.finditer(text or ""):
        start = m.start()
        # Ignorer les adresses courriel (jeton précédé d'un « @ »).
        if start > 0 and text[start - 1] == "@":
            continue
        url = m.group("url").rstrip(".,);:!?'\"")
        key = url.lower()
        if key not in seen:
            seen.add(key)
            found.append(url)
    return found


def _host_tokens(host: str) -> set[str]:
    """Découpe un hôte en jetons alphanumériques (sur «.», «-», «_»)."""
    return {t for t in re.split(r"[.\-_]", host) if t}


def analyze_url(url: str) -> UrlFinding:
    """Analyse une seule URL et calcule un score de risque (0..100)."""
    raw = url if "://" in url else f"http://{url}"
    parsed = urlparse(raw)
    netloc = parsed.netloc
    reasons: list[dict] = []
    score = 0

    # Userinfo (« @ ») dans l'URL : technique d'obscurcissement classique.
    if "@" in netloc:
        reasons.append({"code": "url_userinfo",
                        "fr": "Caractère « @ » trompeur dans l'adresse",
                        "en": "Deceptive '@' character in the address"})
        score += 45
        netloc = netloc.split("@", 1)[-1]

    host = netloc.split(":", 1)[0].lower().strip(".")
    reg = registrable_domain(host)
    is_official = reg in OFFICIAL_DOMAINS

    if is_official:
        return UrlFinding(url=url, host=host, registrable_domain=reg,
                          is_official=True, score=0, reasons=reasons)

    # Adresse IP littérale en guise de domaine.
    if _IP_HOST_RE.match(host):
        reasons.append({"code": "url_ip_literal",
                        "fr": "Adresse IP au lieu d'un nom de domaine",
                        "en": "IP address instead of a domain name"})
        score += 55

    # Punycode / homographes.
    if "xn--" in host:
        reasons.append({"code": "url_punycode",
                        "fr": "Domaine en punycode (risque d'homographe)",
                        "en": "Punycode domain (homograph risk)"})
        score += 50

    # Raccourcisseur d'URL.
    if reg in URL_SHORTENERS:
        reasons.append({"code": "url_shortener",
                        "fr": "Raccourcisseur masquant la vraie destination",
                        "en": "Link shortener hiding the real destination"})
        score += 45

    # TLD abusif.
    tld = reg.rsplit(".", 1)[-1]
    if tld in SUSPICIOUS_TLDS:
        reasons.append({"code": "url_suspicious_tld",
                        "fr": f"Extension de domaine à risque (.{tld})",
                        "en": f"High-abuse domain extension (.{tld})"})
        score += 30

    # Marque usurpée : domaine sosie ou typosquatting.
    tokens = _host_tokens(host)
    reg_main = reg.split(".", 1)[0]
    brand_hit = None
    for token, official in BRAND_TOKENS.items():
        exact = token in tokens
        substr = len(token) >= 6 and token in host
        if (exact or substr) and reg != official:
            brand_hit = (token, official)
            break
    if brand_hit is None:
        # Typosquatting : faible distance d'édition sur la racine du domaine.
        for token, official in BRAND_TOKENS.items():
            brand_main = official.split(".", 1)[0]
            if len(brand_main) >= 5 and 1 <= _levenshtein(reg_main, brand_main) <= 2:
                brand_hit = (token, official)
                reasons.append({"code": "url_typosquat",
                                "fr": f"Domaine imitant « {brand_main} » (faute volontaire)",
                                "en": f"Domain mimicking '{brand_main}' (deliberate typo)"})
                score += 60
                break
    if brand_hit and not any(r["code"] == "url_typosquat" for r in reasons):
        token, official = brand_hit
        reasons.append({"code": "url_lookalike_brand",
                        "fr": f"Marque « {token} » utilisée hors de son domaine officiel",
                        "en": f"Brand '{token}' used outside its official domain"})
        score += 55
        # Jetons « rassurants » accolés à une marque : aggravant.
        if tokens & _LURE_TOKENS:
            reasons.append({"code": "url_lure_tokens",
                            "fr": "Mots rassurants (« secure », « login »…) accolés à la marque",
                            "en": "Reassuring words ('secure', 'login'…) attached to the brand"})
            score += 15

    # Domaine excessivement long ou très fragmenté.
    if host.count(".") >= 4:
        reasons.append({"code": "url_many_subdomains",
                        "fr": "Empilement inhabituel de sous-domaines",
                        "en": "Unusual stack of sub-domains"})
        score += 15

    return UrlFinding(url=url, host=host, registrable_domain=reg,
                      is_official=is_official, score=min(score, 100), reasons=reasons)


def analyze_text_urls(text: str) -> list[UrlFinding]:
    """Analyse toutes les URL d'un texte."""
    return [analyze_url(u) for u in extract_urls(text)]
