"""Dépôt de données communautaires.

Gère les signalements et la liste de blocage agrégée. Implémente le contrat
`CommunitySource` attendu par le moteur de détection.

Règle communautaire : une cible (numéro ou domaine) devient *bloquée* dès que le
nombre de rapporteurs **distincts** atteint le seuil configuré. Cela protège
contre les signalements abusifs d'un seul acteur.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from ..detection.url_analysis import registrable_domain
from ..utils import privacy
from .database import get_connection, init_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_domain(raw: str) -> str:
    """Réduit une URL ou un hôte à son domaine enregistrable (minuscule)."""
    if not raw:
        return ""
    candidate = raw.strip().lower()
    if "://" not in candidate:
        candidate = "http://" + candidate
    host = urlparse(candidate).netloc.split("@")[-1].split(":")[0]
    return registrable_domain(host or raw.strip().lower())


class Repository:
    def __init__(self, db_path: str, block_threshold: int = 3):
        self.db_path = db_path
        self.block_threshold = block_threshold

    def init(self) -> None:
        init_db(self.db_path)

    # -- Écriture ----------------------------------------------------------
    def add_report(self, target_type: str, raw_value: str, category: str | None = None,
                   reporter_id: str | None = None, message: str | None = None) -> dict:
        if target_type not in ("number", "domain"):
            raise ValueError("target_type doit être 'number' ou 'domain'")
        if not raw_value or not raw_value.strip():
            raise ValueError("raw_value est requis")

        if target_type == "number":
            value = privacy.hash_phone(raw_value)
            display = privacy.mask_phone(raw_value)
            if not value:
                raise ValueError("numéro de téléphone invalide")
        else:
            value = normalize_domain(raw_value)
            display = value
            if not value:
                raise ValueError("domaine invalide")

        reporter_hash = privacy.hash_text(reporter_id) if reporter_id else None
        message_hash = privacy.hash_text(message) if message else None
        now = _now()

        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT INTO reports
                   (target_type, target_value, target_display, category,
                    reporter_hash, message_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (target_type, value, display, category, reporter_hash, message_hash, now),
            )
            count = self._distinct_reporters(conn, target_type, value)
            conn.execute(
                """INSERT INTO blocklist
                   (target_type, target_value, target_display, category,
                    report_count, status, first_reported_at, last_reported_at)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                   ON CONFLICT(target_type, target_value) DO UPDATE SET
                       report_count   = excluded.report_count,
                       last_reported_at = excluded.last_reported_at,
                       target_display = excluded.target_display,
                       category       = COALESCE(blocklist.category, excluded.category)""",
                (target_type, value, display, category, count, now, now),
            )

        return {
            "target_type": target_type,
            "target_display": display,
            "category": category,
            "report_count": count,
            "blocked": count >= self.block_threshold,
            "block_threshold": self.block_threshold,
        }

    # -- Lecture -----------------------------------------------------------
    def is_number_blocked(self, phone: str) -> bool:
        return self._is_blocked("number", privacy.hash_phone(phone))

    def is_domain_blocked(self, domain: str) -> bool:
        return self._is_blocked("domain", normalize_domain(domain))

    def lookup_number(self, phone: str) -> dict:
        return self._lookup("number", privacy.hash_phone(phone), privacy.mask_phone(phone))

    def lookup_domain(self, domain: str) -> dict:
        value = normalize_domain(domain)
        return self._lookup("domain", value, value)

    def get_stats(self) -> dict:
        with get_connection(self.db_path) as conn:
            total_reports = conn.execute("SELECT COUNT(*) AS c FROM reports").fetchone()["c"]
            rows = conn.execute(
                """SELECT target_type,
                          SUM(CASE WHEN report_count >= ? AND status='active'
                                   THEN 1 ELSE 0 END) AS blocked,
                          COUNT(*) AS total
                   FROM blocklist GROUP BY target_type""",
                (self.block_threshold,),
            ).fetchall()
        by_type = {r["target_type"]: {"blocked": r["blocked"], "total": r["total"]} for r in rows}
        return {
            "total_reports": total_reports,
            "blocked_numbers": by_type.get("number", {}).get("blocked", 0) or 0,
            "tracked_numbers": by_type.get("number", {}).get("total", 0) or 0,
            "blocked_domains": by_type.get("domain", {}).get("blocked", 0) or 0,
            "tracked_domains": by_type.get("domain", {}).get("total", 0) or 0,
            "block_threshold": self.block_threshold,
        }

    # -- Internes ----------------------------------------------------------
    @staticmethod
    def _distinct_reporters(conn, target_type: str, value: str) -> int:
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM (
                   SELECT DISTINCT COALESCE(reporter_hash, CAST(id AS TEXT)) AS r
                   FROM reports WHERE target_type = ? AND target_value = ?
               )""",
            (target_type, value),
        ).fetchone()
        return int(row["c"])

    def _is_blocked(self, target_type: str, value: str) -> bool:
        if not value:
            return False
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """SELECT report_count, status FROM blocklist
                   WHERE target_type = ? AND target_value = ?""",
                (target_type, value),
            ).fetchone()
        return bool(row and row["status"] == "active"
                    and row["report_count"] >= self.block_threshold)

    def _lookup(self, target_type: str, value: str, display: str) -> dict:
        result = {"blocked": False, "report_count": 0, "category": None, "display": display}
        if not value:
            return result
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """SELECT report_count, status, category, target_display FROM blocklist
                   WHERE target_type = ? AND target_value = ?""",
                (target_type, value),
            ).fetchone()
        if row:
            result["report_count"] = row["report_count"]
            result["category"] = row["category"]
            result["display"] = row["target_display"] or display
            result["blocked"] = (row["status"] == "active"
                                 and row["report_count"] >= self.block_threshold)
        return result
