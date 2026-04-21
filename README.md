# CPSC559Project3

Distributed task system demo with RabbitMQ, a FastAPI dashboard, and a Vite/React frontend.

Repository layout
- `backend/` — Python backend service (server, API endpoints, RabbitMQ integration)
- `frontend/` — Vite + React UI
- `docker-compose.yaml` — main compose file for running the full stack on one machine
- `docker-compose.worker.yaml` — compose file for running one worker on another PC
- `refresh_db.ps1` — helper script for resetting the database

Quick start (Docker)

1. From the repo root run:

```bash
docker compose up --build
```

2. Open the frontend UI in your browser. The backend API, RabbitMQ, dashboard, and worker services will start automatically.

Multi-PC deployment with Docker

`docker compose` is single-host. To run this project across different PCs, use one shared RabbitMQ broker and let every worker container connect to that broker over the network.

Recommended layout
- PC 1: `rabbitmq`, `dashboard`, `frontend`, and optionally one server container
- PC 2..N: one `server` container per machine

Control-plane PC

1. Pick the PC that will host RabbitMQ and note its LAN IP or hostname, for example `192.168.1.50`.
2. Create a `.env` file from `.env.example` and set at least `RABBITMQ_USER` and `RABBITMQ_PASS`.
3. Start the shared services:

```bash
docker compose up -d --build rabbitmq dashboard frontend server_5
```

4. Keep `RABBITMQ_HOST=rabbitmq` on this machine when those services run in the same compose project.

Worker PCs

1. Copy this repository to each worker PC.
2. Create a `.env` file on each worker PC with values like:

```bash
SERVER_ID=1
RABBITMQ_HOST=192.168.1.50
RABBITMQ_PORT=5672
RABBITMQ_USER=app
RABBITMQ_PASS=change-me
```

3. Start one worker on that PC:

```bash
docker compose -f docker-compose.worker.yaml up -d --build
```

4. Repeat on the other machines with different `SERVER_ID` values such as `2`, `3`, `4`, and `5`.

Important notes for multi-PC mode
- Each worker must use a unique `SERVER_ID`. The current UI and backend are set up for IDs `1` through `5`.
- Do not use RabbitMQ `guest/guest` for remote machines. Use a real user such as `app`.
- Open firewall access for port `5672` on the RabbitMQ machine.
- Open port `8000` on the dashboard machine if the frontend or other clients must reach the dashboard directly.
- If the frontend runs on a different PC than the dashboard, set `DASHBOARD_HOST` to the dashboard machine IP or hostname before starting the frontend container.
- Port `15672` is only for the RabbitMQ management UI.
- If you want one command to manage all PCs as a single cluster, move to Docker Swarm or Kubernetes.

Run locally (development)

Backend

1. Open a terminal and go to the backend folder:

```bash
cd backend
```

2. Create and activate a virtual environment, install dependencies, then run the server. The project does not include a pinned `requirements.txt`; install the packages needed for your environment (for example `fastapi`, `uvicorn`, and `aio-pika`), then:

```bash
python server_runner.py
```

Frontend

1. Open a terminal and go to the frontend folder:

```bash
cd frontend
npm install
npm run dev
```

2. Visit the address printed by Vite, commonly `http://localhost:5173`.

Notes
- Configuration for the backend lives in `backend/config.py`.
- Backend entrypoints: `backend/server.py` and `backend/server_runner.py`.
- Task-related API: `backend/task_api.py`.

Troubleshooting
- If you use RabbitMQ locally, confirm the instance is reachable or update connection settings in `backend/rabbitmq.py`.
- For multi-PC deployment, confirm every worker can reach `RABBITMQ_HOST:RABBITMQ_PORT` across the network.
- Use `refresh_db.ps1` to reset the DB when developing on Windows.

Contributing
- Open an issue or submit a PR with improvements or fixes.

License
- Add your preferred license here.

Contact
- For questions about this workspace, ask the repo owner.
