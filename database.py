"""
database.py — Unified SQLite / PostgreSQL connection layer.

* Development : DATABASE_URL is blank → uses SQLite (bot.db)
* Production  : DATABASE_URL is a postgres:// URL → uses PostgreSQL
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

DATABASE_URL: str | None = os.getenv("DATABASE_URL")
IS_POSTGRES: bool = bool(DATABASE_URL)

# ── Compatibility shim ────────────────────────────────────────────────────────
# psycopg2 uses %s placeholders; sqlite3 uses ?.
# All code uses "?" — this shim replaces them for postgres at query time.

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras

    class _PgConn:
        """Thin wrapper that makes psycopg2 look like sqlite3 for simple cases."""

        def __init__(self, dsn: str):
            self._conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
            self._conn.autocommit = False

        def execute(self, sql: str, params=()) -> "_PgCursor":
            sql = sql.replace("?", "%s")
            # SQLite INTEGER PRIMARY KEY AUTOINCREMENT → serial
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return _PgCursor(cur)

        def executemany(self, sql: str, seq):
            sql = sql.replace("?", "%s")
            cur = self._conn.cursor()
            cur.executemany(sql, seq)

        def commit(self):
            self._conn.commit()

        def close(self):
            self._conn.close()

    class _PgCursor:
        def __init__(self, cur):
            self._cur = cur

        def fetchone(self):
            return self._cur.fetchone()   # RealDictRow behaves like dict

        def fetchall(self):
            return self._cur.fetchall()

    def get_conn() -> _PgConn:
        return _PgConn(DATABASE_URL)

else:
    SQLITE_PATH = os.path.join(os.path.dirname(__file__), "bot.db")

    def dict_factory(cursor, row):
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def get_conn() -> sqlite3.Connection:
        conn = sqlite3.connect(SQLITE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = dict_factory
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


# ── Schema ────────────────────────────────────────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT,
    joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vouchers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    price       REAL NOT NULL DEFAULT 0,
    disclaimer  TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS codes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_id    INTEGER NOT NULL,
    code          TEXT NOT NULL,
    is_used       INTEGER NOT NULL DEFAULT 0,
    used_in_order TEXT,
    FOREIGN KEY (voucher_id) REFERENCES vouchers(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id           TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    voucher_id   INTEGER NOT NULL,
    voucher_name TEXT NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    total_price  REAL NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending',
    utr          TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_at    TIMESTAMP,
    approved_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_codes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    code     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS used_utrs (
    utr        TEXT PRIMARY KEY,
    order_id   TEXT NOT NULL,
    used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channels (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    link  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id         TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    username   TEXT,
    full_name  TEXT,
    category   TEXT NOT NULL,
    message    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_replies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  TEXT NOT NULL,
    from_admin INTEGER NOT NULL DEFAULT 0,
    message    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT,
    joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vouchers (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    price       NUMERIC(10,2) NOT NULL DEFAULT 0,
    disclaimer  TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS codes (
    id            SERIAL PRIMARY KEY,
    voucher_id    INTEGER NOT NULL,
    code          TEXT NOT NULL,
    is_used       INTEGER NOT NULL DEFAULT 0,
    used_in_order TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id           TEXT PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    voucher_id   INTEGER NOT NULL,
    voucher_name TEXT NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    total_price  NUMERIC(10,2) NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending',
    utr          TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_at    TIMESTAMP,
    approved_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_codes (
    id       SERIAL PRIMARY KEY,
    order_id TEXT NOT NULL,
    code     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS used_utrs (
    utr       TEXT PRIMARY KEY,
    order_id  TEXT NOT NULL,
    used_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channels (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    link TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id         TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    username   TEXT,
    full_name  TEXT,
    category   TEXT NOT NULL,
    message    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_replies (
    id         SERIAL PRIMARY KEY,
    ticket_id  TEXT NOT NULL,
    from_admin INTEGER NOT NULL DEFAULT 0,
    message    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    schema = _PG_SCHEMA if IS_POSTGRES else _SQLITE_SCHEMA
    for statement in schema.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()
    logger.info(f"DB init OK ({'PostgreSQL' if IS_POSTGRES else 'SQLite'})")
