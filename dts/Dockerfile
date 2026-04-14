# Dockerfile
# Builds a single image that runs all DTS services:
#   - main.py  (server nodes + dashboard API on :8001)
#   - api.py   (task API on :8000)
#
# Build:   docker build -t dts .
# Run:     docker run -p 8000:8000 -p 8001:8001 dts

FROM python:3.11-slim

# ── System deps ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ──────────────────────────
# Copy requirements first so Docker caches this layer
# (only re-runs pip install when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy project files ───────────────────────────────────
COPY config.py        .
COPY network.py       .
COPY server.py        .
COPY api.py           .
COPY dashboard_api.py .
COPY main.py          .

# ── Expose ports ─────────────────────────────────────────
# 8000 — Task API      (FastAPI, does real work)
# 8001 — Dashboard API (React polls this)
# 9001-9005 — TCP sockets between server nodes
EXPOSE 8000 8001 9001 9002 9003 9004 9005

# ── Start everything ─────────────────────────────────────
CMD ["python", "main.py"]