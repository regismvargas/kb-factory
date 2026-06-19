from __future__ import annotations

import sqlite3

from .config import load_config


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL,
            tier TEXT NOT NULL,
            source TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status_changed_at TEXT NOT NULL,
            tier_changed_at TEXT NOT NULL,
            tier_reason TEXT,
            review_after TEXT,
            valid_until TEXT,
            confidence REAL,
            replacement_id TEXT,
            supersedes_id TEXT,
            observed_at TEXT,
            resolution_notes TEXT,
            resolved_at TEXT,
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT NOT NULL,
            action TEXT NOT NULL,
            happened_at TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_records_category ON records(category);
        CREATE INDEX IF NOT EXISTS idx_records_domain ON records(domain);
        CREATE INDEX IF NOT EXISTS idx_records_status ON records(status);
        CREATE INDEX IF NOT EXISTS idx_records_tier ON records(tier);
        CREATE INDEX IF NOT EXISTS idx_records_review_after ON records(review_after);
        CREATE INDEX IF NOT EXISTS idx_records_valid_until ON records(valid_until);

        CREATE VIRTUAL TABLE IF NOT EXISTS records_fts
        USING fts5(
            id UNINDEXED,
            title,
            content,
            tags,
            source,
            domain
        );

        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            original_path TEXT,
            stored_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type TEXT,
            ingested_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            domain TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            notes TEXT,
            record_ids_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE INDEX IF NOT EXISTS idx_sources_content_hash ON sources(content_hash);
        CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources(domain);
        """
    )
    # --- v3 migration: add source_id to records (logical provenance link) ---
    try:
        conn.execute("ALTER TABLE records ADD COLUMN source_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists (idempotent re-run)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_source_id ON records(source_id)")
    # --- v4 migration: append-only operation log ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS operations (
            op_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            event TEXT NOT NULL,
            happened_at TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            summary TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_operations_category ON operations(category);
        CREATE INDEX IF NOT EXISTS idx_operations_happened_at ON operations(happened_at);
        """
    )
    # --- v5 migration: wiki foundation (pages, provenance, snapshots) ---
    # Additive only. Tables are created but not populated by this migration.
    # Wave 3+ materialization is responsible for writing page rows;
    # Wave 5+ lifecycle is responsible for snapshot rows.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS wiki_pages (
            page_id TEXT PRIMARY KEY,
            target_slug TEXT NOT NULL,
            page_class TEXT NOT NULL,
            page_type TEXT NOT NULL,
            title TEXT NOT NULL,
            domain TEXT,
            state TEXT NOT NULL DEFAULT 'managed',
            candidate_id TEXT,
            content_hash TEXT,
            stored_path TEXT,
            supporting_records_json TEXT NOT NULL DEFAULT '[]',
            supporting_sources_json TEXT NOT NULL DEFAULT '[]',
            confidence REAL,
            superseded_by TEXT,
            snapshot_of TEXT,
            generated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_wiki_pages_slug ON wiki_pages(target_slug);
        CREATE INDEX IF NOT EXISTS idx_wiki_pages_class ON wiki_pages(page_class);
        CREATE INDEX IF NOT EXISTS idx_wiki_pages_state ON wiki_pages(state);
        CREATE INDEX IF NOT EXISTS idx_wiki_pages_domain ON wiki_pages(domain);
        CREATE INDEX IF NOT EXISTS idx_wiki_pages_snapshot_of ON wiki_pages(snapshot_of);

        CREATE TABLE IF NOT EXISTS wiki_page_provenance (
            page_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            weight REAL,
            PRIMARY KEY (page_id, kind, ref_id)
        );

        CREATE INDEX IF NOT EXISTS idx_wiki_page_provenance_ref ON wiki_page_provenance(kind, ref_id);

        CREATE TABLE IF NOT EXISTS wiki_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            live_page_id TEXT NOT NULL,
            taken_at TEXT NOT NULL,
            reason TEXT,
            content_hash TEXT,
            stored_path TEXT,
            FOREIGN KEY (live_page_id) REFERENCES wiki_pages(page_id)
        );

        CREATE INDEX IF NOT EXISTS idx_wiki_snapshots_live_page ON wiki_snapshots(live_page_id);
        CREATE INDEX IF NOT EXISTS idx_wiki_snapshots_taken_at ON wiki_snapshots(taken_at);
        """
    )
    config = load_config()
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(config.get("schema_version", 5)),),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Optional append-only hardening (opt-in DB invariant; see `kb.py harden`).
#
# By default, append-only is enforced by the CLI's interface discipline only —
# `update` refuses content edits and there is no delete verb. These triggers
# turn that convention into a real database invariant: even a direct SQLite
# session cannot edit a record's title/content or delete records / the logs.
# They are deliberately NOT installed by `ensure_schema` (opt-in), and they are
# designed to leave every legitimate operation working: `supersede`/`resolve`
# only mutate status/replacement_id/tier/timestamps (never title/content), and
# nothing in the runtime deletes from `records`.
# ---------------------------------------------------------------------------

HARDENING_TRIGGERS = {
    "kbf_records_no_content_update": """
        CREATE TRIGGER kbf_records_no_content_update
        BEFORE UPDATE ON records
        FOR EACH ROW WHEN NEW.title IS NOT OLD.title OR NEW.content IS NOT OLD.content
        BEGIN
            SELECT RAISE(ABORT, 'append-only: record title/content is immutable; use supersede to create a new version');
        END;
    """,
    "kbf_records_no_delete": """
        CREATE TRIGGER kbf_records_no_delete
        BEFORE DELETE ON records
        BEGIN
            SELECT RAISE(ABORT, 'append-only: records cannot be deleted; supersede or resolve instead');
        END;
    """,
    "kbf_audit_log_no_update": """
        CREATE TRIGGER kbf_audit_log_no_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'append-only: audit_log is immutable');
        END;
    """,
    "kbf_audit_log_no_delete": """
        CREATE TRIGGER kbf_audit_log_no_delete
        BEFORE DELETE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'append-only: audit_log is immutable');
        END;
    """,
    "kbf_operations_no_update": """
        CREATE TRIGGER kbf_operations_no_update
        BEFORE UPDATE ON operations
        BEGIN
            SELECT RAISE(ABORT, 'append-only: operations log is immutable');
        END;
    """,
    "kbf_operations_no_delete": """
        CREATE TRIGGER kbf_operations_no_delete
        BEFORE DELETE ON operations
        BEGIN
            SELECT RAISE(ABORT, 'append-only: operations log is immutable');
        END;
    """,
}


def hardening_enabled(conn: sqlite3.Connection) -> bool:
    """True if the optional append-only triggers are installed."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = 'kbf_records_no_delete'"
    ).fetchone()
    return row is not None


def enable_hardening(conn: sqlite3.Connection) -> None:
    """Install the append-only triggers (idempotent)."""
    script = "\n".join(
        f"DROP TRIGGER IF EXISTS {name};\n{sql}"
        for name, sql in HARDENING_TRIGGERS.items()
    )
    conn.executescript(script)


def disable_hardening(conn: sqlite3.Connection) -> None:
    """Remove the append-only triggers (idempotent)."""
    script = "\n".join(
        f"DROP TRIGGER IF EXISTS {name};" for name in HARDENING_TRIGGERS
    )
    conn.executescript(script)
