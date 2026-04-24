import asyncio
import json
import time
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode
from contextlib import asynccontextmanager

RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@localhost/")
OFFLINE_TIMEOUT = 6  # needs to be longer than the heartbeat interval (1s) with enough slack for network delay

server_states: dict[int, dict] = {
    i: {"status": "Offline", "last_seen": 0} for i in range(1, 6)
}
logs: list[str] = []
task_history: list[dict] = []
connected_clients: list[WebSocket] = []
pending_tasks: dict = {}

rabbit_conn = None
rabbit_channel = None


def add_log(msg: str):
    ts = time.strftime("%H:%M:%S")
    logs.append(f"[{ts}] {msg}")
    if len(logs) > 200:
        logs.pop(0)


async def broadcast_state():
    if not connected_clients:
        return
    payload = json.dumps({
        "type": "state",
        "servers": server_states,
        "logs": logs[-50:],
        "tasks": task_history[-30:],
    })
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)


async def handle_heartbeat(msg: aio_pika.IncomingMessage):
    async with msg.process():
        body = json.loads(msg.body.decode())
        leader_id = body.get("leader")
        workers = body.get("workers", [])
        if leader_id is not None:
            now = time.time()
            current_leader = next(
                (
                    sid for sid, state in server_states.items()
                    if state["status"] == "Leader"
                    and now - state["last_seen"] <= OFFLINE_TIMEOUT
                ),
                None,
            )
            # bully algorithm: a lower-ID server can't override a higher-ID leader that's still alive
            if (
                current_leader is not None
                and current_leader != leader_id
                and current_leader > leader_id
            ):
                return

            for sid, state in server_states.items():
                if sid != leader_id and state["status"] == "Leader":
                    server_states[sid]["status"] = "Worker"

            server_states[leader_id] = {"status": "Leader", "last_seen": now}
            for wid in workers:
                if wid in server_states:
                    server_states[wid]["last_seen"] = now
                    if server_states[wid]["status"] == "Offline":
                        server_states[wid]["status"] = "Worker"
                        add_log(f"📶 Server {wid} is back online")
                    elif server_states[wid]["status"] != "Leader":
                        server_states[wid]["status"] = "Worker"
        await broadcast_state()


async def handle_broadcast(msg: aio_pika.IncomingMessage):
    async with msg.process():
        body = json.loads(msg.body.decode())
        msg_type = body.get("type")

        if msg_type == "COORDINATOR":
            new_leader = body["leader"]
            add_log(f"🏆 Server {new_leader} is the new LEADER")

            now = time.time()
            for sid in server_states:
                if sid == new_leader:
                    server_states[sid] = {"status": "Leader", "last_seen": now}
                elif server_states[sid]["status"] == "Leader":
                    server_states[sid]["status"] = "Worker"

        elif msg_type == "ELECTION":
            sender = body.get("from")
            add_log(f"🗳️  Server {sender} started an ELECTION")

        elif msg_type == "OK":
            sender = body.get("from")
            add_log(f"↩️  Server {sender} sent OK to Server {body.get('to')}")

        elif msg_type == "LEADER_DEAD":
            dead_id = body.get("dead_leader")
            add_log(f"💀 Server {dead_id} (leader) declared dead — new election starting")
            if dead_id in server_states:
                server_states[dead_id]["status"] = "Offline"

        elif msg_type == "TASK_EXECUTED":
            worker = body.get("worker")

        elif msg_type == "TASK_DONE":
            task_id = body.get("task_id")
            task_name = body.get("task", "Unknown")
            worker = body.get("worker")
            result = body.get("result", {})
            success = result.get("success", True)
            status = "✅" if success else "❌"
            add_log(f"{status} Task #{task_id} '{task_name}' done by Server {worker}")

            matched_token = body.get("token")

            task_history.append({
                "id": task_id,
                "task": task_name,
                "worker": worker,
                "time": time.strftime("%H:%M:%S"),
                "result": result,
                "success": success,
                "token": matched_token,
            })
            if len(task_history) > 100:
                task_history.pop(0)

        await broadcast_state()


async def watch_offline():
    while True:
        await asyncio.sleep(1)
        now = time.time()
        changed = False
        for sid, state in server_states.items():
            if state["status"] != "Offline" and state["last_seen"] > 0:  # skip servers that never checked in
                if now - state["last_seen"] > OFFLINE_TIMEOUT:
                    server_states[sid]["status"] = "Offline"
                    add_log(f"📴 Server {sid} went offline")
                    changed = True
        if changed:
            await broadcast_state()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rabbit_conn, rabbit_channel

    for attempt in range(10):
        try:
            rabbit_conn = await aio_pika.connect_robust(RABBIT_URL)
            break
        except Exception:
            add_log(f"Waiting for RabbitMQ... (attempt {attempt + 1})")
            await asyncio.sleep(3)
    else:
        add_log("ERROR: Could not connect to RabbitMQ")
        yield
        return

    rabbit_channel = await rabbit_conn.channel()

    direct_ex = await rabbit_channel.declare_exchange("direct_exchange", ExchangeType.DIRECT, durable=True)
    broadcast_ex = await rabbit_channel.declare_exchange("broadcast_exchange", ExchangeType.FANOUT, durable=True)
    heartbeat_ex = await rabbit_channel.declare_exchange("heartbeat_exchange", ExchangeType.FANOUT, durable=True)

    task_queue = await rabbit_channel.declare_queue("task_submission", durable=True)
    await task_queue.bind(direct_ex, routing_key="task_submission")

    bcast_queue = await rabbit_channel.declare_queue(exclusive=True)
    await bcast_queue.bind(broadcast_ex)
    hb_queue = await rabbit_channel.declare_queue(exclusive=True)
    await hb_queue.bind(heartbeat_ex)

    await bcast_queue.consume(handle_broadcast)
    await hb_queue.consume(handle_heartbeat)

    asyncio.create_task(watch_offline())
    add_log("🚀 Dashboard connected to RabbitMQ — watching cluster")

    yield

    if rabbit_conn and not rabbit_conn.is_closed:
        await rabbit_conn.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskPayload(BaseModel):
    task: str
    category: str = ""
    details: dict = {}


@app.post("/submit-task")
async def submit_task(payload: TaskPayload):
    if rabbit_channel is None:
        return {"error": "Not connected to RabbitMQ"}

    import uuid as _uuid
    token = str(_uuid.uuid4())
    add_log(f"📨 Task submitted: '{payload.task}'")
    await broadcast_state()
    direct_ex = await rabbit_channel.declare_exchange("direct_exchange", ExchangeType.DIRECT, durable=True)
    msg = Message(
        json.dumps({
            "type": "TASK", "task": payload.task,
            "category": payload.category, "details": payload.details,
            "token": token,
        }).encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
    )
    await direct_ex.publish(msg, routing_key="task_submission")
    return {"ok": True, "token": token}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)

    await websocket.send_text(json.dumps({
        "type": "state",
        "servers": server_states,
        "logs": logs[-50:],
        "tasks": task_history[-30:],
    }))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


@app.get("/state")
async def get_state():
    return {
        "servers": server_states,
        "logs": logs[-50:],
        "tasks": task_history[-30:],
    }
