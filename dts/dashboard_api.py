# dashboard_api.py
# HTTP bridge between the React frontend and the running Server nodes.
# Runs on port 8001 alongside the task API (port 8000).
# React polls /state every second and POSTs to /submit, /node/{id}/start, /node/{id}/stop

import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from server import Server, _registry, _task_log
from config import SERVER_IDS

# ── Shared asyncio loop injected from main.py ──
_loop: asyncio.AbstractEventLoop = None

def set_loop(loop: asyncio.AbstractEventLoop):
    global _loop
    _loop = loop

# ── App ──────────────────────────────────────────────────
app = FastAPI(title="DTS Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────

@app.get("/state")
def get_state():
    """
    Returns the real live state of every node.
    React polls this every second.
    """
    leader_id = next(
        (s.id for s in _registry.values() if s.role == "leader"),
        None
    )

    nodes = {}
    for sid in SERVER_IDS:
        if sid in _registry:
            nodes[sid] = _registry[sid].snapshot()
        else:
            # node not started yet
            nodes[sid] = {
                "id":              sid,
                "role":            "off",
                "leader_id":       None,
                "term":            0,
                "alive":           False,
                "tasks_assigned":  0,
                "tasks_done":      0,
                "election_active": False,
                "workers_known":   [],
            }

    return {
        "nodes":     nodes,
        "leader_id": leader_id,
        "tasks":     list(reversed(_task_log[-50:])),  # latest 50 tasks, newest first
    }


@app.post("/submit")
async def submit_task(body: dict):
    """
    Client (React) submits a task.
    Forwards it directly to the current leader's handler.
    """
    leader = next((s for s in _registry.values() if s.role == "leader"), None)
    if not leader:
        raise HTTPException(status_code=503, detail="No leader elected yet")

    # Run the async handler in the server's event loop
    asyncio.run_coroutine_threadsafe(
        leader.handle_task_submission(body),
        _loop
    ).result(timeout=5)

    return {"ok": True, "leader_id": leader.id, "task": body.get("task")}


@app.post("/node/{node_id}/start")
async def start_node(node_id: int):
    """Start a server node — called when user clicks Start in the dashboard."""
    if node_id not in SERVER_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown node {node_id}")
    if node_id in _registry:
        return {"ok": False, "detail": f"Server {node_id} already running"}

    def _log(msg):
        print(msg)

    server = Server(node_id, _log)

    async def _start():
        await server.start()
        asyncio.create_task(server.monitor_heartbeat())

    asyncio.run_coroutine_threadsafe(_start(), _loop)
    return {"ok": True, "node_id": node_id}


@app.post("/node/{node_id}/stop")
async def stop_node(node_id: int):
    """Stop a server node — called when user clicks Stop in the dashboard."""
    if node_id not in _registry:
        return {"ok": False, "detail": f"Server {node_id} not running"}

    server = _registry[node_id]
    asyncio.run_coroutine_threadsafe(server.stop(), _loop).result(timeout=5)
    return {"ok": True, "node_id": node_id}


@app.get("/health")
def health():
    return {"status": "ok", "running_nodes": list(_registry.keys())}
