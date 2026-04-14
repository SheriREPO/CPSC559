# CPSC559Project3

Short description

This repository contains a simple project with a backend and frontend used for the CPSC 559 assignment. The backend provides task APIs and a WebSocket/logging system; the frontend is a Vite/React app that interacts with the backend.

Repository layout
- `backend/` — Python backend service (server, API endpoints, RabbitMQ integration)
- `frontend/` — Vite + React UI
- `docker-compose.yaml` — compose file to run services together
- `refresh_db.ps1` — helper script for resetting the database

Quick start (Docker)

1. From the repo root run:

```
docker-compose up --build
```

2. Open the frontend UI in your browser (see compose output for the URL). The backend API and worker services will start automatically.

Run locally (development)

Backend

1. Open a terminal and go to the backend folder:

```
cd backend
```

2. Create and activate a virtual environment, install dependencies, then run the server. The project does not include a pinned `requirements.txt`; install the packages needed for your environment (e.g., `fastapi`, `uvicorn`, `aio-pika` or other RabbitMQ client you prefer), then:

```
python server_runner.py
```

Frontend

1. Open a terminal and go to the frontend folder:

```
cd frontend
npm install
npm run dev
```

2. Visit the address printed by Vite (commonly `http://localhost:5173`).

Notes
- Configuration for the backend lives in `backend/config.py`.
- Backend entrypoints: see `backend/server.py` and `backend/server_runner.py`.
- Task-related API: see `backend/task_api.py`.

Troubleshooting
- If you use RabbitMQ locally, confirm the instance is reachable or update connection settings in `backend/rabbitmq.py`.
- Use `refresh_db.ps1` to reset the DB when developing on Windows.

Contributing
- Open an issue or submit a PR with improvements or fixes.

License
- Add your preferred license here.

Contact
- For questions about this workspace, ask the repo owner.
