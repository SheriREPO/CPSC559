# main.py
# Entry point — runs three things together:
#   1. All 5 server nodes (TCP sockets, elections, tasks)
#   2. Task API on port 8000  (FastAPI — does actual work)
#   3. Dashboard API on port 8001 (FastAPI — React polls this)
#
# Run with:   python main.py
# Then open the React dashboard in your browser.

import asyncio
import uvicorn
import threading

# ── Import both FastAPI apps ──
from api import app as task_app           # port 8000 — does real work (sentiment, file, etc.)
import dashboard_api                       # port 8001 — React polling bridge
from dashboard_api import app as dash_app


def run_uvicorn(app, port: int):
    """Run a uvicorn server in a background thread."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",   # keep console clean
    )
    server = uvicorn.Server(config)
    server.run()


async def main():
    # ── Grab the running event loop so dashboard_api can schedule coroutines ──
    loop = asyncio.get_running_loop()
    dashboard_api.set_loop(loop)

    # ── Start Task API (port 8000) in background thread ──
    t_task = threading.Thread(target=run_uvicorn, args=(task_app, 8000), daemon=True)
    t_task.start()
    print("[Main] Task API running on http://127.0.0.1:8000")

    # ── Start Dashboard API (port 8001) in background thread ──
    t_dash = threading.Thread(target=run_uvicorn, args=(dash_app, 8001), daemon=True)
    t_dash.start()
    print("[Main] Dashboard API running on http://127.0.0.1:8001")

    print("[Main] Open your React dashboard → connect to http://127.0.0.1:8001")
    print("[Main] Nodes will start when you click Start in the dashboard")
    print("[Main] Press Ctrl+C to stop everything\n")

    # ── Keep the async loop alive ──
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
