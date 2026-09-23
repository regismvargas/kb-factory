from __future__ import annotations

import sqlite3

from .paths import DB_PATH, missing_db_message
from .schema import ensure_schema, schema_is_current

# Sessions in several worktrees may share one project KB; wait for a writer
# instead of failing immediately with "database is locked".
BUSY_TIMEOUT_SECONDS = 30


def connect(*, create: bool = False) -> sqlite3.Connection:
    """Open the KB for writing.

    Only `init` passes ``create=True``: every other command fails closed when
    the database is missing instead of silently creating an empty KB.
    """
    if not create and not DB_PATH.is_file():
        raise SystemExit(missing_db_message())
    conn = sqlite3.connect(DB_PATH, timeout=BUSY_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    ensure_schema(conn)
    return conn


def connect_readonly() -> sqlite3.Connection:
    """Open the KB for pure reads without modifying the database file.

    Falls back to a writable connection only while the schema still needs a
    migration, which is a one-time legitimate write.
    """
    if not DB_PATH.is_file():
        raise SystemExit(missing_db_message())
    uri = DB_PATH.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    if schema_is_current(conn):
        return conn
    conn.close()
    return connect()
