"""Client HTTP durci (stdlib uniquement).

Failles corrigées par rapport à l'original (qui laissait chaque module appeler
le réseau comme il voulait) :

* **Aucun timeout** → blocage indéfini du processus sur un serveur lent.
* **Aucune limite de taille** → une réponse hostile de plusieurs Go faisait
  exploser la mémoire.
* **Redirections suivies aveuglément** → un 302 vers ``http://`` ou vers un
  hôte tiers exfiltrait les en-têtes (dont ``Authorization``).
* **Aucune limitation de débit** → bannissement immédiat par la SEC (10 req/s
  maximum, User-Agent nominatif obligatoire).
* **Pas de reprise sur erreur** → une 503 transitoire cassait toute l'analyse.

Le client applique : HTTPS obligatoire, allowlist d'hôtes appliquée aussi aux
redirections, timeout, plafond d'octets lus, seau à jetons, et reprise avec
backoff exponentiel plus gigue.
"""

from __future__ import annotations

import json
import random
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from .errors import HttpError, SecurityError
from .logging_setup import get_logger

log = get_logger(__name__)

#: Seuls ces hôtes peuvent être contactés. Toute autre destination est un bug
#: ou une tentative de SSRF.
DEFAULT_ALLOWED_HOSTS = frozenset(
    {
        "www.sec.gov",
        "data.sec.gov",
        "query1.finance.yahoo.com",
        "query2.finance.yahoo.com",
        "stooq.com",
        "api.telegram.org",
        "api.deepseek.com",
        "api.moonshot.cn",
        "open.bigmodel.cn",
    }
)

#: Hôtes dont les URL peuvent apparaître comme liens dans le rapport HTML.
LINKABLE_HOSTS = frozenset({"www.sec.gov", "data.sec.gov"})

_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class RateLimiter:
    """Seau à jetons simple, sûr entre threads."""

    def __init__(self, rate_per_second: float, burst: int | None = None) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second doit être > 0")
        self._rate = float(rate_per_second)
        self._capacity = float(burst if burst is not None else max(1.0, rate_per_second))
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Bloque jusqu'à disponibilité d'un jeton. Retourne l'attente subie."""
        with self._lock:
            now = time.monotonic()
            self._tokens = min(self._capacity, self._tokens + (now - self._updated) * self._rate)
            self._updated = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0
            wait = (1.0 - self._tokens) / self._rate
            self._tokens = 0.0
            self._updated = now + wait
        time.sleep(wait)
        return wait


class _StrictRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Revalide chaque redirection contre l'allowlist."""

    max_redirections = 3

    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        self._allowed = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self._allowed:
            raise SecurityError(f"redirection refusée vers un hôte non autorisé : {parsed.scheme}://{parsed.hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpClient:
    """Client GET/POST JSON contraint."""

    def __init__(
        self,
        user_agent: str,
        allowed_hosts: frozenset[str] = DEFAULT_ALLOWED_HOSTS,
        timeout: float = 15.0,
        retries: int = 3,
        max_bytes: int = 12 * 1024 * 1024,
        requests_per_second: float = 5.0,
        sleeper=time.sleep,
    ) -> None:
        self.user_agent = user_agent
        self.allowed_hosts = frozenset(allowed_hosts)
        self.timeout = float(timeout)
        self.retries = max(0, int(retries))
        self.max_bytes = int(max_bytes)
        self._limiter = RateLimiter(requests_per_second)
        self._sleep = sleeper
        self._opener = urllib.request.build_opener(
            _StrictRedirectHandler(self.allowed_hosts),
            urllib.request.HTTPSHandler(),
        )
        # On n'annonce pas gzip : évite les bombes de décompression.
        self._opener.addheaders = []

    # ------------------------------------------------------------------ API

    def get_bytes(self, url: str, accept: str = "application/json") -> bytes:
        return self._request("GET", url, accept=accept)

    def get_json(self, url: str) -> Any:
        return self._decode_json(self.get_bytes(url), url)

    def get_text(self, url: str, accept: str = "text/plain") -> str:
        return self.get_bytes(url, accept=accept).decode("utf-8", errors="replace")

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        raw = self._request("POST", url, body=body, headers=headers, accept="application/json")
        return self._decode_json(raw, url)

    # ------------------------------------------------------------- interne

    def _check_url(self, url: str) -> str:
        if not isinstance(url, str) or any(c in url for c in "\r\n\x00"):
            raise SecurityError("URL invalide (caractères de contrôle)")
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise SecurityError(f"schéma refusé : {parsed.scheme!r} (HTTPS obligatoire)")
        if parsed.username or parsed.password:
            raise SecurityError("identifiants interdits dans l'URL")
        host = (parsed.hostname or "").lower()
        if host not in self.allowed_hosts:
            raise SecurityError(f"hôte hors allowlist : {host!r}")
        return host

    def _request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        accept: str = "application/json",
    ) -> bytes:
        self._check_url(url)

        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("User-Agent", self.user_agent)
        request.add_header("Accept", accept)
        request.add_header("Accept-Encoding", "identity")
        request.add_header("Connection", "close")
        if body is not None:
            request.add_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (headers or {}).items():
            if any(c in f"{key}{value}" for c in "\r\n\x00"):
                raise SecurityError("injection d'en-tête HTTP détectée")
            request.add_header(key, value)

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._limiter.acquire()
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    return self._read_capped(response, url)
            except urllib.error.HTTPError as exc:
                # Le corps d'erreur peut contenir des détails serveur : on ne le
                # journalise pas, seulement le code.
                exc.close()
                last_error = HttpError(f"HTTP {exc.code} sur {_safe_url(url)}")
                if exc.code not in _RETRYABLE_STATUS:
                    raise last_error from None
            except SecurityError:
                raise
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
                last_error = HttpError(f"échec réseau sur {_safe_url(url)} : {exc.__class__.__name__}")

            if attempt < self.retries:
                delay = min(8.0, (2**attempt)) * (0.5 + random.random() / 2)
                log.debug("nouvelle tentative dans %.1fs (%s)", delay, _safe_url(url))
                self._sleep(delay)

        raise last_error or HttpError(f"échec sur {_safe_url(url)}")

    def _read_capped(self, response, url: str) -> bytes:
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            raise SecurityError(
                f"réponse trop volumineuse ({declared} octets) sur {_safe_url(url)}"
            )
        data = response.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise SecurityError(f"réponse tronquée : plafond {self.max_bytes} octets atteint")
        return data

    @staticmethod
    def _decode_json(raw: bytes, url: str) -> Any:
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpError(f"réponse non JSON depuis {_safe_url(url)} : {exc}") from None


def _safe_url(url: str) -> str:
    """URL réduite à schéma+hôte+chemin : jamais de query string en log.

    Les jetons voyagent parfois en paramètre (Telegram met le jeton dans le
    chemin) ; on ne garde que l'hôte pour les messages d'erreur.
    """
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.hostname}"
    except ValueError:  # pragma: no cover
        return "<url invalide>"
