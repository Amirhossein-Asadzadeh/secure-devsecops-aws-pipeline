"""Database migration runner.

Executes SQL migration files in filename order. Each migration is applied
exactly once; the ``schema_migrations`` table records which versions have
already run so re-running this script is always safe.

Usage
-----
Run directly (reads DB connection from environment variables or a .env file):

    python app/migrations/migrate.py

Environment variables (same as the application):

    DB_HOST      – hostname of the PostgreSQL server (required)
    DB_NAME      – database name              (default: appdb)
    DB_USER      – database user              (default: appuser)
    DB_PASSWORD  – database password
    DB_PORT      – port                       (default: 5432)
"""

import logging
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MIGRATIONS_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# DB helpers  (mirror _db_params from main.py so there is a single source of
# truth for the connection parameters)
# ---------------------------------------------------------------------------
def _db_params() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "dbname": os.getenv("DB_NAME", "appdb"),
        "user": os.getenv("DB_USER", "appuser"),
        "password": os.getenv("DB_PASSWORD"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "connect_timeout": 10,
    }


def _connect() -> "psycopg2.connection":
    params = _db_params()
    logger.info("Connecting to %s:%s/%s", params["host"], params["port"], params["dbname"])
    return psycopg2.connect(**params)


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------
def _ensure_migrations_table(cur) -> None:
    """Create schema_migrations if it does not exist yet."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _applied_versions(cur) -> set:
    """Return the set of migration versions already recorded in the DB."""
    cur.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def _sql_files() -> list[Path]:
    """Return .sql migration files sorted by filename (lexicographic order)."""
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_migrations(conn) -> int:
    """Apply all pending migrations. Returns the number of migrations run."""
    applied = 0

    with conn.cursor() as cur:
        _ensure_migrations_table(cur)
        conn.commit()

        already_applied = _applied_versions(cur)

        for sql_file in _sql_files():
            version = sql_file.stem  # filename without .sql extension

            if version in already_applied:
                logger.info("SKIP  %s (already applied)", version)
                continue

            logger.info("APPLY %s", version)
            sql = sql_file.read_text(encoding="utf-8")

            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            conn.commit()
            logger.info("OK    %s", version)
            applied += 1

    return applied


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    load_dotenv()

    if not os.getenv("DB_HOST"):
        logger.error("DB_HOST is not set. Export DB_HOST (and optionally DB_NAME, DB_USER, DB_PASSWORD) before running.")
        sys.exit(1)

    try:
        conn = _connect()
    except psycopg2.OperationalError as exc:
        logger.error("Could not connect to the database: %s", exc)
        sys.exit(1)

    try:
        count = run_migrations(conn)
    except Exception:
        logger.exception("Migration failed — all changes rolled back")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

    if count == 0:
        logger.info("Nothing to do — database is up to date")
    else:
        logger.info("Applied %d migration(s) successfully", count)


if __name__ == "__main__":
    main()
