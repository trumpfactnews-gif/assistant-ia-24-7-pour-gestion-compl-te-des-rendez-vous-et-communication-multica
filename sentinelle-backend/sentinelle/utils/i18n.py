"""Messages bilingues (français / anglais).

Sentinelle cible le Canada : toutes les explications destinées à l'utilisateur
sont fournies en français et en anglais.
"""

from __future__ import annotations

# Libellés des niveaux de risque.
LEVEL_LABELS: dict[str, dict[str, str]] = {
    "safe": {"fr": "Sûr", "en": "Safe"},
    "caution": {"fr": "Prudence", "en": "Caution"},
    "suspicious": {"fr": "Suspect", "en": "Suspicious"},
    "fraud": {"fr": "Fraude probable", "en": "Likely fraud"},
}

# Libellés des catégories d'arnaque.
CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "none": {"fr": "Aucune", "en": "None"},
    "bank_fraud": {"fr": "Faux conseiller bancaire", "en": "Fake bank advisor"},
    "gov_phishing": {
        "fr": "Hameçonnage gouvernemental (ARC / Revenu Québec)",
        "en": "Government phishing (CRA / Revenu Québec)",
    },
    "package_delivery": {"fr": "Arnaque de colis", "en": "Package delivery scam"},
    "family_emergency": {
        "fr": "Urgence familiale (« bonjour grand-maman »)",
        "en": "Family emergency (grandparent scam)",
    },
    "crypto_investment": {"fr": "Investissement / crypto", "en": "Crypto / investment scam"},
    "prize_lottery": {"fr": "Prix / loterie", "en": "Prize / lottery scam"},
    "tech_support": {"fr": "Faux support technique", "en": "Tech-support scam"},
    "toll_road": {"fr": "Péage routier (407 ETR)", "en": "Highway toll (407 ETR)"},
    "job_scam": {"fr": "Fausse offre d'emploi", "en": "Job-offer scam"},
    "phishing": {"fr": "Hameçonnage générique", "en": "Generic phishing"},
    "spam": {"fr": "Pourriel", "en": "Spam"},
}

# Recommandations selon le niveau de risque.
RECOMMENDED_ACTIONS: dict[str, dict[str, str]] = {
    "safe": {
        "fr": "Aucune action particulière. Restez tout de même vigilant.",
        "en": "No particular action needed. Stay vigilant nonetheless.",
    },
    "caution": {
        "fr": "Soyez prudent. Ne cliquez sur aucun lien et ne communiquez aucune "
        "information personnelle avant d'avoir vérifié l'expéditeur.",
        "en": "Be cautious. Do not click any link or share personal information "
        "before verifying the sender.",
    },
    "suspicious": {
        "fr": "Ne cliquez sur aucun lien et ne répondez pas. Contactez "
        "directement l'organisation concernée par son numéro officiel.",
        "en": "Do not click any link and do not reply. Contact the organization "
        "directly using its official phone number.",
    },
    "fraud": {
        "fr": "Il s'agit très probablement d'une fraude. Ne cliquez sur rien, ne "
        "répondez pas, supprimez le message et signalez-le. En cas de perte "
        "financière, communiquez avec le Centre antifraude du Canada "
        "(1-888-495-8501).",
        "en": "This is very likely a fraud. Do not click anything, do not reply, "
        "delete the message and report it. If you lost money, contact the "
        "Canadian Anti-Fraud Centre (1-888-495-8501).",
    },
}


def level_label(level: str) -> dict[str, str]:
    return LEVEL_LABELS.get(level, LEVEL_LABELS["safe"])


def category_label(category: str) -> dict[str, str]:
    return CATEGORY_LABELS.get(category, CATEGORY_LABELS["none"])


def recommended_action(level: str) -> dict[str, str]:
    return RECOMMENDED_ACTIONS.get(level, RECOMMENDED_ACTIONS["safe"])
