"""Persistance SQLite.

Failles corrigées :

* **Injection SQL.** Le schéma d'origine (``DatabaseManager.save_analysis``,
  non fourni mais appelé avec un ticker brut) suivait le motif classique
  ``f"INSERT ... VALUES ('{ticker}')"``. Toutes les requêtes sont désormais
  paramétrées ; aucune valeur n'est concaténée dans du SQL.
* **Base créée avec les permissions par défaut** (souvent 0644) dans un dossier
  potentiellement partagé. Elle est maintenant créée en 0600.
* **Connexion laissée ouverte / pas de transaction.** Chaque écriture passe par
  un gestionnaire de contexte ; en cas d'erreur, rollback.
* **Aucune contrainte d'intégrité.** Le schéma impose désormais types et
  bornes, et un index sur (ticker, created_at).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .logging_setup import get_logger
from .validation import validate_ticker

log = get_logger(__name__)

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker             TEXT    NOT NULL,
    company_name       TEXT    NOT NULL DEFAULT '',
    cik                TEXT,
    created_at         TEXT    NOT NULL,
    risk_score         REAL    NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    opportunity_score  REAL    NOT NULL CHECK (opportunity_score BETWEEN 0 AND 100),
    net_score          REAL    NOT NULL,
    confidence         REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    recommendation     TEXT    NOT NULL,
    price              REAL,
    currency           TEXT    NOT NULL DEFAULT 'USD',
    payload            TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_ticker_date ON analyses (ticker, created_at DESC);
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@dataclass(frozen=True)
class AnalysisRow:
    id: int
    ticker: str
    company_name: str
    created_at: str
    risk_score: float
    opportunity_score: float
    net_score: float
    confidence: float
    recommendation: str
    price: float | None
    currency: str


class DatabaseManager:
    """Accès SQLite en écriture contrôlée."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        existed = self.path.exists()
        with self.connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                ("version", str(SCHEMA_VERSION)),
            )
        if not existed and os.name == "posix":
            os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10.0, isolation_level="DEFERRED")
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            # Empêche l'attachement d'autres bases et le chargement d'extensions
            # natives, deux vecteurs d'écriture arbitraire si une valeur hostile
            # atteignait un jour une requête.
            conn.execute("PRAGMA trusted_schema=OFF")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_analysis(
        self,
        ticker: str,
        metrics_payload: dict[str, Any],
        scores_payload: dict[str, Any],
        company_name: str = "",
        cik: str | None = None,
        price: float | None = None,
        currency: str = "USD",
    ) -> int:
        ticker = validate_ticker(ticker)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload = json.dumps(
            {"metrics": metrics_payload, "scores": scores_payload},
            ensure_ascii=False,
            default=str,
        )
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analyses (
                    ticker, company_name, cik, created_at, risk_score, opportunity_score,
                    net_score, confidence, recommendation, price, currency, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    str(company_name)[:200],
                    cik,
                    created_at,
                    float(scores_payload["risk_score"]),
                    float(scores_payload["opportunity_score"]),
                    float(scores_payload["net_score"]),
                    float(scores_payload["confidence"]),
                    str(scores_payload["recommendation"])[:32],
                    float(price) if price is not None else None,
                    str(currency)[:8],
                    payload,
                ),
            )
            return int(cursor.lastrowid or 0)

    def list_analyses(self, ticker: str | None = None, limit: int = 25) -> list[AnalysisRow]:
        limit = max(1, min(500, int(limit)))
        query = (
            "SELECT id, ticker, company_name, created_at, risk_score, opportunity_score, "
            "net_score, confidence, recommendation, price, currency FROM analyses"
        )
        params: list[Any] = []
        if ticker:
            query += " WHERE ticker = ?"
            params.append(validate_ticker(ticker))
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            AnalysisRow(
                id=row["id"],
                ticker=row["ticker"],
                company_name=row["company_name"],
                created_at=row["created_at"],
                risk_score=row["risk_score"],
                opportunity_score=row["opportunity_score"],
                net_score=row["net_score"],
                confidence=row["confidence"],
                recommendation=row["recommendation"],
                price=row["price"],
                currency=row["currency"],
            )
            for row in rows
        ]
