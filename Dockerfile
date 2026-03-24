FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# --- Python dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip wheel --wheel-dir /wheels -r requirements.txt

# --- Frontend dependencies (Node.js + Vite) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ web/
COPY vite.config.js .
RUN npm run build

FROM python:3.13-slim

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp \
    MPLCONFIGDIR=/tmp \
    NUMBA_CACHE_DIR=/tmp

WORKDIR /app

# --- Python dependencies ---
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# --- Application code ---
COPY . .

# --- Overlay Vite-built frontend assets ---
COPY --from=builder /build/dist/static/index.html web/index.html
COPY --from=builder /build/dist/static/assets/ web/assets/
RUN find /app/web/js -type f -name "*.js" -delete 2>/dev/null || true

RUN find /app -type d -name "__pycache__" -prune -exec rm -rf {} + \
    && find /app -type f -name "*.py[co]" -delete \
    && addgroup --system app \
    && adduser --system --ingroup app --home /app appuser \
    && mkdir -p /app/data /app/config/keys /tmp/pycache \
    && chown -R appuser:app /app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)" || exit 1

USER appuser

CMD ["gunicorn", "-c", "gunicorn.conf.py", "api.main:app"]
