"""Moteur de détection — orchestrateur.

Combine quatre sources de signal en un verdict unique et explicable :

1. Heuristiques expertes (`heuristics.py`)
2. Classifieur ML (`classifier.py`)
3. Analyse anti-hameçonnage des URL (`url_analysis.py`)
4. Base communautaire (numéros / domaines déjà signalés)

La logique de combinaison privilégie la prudence (produit défensif) : le ML peut
*relever* le verdict pour attraper des fraudes inédites, mais ne peut que
faiblement l'*abaisser* ; la communauté et certaines combinaisons critiques
imposent un plancher de risque.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Protocol

from ..utils import i18n
from . import heuristics
from .classifier import FraudClassifier
from .url_analysis import UrlFinding, analyze_text_urls


class CommunitySource(Protocol):
    """Contrat minimal pour interroger la base communautaire."""

    def is_number_blocked(self, phone: str) -> bool: ...
    def is_domain_blocked(self, domain: str) -> bool: ...


@dataclass
class Signal:
    code: str
    category: str
    label: dict
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Verdict:
    risk_score: int
    level: str
    level_label: dict
    category: str
    category_label: dict
    signals: list[Signal]
    explanation: dict
    recommended_action: dict
    components: dict
    analyzed_urls: list[dict] = field(default_factory=list)
    language: str = "fr"
    version: str = "1"

    @property
    def is_fraud(self) -> bool:
        return self.level in ("suspicious", "fraud")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_fraud"] = self.is_fraud
        return d


_FR_ACCENTS = re.compile(r"[àâäéèêëïîôöùûüçœ]", re.IGNORECASE)
_FR_WORDS = re.compile(
    r"\b(le|la|les|un|une|des|du|votre|vos|vous|nous|avez|êtes|est|sont|pour|avec|"
    r"sur|dans|compte|cliquez|argent|merci|bonjour|veuillez|payez|frais|reçu|"
    r"numéro|réclamez|gratuit|gagné)\b",
    re.IGNORECASE,
)
_EN_WORDS = re.compile(
    r"\b(the|your|you|have|are|is|for|with|account|click|money|thanks|hello|"
    r"please|pay|fee|received|number|claim|free|won|reply|verify)\b",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    """Devine la langue dominante (fr/en) par comptage de mots indicateurs.
    Le Québec étant la cible première, le français l'emporte à égalité."""
    text = text or ""
    fr = len(_FR_WORDS.findall(text)) + (2 if _FR_ACCENTS.search(text) else 0)
    en = len(_EN_WORDS.findall(text))
    return "en" if en > fr else "fr"


def level_from_score(score: int) -> str:
    if score >= 75:
        return "fraud"
    if score >= 50:
        return "suspicious"
    if score >= 25:
        return "caution"
    return "safe"


class DetectionEngine:
    """Façade de détection. Thread-safe et réutilisable."""

    def __init__(self, classifier: FraudClassifier, community: CommunitySource | None = None,
                 ml_weight: float = 0.45):
        self.classifier = classifier
        self.community = community
        self.ml_weight = ml_weight

    # -- API principale ----------------------------------------------------
    def analyze(self, text: str, sender: str | None = None,
                lang: str | None = None) -> Verdict:
        text = text or ""
        language = lang if lang in ("fr", "en") else detect_language(text)

        heur = heuristics.evaluate(text)
        findings = analyze_text_urls(text)
        url_score = max((f.score for f in findings), default=0)
        ml_prob = self.classifier.predict_proba(text)

        community_score, community_signal = self._community_check(sender, findings)

        score = self._combine(heur.score, url_score, ml_prob, community_score,
                              heur, findings)
        level = level_from_score(score)
        category = self._resolve_category(heur.category, url_score, score)

        signals = self._collect_signals(heur, findings, community_signal)
        explanation = self._build_explanation(language, level, score, category, signals)

        return Verdict(
            risk_score=score,
            level=level,
            level_label=i18n.level_label(level),
            category=category,
            category_label=i18n.category_label(category),
            signals=signals,
            explanation=explanation,
            recommended_action=i18n.recommended_action(level),
            components={
                "heuristics": heur.score,
                "url": url_score,
                "ml": round(ml_prob, 4) if ml_prob is not None else None,
                "community": community_score,
            },
            analyzed_urls=[f.to_dict() for f in findings],
            language=language,
        )

    # -- Internes ----------------------------------------------------------
    def _community_check(self, sender: str | None,
                         findings: list[UrlFinding]) -> tuple[int, Signal | None]:
        if self.community is None:
            return 0, None
        if sender and self.community.is_number_blocked(sender):
            return 100, Signal(
                code="community_number",
                category="generic",
                label={"fr": "Expéditeur signalé par la communauté",
                       "en": "Sender flagged by the community"},
                evidence=sender,
            )
        for f in findings:
            if not f.is_official and self.community.is_domain_blocked(f.registrable_domain):
                return 100, Signal(
                    code="community_domain",
                    category="generic",
                    label={"fr": "Domaine signalé par la communauté",
                           "en": "Domain flagged by the community"},
                    evidence=f.registrable_domain,
                )
        return 0, None

    def _combine(self, heur_score: int, url_score: int, ml_prob: float | None,
                 community_score: int, heur: heuristics.HeuristicResult,
                 findings: list[UrlFinding]) -> int:
        rule_component = max(heur_score, url_score)

        if ml_prob is not None:
            ml_score = ml_prob * 100
            w = self.ml_weight
            blended = (1 - w) * rule_component + w * ml_score
            # Le ML relève (attrape l'inédit) sans trop pouvoir abaisser une règle forte.
            score = max(rule_component * 0.7, blended, ml_score * 0.7)
        else:
            score = rule_component

        score = max(score, community_score)

        # Planchers pour combinaisons critiques.
        has_cred = any(s.code == "credential_request" for s in heur.signals)
        risky_link = any(f.score >= 45 for f in findings)
        if has_cred and risky_link:
            score = max(score, 85)
        if community_score >= 100:
            score = max(score, 90)

        return int(round(min(max(score, 0), 100)))

    @staticmethod
    def _resolve_category(heur_category: str, url_score: int, score: int) -> str:
        if heur_category != "none":
            return heur_category
        if url_score >= 50:
            return "phishing"
        if score >= 50:
            return "spam"
        return "none"

    @staticmethod
    def _collect_signals(heur: heuristics.HeuristicResult,
                         findings: list[UrlFinding],
                         community_signal: Signal | None) -> list[Signal]:
        signals: list[Signal] = []
        if community_signal is not None:
            signals.append(community_signal)
        for s in heur.signals:
            signals.append(Signal(code=s.code, category=s.category,
                                  label=s.label, evidence=s.evidence))
        for f in findings:
            for r in f.reasons:
                signals.append(Signal(
                    code=r["code"], category="url",
                    label={"fr": r["fr"], "en": r["en"]}, evidence=f.host))
        return signals

    @staticmethod
    def _build_explanation(language: str, level: str, score: int,
                           category: str, signals: list[Signal]) -> dict:
        cat = i18n.category_label(category)
        lvl = i18n.level_label(level)
        top = [s.label for s in signals[:4]]
        fr_indices = ", ".join(t["fr"] for t in top) if top else "aucun indice marquant"
        en_indices = ", ".join(t["en"] for t in top) if top else "no notable indicator"
        return {
            "fr": (f"Message classé « {lvl['fr']} » ({score}/100). "
                   f"Catégorie probable : {cat['fr']}. Indices : {fr_indices}."),
            "en": (f"Message classified as '{lvl['en']}' ({score}/100). "
                   f"Likely category: {cat['en']}. Indicators: {en_indices}."),
        }
