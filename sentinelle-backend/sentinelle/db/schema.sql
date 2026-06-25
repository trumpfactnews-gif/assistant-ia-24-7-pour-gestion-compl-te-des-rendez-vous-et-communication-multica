-- Schéma de la base communautaire Sentinelle (SQLite).
-- Conçu pour migrer facilement vers PostgreSQL à l'échelle.

-- Signalements bruts. Un numéro de téléphone n'est JAMAIS stocké en clair :
-- on conserve son condensé salé (voir utils/privacy.py). Les domaines, qui ne
-- sont pas des données personnelles, sont stockés en clair (domaine enregistrable).
CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type     TEXT NOT NULL CHECK (target_type IN ('number', 'domain')),
    target_value    TEXT NOT NULL,            -- numéro: hash ; domaine: clair
    target_display  TEXT,                      -- forme masquée affichable
    category        TEXT,
    reporter_hash   TEXT,                      -- rapporteur (hashé) pour compter les signalements distincts
    message_hash    TEXT,                      -- déduplication de contenu
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_target
    ON reports (target_type, target_value);
CREATE INDEX IF NOT EXISTS idx_reports_reporter
    ON reports (target_type, target_value, reporter_hash);

-- Liste de blocage agrégée, dérivée des signalements.
-- Une cible devient « bloquée » une fois le seuil de rapporteurs distincts atteint.
CREATE TABLE IF NOT EXISTS blocklist (
    target_type        TEXT NOT NULL,
    target_value       TEXT NOT NULL,
    target_display     TEXT,
    category           TEXT,
    report_count       INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'revoked')),
    first_reported_at  TEXT,
    last_reported_at   TEXT,
    PRIMARY KEY (target_type, target_value)
);

CREATE INDEX IF NOT EXISTS idx_blocklist_status
    ON blocklist (target_type, status);
