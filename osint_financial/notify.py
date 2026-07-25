"""Alertes Telegram.

Failles corrigées :

* **Injection de balisage.** L'original envoyait probablement le message en
  ``parse_mode=Markdown``/``HTML`` avec une raison sociale et des intitulés de
  filings issus du réseau. Un nom contenant ``<a href="...">`` ou des
  caractères Markdown produisait un message trompeur (hameçonnage dans un canal
  de confiance). On envoie désormais en **texte brut** — pas de ``parse_mode``,
  donc rien à échapper et rien à détourner.
* **Jeton dans l'URL journalisée.** Telegram place le jeton dans le chemin ;
  toute trace d'erreur le divulguait. Les logs ne contiennent plus que l'hôte,
  et le jeton est enregistré auprès du filtre d'expurgation.
* **Échec bloquant.** Une panne Telegram faisait remonter une exception après
  l'analyse. L'envoi est maintenant explicitement non fatal.
* **Aucune limite de taille.** L'API rejette au-delà de 4096 caractères ; le
  message est tronqué proprement.
"""

from __future__ import annotations

from .config import Config
from .errors import OsintError
from .httpclient import HttpClient
from .logging_setup import get_logger
from .metrics import Metrics
from .portfolio import PositionPlan
from .scoring import ScoreResult

log = get_logger(__name__)

MAX_TELEGRAM_CHARS = 3800


def _sanitize_plain(text: str, limit: int) -> str:
    """Retire les caractères de contrôle et borne la longueur."""
    cleaned = "".join(ch for ch in text if ch == "\n" or ch >= " ")
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


def build_message(
    metrics: Metrics, scores: ScoreResult, plan: PositionPlan | None = None
) -> str:
    lines = [
        f"OSINT — {metrics.company_name} ({metrics.ticker})",
        f"Recommandation : {scores.recommendation} (confiance {scores.confidence:.0%})",
        f"Risque {scores.risk_score}/100 · Opportunité {scores.opportunity_score}/100",
    ]
    if scores.resilience_score is not None:
        lines.append(f"Résilience : {scores.resilience_score}/100")
    if metrics.price is not None:
        lines.append(f"Cours : {metrics.price:.2f} {metrics.currency} ({metrics.price_source})")
    if metrics.target_price_pe is not None:
        lines.append(
            f"Prix cible PE : {metrics.target_price_pe:.2f} {metrics.currency} "
            f"({metrics.upside_pe_pct:+.1f} %)"
            if metrics.upside_pe_pct is not None
            else f"Prix cible PE : {metrics.target_price_pe:.2f} {metrics.currency}"
        )
    if metrics.dcf.available and metrics.dcf.upside_pct is not None:
        lines.append(
            f"Valeur DCF : {metrics.dcf.value_per_share:.2f} {metrics.currency} "
            f"({metrics.dcf.upside_pct:+.1f} %)"
        )
    if metrics.technical is not None and metrics.technical.has_signal:
        lines.append(
            f"Technique : {metrics.technical.signal} "
            f"(momentum 20 j {metrics.technical.momentum_20d_pct:+.1f} %)"
        )
    if metrics.insider is not None and metrics.insider.available:
        lines.append(f"Initiés : {metrics.insider.verdict()}")
    if plan is not None and plan.suggested_weight_pct > 0:
        stop = f", stop {plan.stop_loss_price}" if plan.stop_loss_price else ""
        lines.append(f"Taille suggérée : {plan.suggested_weight_pct:.2f} % du portefeuille{stop}")

    risks = scores.risk_factors[:3]
    if risks:
        lines.append("")
        lines.append("Risques :")
        lines.extend(f"- {item}" for item in risks)

    opportunities = scores.opportunity_factors[:3]
    if opportunities:
        lines.append("")
        lines.append("Opportunités :")
        lines.extend(f"- {item}" for item in opportunities)

    if scores.missing_inputs:
        lines.append("")
        lines.append(f"Données manquantes : {len(scores.missing_inputs)} critère(s).")

    lines.append("")
    lines.append("Aide à la décision automatisée — pas un conseil en investissement.")
    return _sanitize_plain("\n".join(lines), MAX_TELEGRAM_CHARS)


class TelegramNotifier:
    def __init__(self, config: Config, http: HttpClient) -> None:
        self.config = config
        self.http = http

    @property
    def enabled(self) -> bool:
        return self.config.telegram_enabled

    def send(self, text: str) -> bool:
        """Envoie le message. Retourne ``False`` sur échec, sans lever."""
        if not self.enabled:
            log.debug("Telegram non configuré : envoi ignoré")
            return False
        url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": _sanitize_plain(text, MAX_TELEGRAM_CHARS),
            # Pas de parse_mode : le texte est rendu littéralement.
            "disable_web_page_preview": True,
            "disable_notification": False,
        }
        try:
            response = self.http.post_json(url, payload)
        except OsintError as exc:
            log.warning("envoi Telegram échoué : %s", exc)
            return False
        if isinstance(response, dict) and response.get("ok") is True:
            log.info("alerte Telegram envoyée")
            return True
        log.warning("Telegram a refusé le message (réponse inattendue)")
        return False

    def send_analysis(
        self, metrics: Metrics, scores: ScoreResult, plan: PositionPlan | None = None
    ) -> bool:
        return self.send(build_message(metrics, scores, plan))
