FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    aio_pika \
    fastapi \
    uvicorn[standard] \
    Pillow \
    groq

COPY config.py .
COPY rabbitmq.py .
COPY server.py .
COPY server_runner.py .
COPY dashboard.py .
COPY task_api.py .
COPY storage.py .

# Create data directory for SQLite DB and WAL
RUN mkdir -p /app/data

CMD ["python", "server_runner.py"]