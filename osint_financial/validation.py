"""Validation des entrées et confinement des chemins.

Failles corrigées ici :

* **Traversée de répertoire / écriture arbitraire.** L'original faisait
  ``ticker = args.ticker.upper()`` puis
  ``os.makedirs(f"osint_reports/{ticker}")`` et ouvrait
  ``osint_reports/{ticker}/{ticker}_report.html`` en écriture. ``.upper()``
  n'est pas un assainissement : ``--ticker ../../../../home/user/.bashrc``
  écrivait du HTML contrôlé par l'attaquant hors du dossier de travail.
* **Crash sur entrée absente.** ``args.ticker`` valait ``None`` sans
  ``--ticker`` ni ``--list`` → ``AttributeError``.
* **Injection via nom d'hôte / schéma d'URL.** Les liens de filings issus du
  réseau étaient réinjectés tels quels dans le rapport (``javascript:`` était
  cliquable).
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from .errors import ValidationError

# Symboles US : 1 à 5 lettres, éventuellement suffixées (BRK.B, RDS-A).
# L'ancrage `\A ... \Z` (et non `^...$`) évite l'acceptation d'un retour
# chariot final, qui autoriserait « AAPL\n../../etc ».
_TICKER_RE = re.compile(r"\A[A-Z][A-Z0-9]{0,4}(?:[.\-][A-Z0-9]{1,4})?\Z")

_MAX_TICKER_LEN = 10


def validate_ticker(raw: object) -> str:
    """Retourne le ticker normalisé, ou lève :class:`ValidationError`.

    Aucun caractère hors ``[A-Z0-9.-]`` ne survit : pas de séparateur de
    chemin, pas de NUL, pas d'espace, pas d'unicode homoglyphe.
    """
    if raw is None:
        raise ValidationError("aucun ticker fourni (utilisez --ticker SYMBOLE)")
    if not isinstance(raw, str):
        raise ValidationError(f"ticker de type invalide : {type(raw).__name__}")

    candidate = raw.strip().upper()
    if not candidate:
        raise ValidationError("ticker vide")
    if len(candidate) > _MAX_TICKER_LEN:
        raise ValidationError(f"ticker trop long ({len(candidate)} > {_MAX_TICKER_LEN})")
    if not _TICKER_RE.match(candidate):
        raise ValidationError(
            f"ticker invalide : {candidate!r} — attendu 1 à 5 lettres, "
            "suffixe optionnel (ex. AAPL, BRK.B)"
        )
    return candidate


def validate_cik(raw: object) -> str:
    """Normalise un CIK SEC sur 10 chiffres."""
    if isinstance(raw, int):
        raw = str(raw)
    if not isinstance(raw, str):
        raise ValidationError(f"CIK de type invalide : {type(raw).__name__}")
    match = re.fullmatch(r"(?:CIK)?[-_ ]?(\d{1,10})", raw.strip(), flags=re.IGNORECASE)
    if not match:
        raise ValidationError(f"CIK invalide : {raw!r}")
    return match.group(1).zfill(10)


def safe_child_path(base: Path, *parts: str) -> Path:
    """Résout ``base/parts...`` en garantissant le confinement sous ``base``.

    Défense en profondeur : même si un ticker malformé franchissait
    :func:`validate_ticker`, le chemin résultant est vérifié après résolution
    (``..``, liens symboliques et chemins absolus compris).
    """
    base_resolved = Path(base).resolve()
    for part in parts:
        if not isinstance(part, str) or not part:
            raise ValidationError("composant de chemin vide")
        if "\x00" in part:
            raise ValidationError("octet NUL dans le chemin")
        if Path(part).is_absolute() or part in {".", ".."} or "/" in part or "\\" in part:
            raise ValidationError(f"composant de chemin refusé : {part!r}")

    candidate = base_resolved.joinpath(*parts)
    # `resolve()` sur un chemin inexistant reste valide (strict=False).
    resolved = candidate.resolve()
    if resolved != base_resolved and base_resolved not in resolved.parents:
        raise ValidationError(f"chemin hors du répertoire autorisé : {resolved}")
    return resolved


def sanitize_url(raw: object, allowed_hosts: frozenset[str] | set[str]) -> str | None:
    """Retourne une URL sûre à rendre dans le HTML, ou ``None``.

    Refuse tout ce qui n'est pas ``https://`` vers un hôte connu : bloque
    ``javascript:``, ``data:``, ``file:``, ``http://`` en clair, et les URL
    contenant des identifiants (``https://user:pass@evil/``).
    """
    if not isinstance(raw, str) or not raw:
        return None
    raw = raw.strip()
    if len(raw) > 2048 or any(ch in raw for ch in "\r\n\t\x00"):
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme != "https":
        return None
    if parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts:
        return None
    return raw
