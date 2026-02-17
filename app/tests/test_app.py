import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_conn(fetchall=None, fetchone=None):
    """Build a mock psycopg2 connection with pre-configured cursor results.

    The cursor is used as a context manager (`with conn.cursor() as cur:`),
    so we configure __enter__ on the cursor's return value.
    """
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = fetchall or []
    cur.fetchone.return_value = fetchone
    return conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert "version" in data


# ---------------------------------------------------------------------------
# GET /api/v1/items
# ---------------------------------------------------------------------------
@patch("main.get_db")
def test_list_items(mock_get_db, client):
    mock_get_db.return_value = _mock_conn(
        fetchall=[
            (1, "Secure Pipeline", "active"),
            (2, "Cloud Deploy", "active"),
        ]
    )
    resp = client.get("/api/v1/items")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert data["count"] == len(data["items"])
    assert data["count"] == 2


@patch("main.get_db")
def test_list_items_db_error(mock_get_db, client):
    mock_get_db.side_effect = Exception("connection refused")
    resp = client.get("/api/v1/items")
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "database error"


# ---------------------------------------------------------------------------
# POST /api/v1/items
# ---------------------------------------------------------------------------
@patch("main.get_db")
def test_create_item_success(mock_get_db, client):
    mock_get_db.return_value = _mock_conn(fetchone=(3, "New Item", "active"))
    resp = client.post(
        "/api/v1/items",
        json={"name": "New Item"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "New Item"
    assert data["status"] == "active"


def test_create_item_missing_name(client):
    resp = client.post(
        "/api/v1/items",
        json={"description": "no name"},
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


@patch("main.get_db")
def test_create_item_db_error(mock_get_db, client):
    mock_get_db.side_effect = Exception("connection refused")
    resp = client.post(
        "/api/v1/items",
        json={"name": "New Item"},
        content_type="application/json",
    )
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "database error"


# ---------------------------------------------------------------------------
# /metrics
# ---------------------------------------------------------------------------
def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"http_requests_total" in resp.data
