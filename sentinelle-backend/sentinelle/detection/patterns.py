"""Base de connaissances des arnaques (Canada / Québec).

Ce module centralise les *données* de détection :

* `RULES`           : règles heuristiques (expressions régulières pondérées),
                      bilingues, spécifiques au contexte canadien ;
* `OFFICIAL_DOMAINS`: domaines officiels des banques, gouvernements, etc. ;
* `BRAND_TOKENS`    : marques fréquemment usurpées (pour la détection de
                      domaines sosies / typosquatting).

Les *algorithmes* qui consomment ces données vivent dans `heuristics.py` et
`url_analysis.py`. Séparer données et logique facilite l'ajustement des règles
et leur futur remplacement par un modèle entraîné sur des données réelles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """Une règle heuristique.

    Attributs :
        code     : identifiant stable (utile pour les logs et les tests) ;
        category : catégorie d'arnaque visée, ou "generic" ;
        weight   : indice de gravité dans l'intervalle [0, 1] ;
        regex    : motif compilé recherché dans le message ;
        label    : libellé bilingue de ce qui a été détecté.
    """

    code: str
    category: str
    weight: float
    regex: re.Pattern
    label: dict


def _c(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


# ---------------------------------------------------------------------------
# Signaux génériques : forts indicateurs de fraude, toutes catégories confondues
# ---------------------------------------------------------------------------
_GENERIC = [
    Rule(
        "urgency",
        "generic",
        0.35,
        _c(
            r"\b(urgent|imm[ée]diat(?:ement)?|maintenant|au plus vite|derni[eè]re chance|"
            r"expire|dans les 24\s*h(?:eures)?|sous 24\s*h|act now|immediately|"
            r"within 24\s*hours?|right away|last chance|as soon as possible)\b"
        ),
        {"fr": "Pression / urgence", "en": "Pressure / urgency"},
    ),
    Rule(
        "credential_request",
        "generic",
        0.70,
        _c(
            r"\b(mot de passe|code (?:de )?(?:v[ée]rification|s[ée]curit[ée]|confirmation)|"
            r"n[ip]{2,3}\b|num[ée]ro de carte|carte de cr[ée]dit|cvv|nas\b|"
            r"num[ée]ro d.assurance sociale|identifiants?|password|verification code|"
            r"one[-\s]?time (?:code|password)|otp\b|pin\b|card number|sin\b|"
            r"social insurance|login credentials?)\b"
        ),
        {"fr": "Demande d'identifiants / code secret", "en": "Request for credentials / secret code"},
    ),
    Rule(
        "money_request",
        "generic",
        0.40,
        _c(
            r"(?:\bvirement\b|interac|e-?transfer|transfert d.argent|"
            r"\bpay(?:er|ez)\b|paiement|verser|d[ée]p[oô]t|frais (?:de|d[\s'])|"
            r"\$\s?\d|\d+\s?\$|\bpay (?:now|a fee)\b|wire (?:money|transfer))"
        ),
        {"fr": "Demande d'argent / paiement", "en": "Money / payment request"},
    ),
    Rule(
        "gift_card",
        "generic",
        0.80,
        _c(
            r"\b(carte[s]? cadeau|gift card|itunes|google play (?:card|gift)|"
            r"amazon (?:gift )?card|steam card|cartes? pr[ée]pay[ée]e)\b"
        ),
        {"fr": "Demande de carte cadeau (signe quasi certain de fraude)",
         "en": "Gift-card request (near-certain fraud sign)"},
    ),
    Rule(
        "threat_legal",
        "generic",
        0.60,
        _c(
            r"\b(poursuite|arrestation|mandat|amende|p[ée]nalit[ée]|saisie|"
            r"votre compte sera (?:ferm[ée]|suspendu|bloqu[ée])|gel de (?:votre )?compte|"
            r"action en justice|arrest|lawsuit|warrant|legal action|account (?:will be )?"
            r"(?:suspended|closed|locked|frozen)|penalty|seizure)\b"
        ),
        {"fr": "Menace / intimidation", "en": "Threat / intimidation"},
    ),
    Rule(
        "click_link",
        "generic",
        0.30,
        _c(
            r"\b(cliquez(?: ici)?|cliquer sur|appuyez sur le lien|suivez (?:ce|le) lien|"
            r"click (?:here|the link|below)|tap (?:here|the link)|visitez|rendez-vous sur)\b"
        ),
        {"fr": "Incitation à cliquer sur un lien", "en": "Call to click a link"},
    ),
    Rule(
        "too_good",
        "generic",
        0.45,
        _c(
            r"\b(f[ée]licitations|gratuit(?:ement)?|vous avez gagn[ée]|cadeau gratuit|"
            r"rembours(?:ement|er) (?:imm[ée]diat|en attente)|congratulations|"
            r"you(?:'ve| have) won|free (?:gift|prize)|claim your)\b"
        ),
        {"fr": "Offre trop belle pour être vraie", "en": "Too-good-to-be-true offer"},
    ),
]

# ---------------------------------------------------------------------------
# Signaux spécifiques par catégorie d'arnaque (contexte canadien)
# ---------------------------------------------------------------------------
_CATEGORY = [
    # --- Faux conseiller bancaire ----------------------------------------
    Rule(
        "bank_keywords",
        "bank_fraud",
        0.55,
        _c(
            r"\b(desjardins|banque|caisse|rbc|td|bmo|scotia(?:bank)?|cibc|tangerine|"
            r"banque nationale|laurentienne|account|compte bancaire|"
            r"transaction (?:suspecte|inhabituelle|non autoris[ée]e)|"
            r"activit[ée] suspecte|carte (?:bloqu[ée]e|d[ée]sactiv[ée]e|verrouill[ée]e)|"
            r"suspicious (?:transaction|activity)|your (?:card|account))\b"
        ),
        {"fr": "Vocabulaire bancaire", "en": "Banking vocabulary"},
    ),
    # --- Hameçonnage gouvernemental --------------------------------------
    Rule(
        "gov_keywords",
        "gov_phishing",
        0.6,
        _c(
            r"\b(arc\b|agence du revenu|revenu qu[ée]bec|service[\s-]?canada|"
            r"cra\b|canada revenue|gouvernement du canada|tps|tvq|tvh|gst|hst|"
            r"prestation|cr[ée]dit d.imp[oô]t|remboursement d.imp[oô]t|"
            r"tax refund|benefit payment|d[ée]claration de revenus)\b"
        ),
        {"fr": "Usurpation d'organisme gouvernemental", "en": "Government-agency impersonation"},
    ),
    # --- Colis / livraison ------------------------------------------------
    Rule(
        "package_keywords",
        "package_delivery",
        0.55,
        _c(
            r"\b(postes? canada|canada post|colis|livraison|exp[ée]dition|"
            r"frais de douane|frais de livraison|votre paquet|redelivery|reprogrammer la livraison|"
            r"purolator|fedex|ups\b|dhl|package|parcel|shipment|customs fee|"
            r"delivery (?:failed|attempt|fee))\b"
        ),
        {"fr": "Arnaque de colis / livraison", "en": "Package / delivery scam"},
    ),
    # --- Urgence familiale (« grand-maman ») ------------------------------
    Rule(
        "family_emergency",
        "family_emergency",
        0.6,
        _c(
            r"(\bc.est moi\b|grand[\s-]?(?:maman|papa|m[èe]re|p[èe]re)|"
            r"j.ai (?:eu un accident|chang[ée] de num[ée]ro|perdu mon t[ée]l[ée]phone)|"
            r"je suis en prison|paie?r? la caution|\bit.s me\b|"
            r"i (?:had an accident|lost my phone|changed my number)|"
            r"i.m in (?:jail|trouble)|need (?:money|bail))"
        ),
        {"fr": "Fausse urgence d'un proche", "en": "Fake relative emergency"},
    ),
    # --- Crypto / investissement -----------------------------------------
    Rule(
        "crypto_keywords",
        "crypto_investment",
        0.55,
        _c(
            r"\b(crypto(?:monnaie)?|bitcoin|btc|ethereum|investiss?ement|"
            r"rendement garanti|profit garanti|trading|opportunit[ée] d.investissement|"
            r"guaranteed return|double your (?:money|investment)|crypto opportunity)\b"
        ),
        {"fr": "Investissement / crypto miracle", "en": "Crypto / investment lure"},
    ),
    # --- Prix / loterie ---------------------------------------------------
    Rule(
        "prize_keywords",
        "prize_lottery",
        0.5,
        _c(
            r"\b(loterie|tirage|vous avez [ée]t[ée] s[ée]lectionn[ée]|"
            r"r[ée]clamer votre prix|gros lot|iphone gratuit|"
            r"lottery|prize draw|you (?:have been|were) selected|claim your prize|"
            r"free iphone|gift waiting)\b"
        ),
        {"fr": "Prix / loterie fictifs", "en": "Fake prize / lottery"},
    ),
    # --- Faux support technique ------------------------------------------
    Rule(
        "tech_support",
        "tech_support",
        0.55,
        _c(
            r"\b(support technique|microsoft|apple support|votre (?:ordinateur|appareil) "
            r"est infect[ée]|virus d[ée]tect[ée]|acc[èe]s [àa] distance|"
            r"tech support|your (?:computer|device) is infected|virus detected|"
            r"remote access|geek squad)\b"
        ),
        {"fr": "Faux support technique", "en": "Fake tech support"},
    ),
    # --- Péage routier (très répandu au Canada : 407 ETR) ----------------
    Rule(
        "toll_road",
        "toll_road",
        0.6,
        _c(
            r"\b(407\s*etr|407etr|p[ée]age|toll|frais de p[ée]age|"
            r"unpaid toll|outstanding toll|toll (?:charge|invoice|bill))\b"
        ),
        {"fr": "Arnaque de péage (407 ETR)", "en": "Toll-road scam (407 ETR)"},
    ),
    # --- Fausse offre d'emploi -------------------------------------------
    Rule(
        "job_scam",
        "job_scam",
        0.5,
        _c(
            r"\b(offre d.emploi|travail [àa] domicile|recrutement|poste disponible|"
            r"gagnez \d+\s?\$ ?(?:par|/)\s?(?:jour|semaine|heure)|"
            r"job offer|work from home|earn \$?\d+\s?(?:per|/)\s?(?:day|week|hour)|"
            r"hiring now|easy money)\b"
        ),
        {"fr": "Fausse offre d'emploi", "en": "Fake job offer"},
    ),
]

RULES: list[Rule] = _GENERIC + _CATEGORY


# ---------------------------------------------------------------------------
# Anti-hameçonnage : domaines officiels et marques usurpées
# ---------------------------------------------------------------------------

# Domaines officiels (registrable domain) à NE PAS signaler comme sosies.
OFFICIAL_DOMAINS: frozenset[str] = frozenset(
    {
        # Banques / caisses
        "desjardins.com", "accweb.mouv.desjardins.com",
        "rbc.com", "rbcroyalbank.com", "royalbank.com",
        "td.com", "tdcanadatrust.com", "tdbank.com",
        "bmo.com", "bmoharris.com",
        "scotiabank.com", "scotiaonline.scotiabank.com",
        "cibc.com",
        "tangerine.ca",
        "nbc.ca", "bnc.ca",  # Banque Nationale
        "laurentianbank.ca", "banquelaurentienne.ca",
        # Paiement
        "interac.ca",
        "paypal.com", "paypal.ca",
        # Gouvernements
        "canada.ca", "cra-arc.gc.ca", "gc.ca", "servicecanada.gc.ca",
        "revenuquebec.ca", "quebec.ca", "gouv.qc.ca",
        # Postes / messageries
        "canadapost-postescanada.ca", "canadapost.ca", "postescanada.ca",
        "purolator.com", "ups.com", "fedex.com", "dhl.com",
        # Télécoms
        "bell.ca", "rogers.com", "telus.com", "videotron.com",
        "fido.ca", "koodomobile.com", "virginplus.ca",
        # Services en ligne courants
        "amazon.ca", "amazon.com", "netflix.com", "apple.com", "microsoft.com",
        # Péage
        "407etr.com",
    }
)

# Marques (jetons) fréquemment usurpées -> domaine officiel de référence.
# Sert à repérer un jeton de marque présent dans un domaine NON officiel
# (ex. « desjardins.secure-login.xyz ») et le typosquatting (ex. « desjardlns.com »).
BRAND_TOKENS: dict[str, str] = {
    "desjardins": "desjardins.com",
    "interac": "interac.ca",
    "rbc": "rbc.com",
    "scotiabank": "scotiabank.com",
    "scotia": "scotiabank.com",
    "cibc": "cibc.com",
    "tangerine": "tangerine.ca",
    "bmo": "bmo.com",
    "revenuquebec": "revenuquebec.ca",
    "servicecanada": "servicecanada.gc.ca",
    "canadapost": "canadapost.ca",
    "postescanada": "postescanada.ca",
    "purolator": "purolator.com",
    "paypal": "paypal.com",
    "netflix": "netflix.com",
    "amazon": "amazon.ca",
    "fedex": "fedex.com",
    "telus": "telus.com",
    "videotron": "videotron.com",
    "407etr": "407etr.com",
}

# TLD à forte prévalence d'abus (signal faible à modéré).
SUSPICIOUS_TLDS: frozenset[str] = frozenset(
    {
        "zip", "mov", "xyz", "top", "tk", "ml", "ga", "cf", "gq", "click",
        "link", "rest", "country", "kim", "work", "fit", "loan", "men",
        "review", "date", "racing", "stream", "download", "win", "bid",
    }
)

# Raccourcisseurs d'URL (masquent la destination réelle).
URL_SHORTENERS: frozenset[str] = frozenset(
    {
        "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
        "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "t.ly", "tiny.cc",
        "bnc.lt", "soo.gd", "v.gd", "qr.ae",
    }
)
