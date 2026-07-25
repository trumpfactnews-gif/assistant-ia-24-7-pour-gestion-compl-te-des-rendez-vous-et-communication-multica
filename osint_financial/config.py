"""Chargement et validation de la configuration.

Failles corrigées :

* ``.env`` chargé sans contrôle : l'original dépendait d'un fichier de clés au
  milieu du code source, sans ``.gitignore`` ni contrôle de permissions. On
  vérifie ici que le fichier n'est pas lisible par le monde (POSIX) et on
  refuse de continuer sinon.
* Secrets réutilisés partout : ils sont désormais enregistrés auprès du filtre
  d'expurgation dès le chargement, donc masqués dans toute trace ultérieure.
* SEC EDGAR **exige** un User-Agent nominatif avec courriel de contact. Sans
  lui, l'adresse IP est bannie ; l'original n'en envoyait aucun.
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError
from .logging_setup import get_logger, register_secret

log = get_logger(__name__)

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_ENV_LINE_RE = re.compile(r"\A\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\Z")

#: Valeurs traitées comme « non renseigné » plutôt que comme un secret.
_PLACEHOLDERS = {"", "changeme", "todo", "xxx", "your-key-here", "none", "null"}


def load_env_file(path: Path) -> dict[str, str]:
    """Lit un fichier ``.env`` minimal sans dépendance externe.

    Ne remplace jamais une variable déjà présente dans l'environnement : en
    production, les secrets viennent du gestionnaire de secrets, pas du disque.
    """
    values: dict[str, str] = {}
    if not path.is_file():
        return values

    if os.name == "posix":
        mode = path.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            raise ConfigError(
                f"{path} est lisible par le groupe ou par tous "
                f"(mode {stat.filemode(mode)}). Corrigez : chmod 600 {path}"
            )

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _ENV_LINE_RE.match(line)
        if not match:
            log.warning("%s:%d ignorée (syntaxe invalide)", path, lineno)
            continue
        key, raw = match.group(1), match.group(2).strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        values[key] = raw
    return values


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return None if value.lower() in _PLACEHOLDERS else value


@dataclass(frozen=True)
class Config:
    """Configuration effective d'une exécution."""

    sec_user_agent: str
    output_dir: Path
    db_path: Path
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    deepseek_api_key: str | None = None
    http_timeout: float = 15.0
    http_retries: int = 3
    max_response_bytes: int = 12 * 1024 * 1024
    requests_per_second: float = 5.0
    llm_max_output_tokens: int = 300
    _secrets: tuple[str, ...] = field(default=(), repr=False)

    # `repr` masque les secrets : un `print(config)` accidentel ne fuit rien.
    def __repr__(self) -> str:  # pragma: no cover - confort de débogage
        return (
            f"Config(sec_user_agent={self.sec_user_agent!r}, "
            f"output_dir={self.output_dir}, db_path={self.db_path}, "
            f"telegram={'oui' if self.telegram_enabled else 'non'}, "
            f"deepseek={'oui' if self.deepseek_enabled else 'non'})"
        )

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    @property
    def deepseek_enabled(self) -> bool:
        return bool(self.deepseek_api_key)


def load_config(
    env_file: Path | None = None,
    output_dir: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Config:
    """Assemble la configuration : environnement > fichier ``.env`` > défauts."""
    environ = dict(os.environ if environ is None else environ)
    file_values = load_env_file(env_file) if env_file else {}
    merged = {**file_values, **environ}

    user_agent = _clean(merged.get("SEC_USER_AGENT"))
    if not user_agent:
        raise ConfigError(
            "SEC_USER_AGENT manquant. La SEC impose un User-Agent nominatif, "
            'par exemple : SEC_USER_AGENT="Fluxor Research contact@exemple.com"'
        )
    if not _EMAIL_RE.search(user_agent):
        raise ConfigError(
            "SEC_USER_AGENT doit contenir une adresse de contact "
            "(politique d'accès data.sec.gov)."
        )
    if len(user_agent) > 200 or any(c in user_agent for c in "\r\n\x00"):
        raise ConfigError("SEC_USER_AGENT invalide (trop long ou caractères de contrôle)")

    out = Path(output_dir or _clean(merged.get("OSINT_OUTPUT_DIR")) or "osint_reports")
    out = out.expanduser().resolve()

    db_path = Path(
        _clean(merged.get("OSINT_DB_PATH")) or out / "osint_database.db"
    ).expanduser().resolve()

    telegram_token = _clean(merged.get("TELEGRAM_BOT_TOKEN"))
    telegram_chat = _clean(merged.get("TELEGRAM_CHAT_ID"))
    deepseek_key = _clean(merged.get("DEEPSEEK_API_KEY"))

    if telegram_chat and not re.fullmatch(r"-?\d{1,20}", telegram_chat):
        raise ConfigError("TELEGRAM_CHAT_ID doit être un identifiant numérique")

    secrets = tuple(s for s in (telegram_token, deepseek_key) if s)
    for secret in secrets:
        register_secret(secret)

    return Config(
        sec_user_agent=user_agent,
        output_dir=out,
        db_path=db_path,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat,
        deepseek_api_key=deepseek_key,
        http_timeout=_positive_float(merged.get("OSINT_HTTP_TIMEOUT"), 15.0),
        http_retries=int(_positive_float(merged.get("OSINT_HTTP_RETRIES"), 3.0)),
        requests_per_second=_positive_float(merged.get("OSINT_RPS"), 5.0),
        _secrets=secrets,
    )


def _positive_float(raw: str | None, default: float) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"valeur numérique invalide : {raw!r}") from exc
    if value <= 0 or value > 3600:
        raise ConfigError(f"valeur hors bornes : {value}")
    return value
