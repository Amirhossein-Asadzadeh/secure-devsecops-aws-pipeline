import logging
import os
import time

import psycopg2
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)


@app.before_request
def _start_timer():
    request._start_time = time.time()


@app.after_request
def _record_metrics(response):
    latency = time.time() - getattr(request, "_start_time", time.time())
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.path,
    ).observe(latency)
    return response


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def _db_params() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "dbname": os.getenv("DB_NAME", "appdb"),
        "user": os.getenv("DB_USER", "appuser"),
        "password": os.getenv("DB_PASSWORD"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "connect_timeout": 5,
    }


def get_db():
    """Return a per-request psycopg2 connection, creating it on first call."""
    if "db" not in g:
        g.db = psycopg2.connect(**_db_params())
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the items table if it does not exist.

    Skipped silently when DB_HOST is not set (e.g. local dev without Docker).
    """
    if not os.getenv("DB_HOST"):
        logger.info("DB_HOST not set — skipping database initialisation")
        return
    try:
        conn = psycopg2.connect(**_db_params())
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id         SERIAL PRIMARY KEY,
                    name       VARCHAR(255) NOT NULL,
                    status     VARCHAR(50)  NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()
        conn.close()
        logger.info("Database initialised successfully")
    except Exception:
        logger.exception("Failed to initialise database — app will start without DB")


# ---------------------------------------------------------------------------
# Application routes
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "version": os.getenv("APP_VERSION", "1.0.0")})


@app.route("/api/v1/items", methods=["GET"])
def list_items():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, status FROM items ORDER BY id")
            rows = cur.fetchall()
        items = [{"id": r[0], "name": r[1], "status": r[2]} for r in rows]
        logger.info("Listed %d items", len(items))
        return jsonify({"items": items, "count": len(items)})
    except Exception:
        logger.exception("Failed to list items")
        return jsonify({"error": "database error"}), 503


@app.route("/api/v1/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True)
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO items (name, status) VALUES (%s, %s) RETURNING id, name, status",
                (data["name"], data.get("status", "active")),
            )
            row = cur.fetchone()
        conn.commit()
        item = {"id": row[0], "name": row[1], "status": row[2]}
        logger.info("Created item: %s", item["name"])
        return jsonify(item), 201
    except Exception:
        logger.exception("Failed to create item")
        return jsonify({"error": "database error"}), 503


@app.route("/metrics", methods=["GET"])
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
