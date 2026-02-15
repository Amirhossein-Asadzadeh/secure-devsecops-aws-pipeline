import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import app  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_list_items(client):
    resp = client.get("/api/v1/items")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert data["count"] == len(data["items"])


def test_create_item_success(client):
    resp = client.post(
        "/api/v1/items",
        json={"name": "New Item"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "New Item"
    assert data["status"] == "created"


def test_create_item_missing_name(client):
    resp = client.post(
        "/api/v1/items",
        json={"description": "no name"},
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"http_requests_total" in resp.data
