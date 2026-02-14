# ---------- build stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build
COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- runtime stage ----------
FROM python:3.12-slim

# Security: run as non-root
RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ .

# Security: drop all capabilities, read-only filesystem where possible
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]

ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--access-logfile", "-", "main:app"]
