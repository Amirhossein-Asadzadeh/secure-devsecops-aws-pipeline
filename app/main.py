import os
import logging
import time

from flask import Flask, jsonify, request
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

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
# Application routes
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "version": os.getenv("APP_VERSION", "1.0.0")})


@app.route("/api/v1/items", methods=["GET"])
def list_items():
    items = [
        {"id": 1, "name": "Secure Pipeline", "status": "active"},
        {"id": 2, "name": "Cloud Deploy", "status": "active"},
    ]
    logger.info("Listed %d items", len(items))
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/v1/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True)
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400
    item = {"id": 3, "name": data["name"], "status": "created"}
    logger.info("Created item: %s", item["name"])
    return jsonify(item), 201


@app.route("/metrics", methods=["GET"])
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
