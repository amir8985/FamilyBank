# Cloud Run image for the FamilyBank backend. Render builds from a
# buildpack + render.yaml; Cloud Run needs an explicit container.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Cloud Run injects $PORT (8080 by default). The forwarded-IP flags match
# render.yaml's startCommand — Cloud Run also sits behind a proxy, and the
# per-IP rate limit on /internal/client-metrics (app/core/rate_limit.py)
# needs the real client address, not the proxy's.
#
# Migrations do NOT run here — a fresh container starts on every autoscale
# event, and they'd race. `alembic upgrade head` runs once per deploy as a
# Cloud Build step instead (see cloudbuild.yaml).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
