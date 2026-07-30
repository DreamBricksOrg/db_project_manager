# ── OOH Project Manager ──────────────────────────────────
# Multi-stage build for a lean production image

# ── Stage 1: Builder ─────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    pkg-config \
    libcairo2-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="DreamBricks"
LABEL description="OOH Project Manager – Flask + MongoDB"

# Runtime dependency for pycairo
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
  && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create directories that the app expects
RUN mkdir -p data app/static/uploads secrets \
    && chown -R app:app /app

USER app

# Fail fast and unbuffered, so logs reach the container runtime immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=5).status == 200 else 1)"

# Gunicorn for production. Access logs go to stdout so `docker logs` shows them.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "run:app"]
