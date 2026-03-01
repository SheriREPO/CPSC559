# ── Base image ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Dependencies ──────────────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ── Final image ───────────────────────────────────────────────────────────────
FROM deps AS final

# Create a non-root user for security
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

# Copy application source
COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

# Healthcheck — ensures the container is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import aio_pika; print('ok')" || exit 1

CMD ["python", "main.py"]