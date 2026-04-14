# server.py
import asyncio
import time
import aiohttp
from dts.network import Network
from test.config import (
    SERVER_IDS, HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT,
    WORKER_HB_INTERVAL, WORKER_HB_TIMEOUT, ELECTION_TIMEOUT,API_BASE_URL
)


class Server:
    """
    One class, one file — every node runs this.
    Role is just a variable: "leader" or "worker".
    When a worker wins an election it flips self.role = "leader"
    and immediately starts doing leader work.
    """

    def __init__(self, server_id, log, on_status_change=None):
        self.id                  = server_id
        self.log                 = log
        self.on_status_change    = on_status_change

        # ── Network layer (pure TCP sockets, no RabbitMQ) ──
        self.net                 = Network(server_id, log)

        # ── Distributed state ──
        self.role                = "worker"   # "leader" or "worker"
        self.leader_id           = None
        self.term                = 0          # election term — rejects stale leaders

        # ── Election state ──
        self.election_in_progress = False
        self.received_ok          = False

        # ── Leader state ──
        self.task_counter         = 0
        # worker_id → last heartbeat timestamp
        self.worker_last_hb: dict[int, float] = {}
        # task_id → worker_id (so we can reassign on worker death)
        self.task_assignments: dict[int, int] = {}
        # task_id → task payload (so we can re-send on reassignment)
        self.task_payloads: dict[int, dict]   = {}

        # ── Worker state ──
        # tracks workers known to be alive (used by leader for round-robin)
        self._alive_workers: list[int]        = []

        # ── Background tasks ──
        self._heartbeat_task     = None
        self._worker_hb_task     = None
        self._worker_monitor_task = None
        self.alive               = True

    # ─────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────

    async def start(self):
        await self.net.connect()

        # Register message handlers (same API as old rabbitmq.py)
        await self.net.consume_broadcast(self.handle_broadcast)
        await self.net.consume_heartbeat(self.handle_heartbeat)
        await self.net.consume_worker_tasks(self.handle_worker_task)
        # task_submission handler is registered only when we become leader

        # Give other nodes a moment to come up, then decide on leadership
        await asyncio.sleep(2)
        await self.evaluate_leadership()

    async def stop(self):
        self.alive = False
        self._cancel(self._heartbeat_task)
        self._cancel(self._worker_hb_task)
        self._cancel(self._worker_monitor_task)
        await self.net.close()

    def _cancel(self, task):
        if task and not task.done():
            task.cancel()

    # ─────────────────────────────────────────────────────────
    # Leadership evaluation on startup / re-join
    # ─────────────────────────────────────────────────────────

    async def evaluate_leadership(self):
        if self.leader_id is None:
            self.log(f"[Server {self.id}] No known leader → starting election")
            await self.start_election()
        elif self.leader_id < self.id:
            self.log(f"[Server {self.id}] My ID {self.id} > leader {self.leader_id} → challenging")
            await self.start_election()
        else:
            self.log(f"[Server {self.id}] Leader {self.leader_id} has higher ID → joining as worker")
            self._start_worker_heartbeat()

    # ─────────────────────────────────────────────────────────
    # Broadcast message handler (ELECTION, OK, COORDINATOR, …)
    # ─────────────────────────────────────────────────────────

    async def handle_broadcast(self, msg):
        msg_type = msg.get("type")

        # ── ELECTION ──
        if msg_type == "ELECTION":
            sender = msg["from"]
            incoming_term = msg.get("term", 0)

            if sender < self.id:
                # I have a higher ID — suppress sender and run my own election
                self.log(f"[Server {self.id}] ELECTION from {sender} (lower ID) → sending OK")
                await self.net.broadcast_msg({
                    "type": "OK",
                    "to":   sender,
                    "from": self.id,
                    "term": self.term,
                })
                await self.start_election()

        # ── OK ──
        elif msg_type == "OK":
            if msg.get("to") == self.id:
                self.received_ok = True
                self.log(f"[Server {self.id}] Received OK from Server {msg['from']} → stepping back")

        # ── COORDINATOR — new leader announced ──
        elif msg_type == "COORDINATOR":
            incoming_term = msg.get("term", 0)
            new_leader    = msg["leader"]

            # Reject stale coordinator messages (split-brain protection)
            if incoming_term < self.term:
                self.log(f"[Server {self.id}] Ignoring stale COORDINATOR (term {incoming_term} < {self.term})")
                return

            self.term      = incoming_term
            self.election_in_progress = False

            if new_leader != self.leader_id:
                self.log(f"[Server {self.id}] New leader: Server {new_leader} (term {self.term})")

            # If I was leader and someone else won — step down
            if self.role == "leader" and new_leader != self.id:
                await self._step_down()

            self.leader_id = new_leader

            if self.on_status_change:
                self.on_status_change(self.id, "LEADER" if new_leader == self.id else "WORKER")

            # Cancel leader heartbeat if I'm now a worker
            if self.role != "leader":
                self._cancel(self._heartbeat_task)
                self._heartbeat_task = None
                self.last_heartbeat  = time.time()  # reset timeout clock
                self._start_worker_heartbeat()

        # ── LEADER_DEAD ──
        elif msg_type == "LEADER_DEAD":
            dead_leader = msg.get("dead_leader")
            if self.leader_id == dead_leader:
                self.log(f"[Server {self.id}] Leader {dead_leader} declared dead → election")
                self.leader_id        = None
                self.election_in_progress = False
                # Don't start election here — monitor_heartbeat will do it
                # (avoids double-election storms)

        # ── TASK_EXECUTED — worker finished a task, reports to leader ──
        elif msg_type == "TASK_EXECUTED":
            if self.role == "leader":
                task_id   = msg.get("task_id")
                worker_id = msg.get("worker")
                self.log(f"[Leader {self.id}] Task {task_id} done by Worker {worker_id}")

                # Clear assignment tracking
                self.task_assignments.pop(task_id, None)
                self.task_payloads.pop(task_id, None)

                # Mark worker as free and tell everyone the task is done
                await self.net.broadcast_msg({
                    "type":    "TASK_DONE",
                    "task_id": task_id,
                    "task":    msg["task"],
                    "worker":  worker_id,
                })

        # ── TASK_DONE — replication: all nodes log completion ──
        elif msg_type == "TASK_DONE":
            task_id   = msg.get("task_id")
            task_name = msg.get("task", "Unknown")
            worker_id = msg.get("worker")
            self.log(f"[Server {self.id}] ✓ Task {task_id} '{task_name}' completed by Server {worker_id} (replicated)")

        # ── WORKER_HB — worker sends heartbeat to leader ──
        elif msg_type == "WORKER_HB":
            if self.role == "leader":
                worker_id = msg.get("from")
                self.worker_last_hb[worker_id] = time.time()

    # ─────────────────────────────────────────────────────────
    # Heartbeat handlers
    # ─────────────────────────────────────────────────────────

    async def handle_heartbeat(self, msg):
        """Receive leader heartbeat — workers use this to stay alive."""
        leader = msg.get("leader")
        term   = msg.get("term", 0)

        # Reject heartbeats from stale leaders
        if term < self.term:
            return

        if leader == self.leader_id:
            self.last_heartbeat = time.time()
        elif self.leader_id is None:
            # First heartbeat we've seen — learn the leader
            self.leader_id      = leader
            self.term           = term
            self.last_heartbeat = time.time()
            self.log(f"[Server {self.id}] Learned leader {leader} from heartbeat (term {term})")
            if self.on_status_change:
                self.on_status_change(self.id, "WORKER")
            self._start_worker_heartbeat()

    async def monitor_heartbeat(self):
        """Worker monitors leader heartbeat — triggers election on timeout."""
        self.last_heartbeat = time.time()
        while self.alive:
            await asyncio.sleep(1)
            if (
                self.role == "worker"
                and self.leader_id is not None
                and self.leader_id != self.id
                and time.time() - self.last_heartbeat > HEARTBEAT_TIMEOUT
            ):
                dead_leader    = self.leader_id
                self.leader_id = None
                self.log(f"[Server {self.id}] Leader {dead_leader} timed out → new election")
                await self.net.broadcast_msg({
                    "type":        "LEADER_DEAD",
                    "dead_leader": dead_leader,
                    "caller":      self.id,
                })
                await self.start_election()

    # ─────────────────────────────────────────────────────────
    # Task handlers
    # ─────────────────────────────────────────────────────────

    async def handle_task_submission(self, msg):
        """Leader receives a task from a client and assigns it to a worker."""
        if self.role != "leader":
            return

        self.task_counter += 1
        task_id = self.task_counter

        worker_id = self._pick_worker()
        if worker_id is None:
            self.log(f"[Leader {self.id}] No workers available for task {task_id} — queued")
            # In a full implementation you'd queue it; for demo we log
            return

        payload = {
            "type":     "TASK",
            "task_id":  task_id,
            "task":     msg.get("task", "Unknown"),
            "category": msg.get("category", ""),
        }

        # Track assignment for potential reassignment on worker death
        self.task_assignments[task_id] = worker_id
        self.task_payloads[task_id]    = payload

        self.log(f"[Leader {self.id}] Assigning task {task_id} → Worker {worker_id}: {payload['task']}")

        # Send DIRECTLY to that specific worker via its TCP socket
        await self.net.send_to_worker(worker_id, payload)

    async def handle_worker_task(self, msg):
        """Worker receives a task assigned directly by the leader."""
        task_id   = msg.get("task_id")
        task_name = msg.get("task", "Unknown")
        self.log(f"[Worker {self.id}] Executing task {task_id}: {task_name}")

        # Simulate task execution
        await asyncio.sleep(2)

        if self.leader_id is not None:
            self.log(f"[Worker {self.id}] Task {task_id} done → reporting to leader")
            await self.net.broadcast_msg({
                "type":    "TASK_EXECUTED",
                "task_id": task_id,
                "task":    task_name,
                "worker":  self.id,
            })

    # ─────────────────────────────────────────────────────────
    # Election (Bully Algorithm)
    # ─────────────────────────────────────────────────────────

    async def start_election(self):
        if self.election_in_progress:
            return

        self.election_in_progress = True
        self.received_ok          = False

        self.log(f"[Server {self.id}] Starting election (term {self.term + 1})")

        # Broadcast ELECTION to all — nodes with higher ID will respond OK
        await self.net.broadcast_msg({
            "type": "ELECTION",
            "from": self.id,
            "term": self.term,
        })

        # Wait for any OK responses
        await asyncio.sleep(ELECTION_TIMEOUT)

        if not self.received_ok and self.election_in_progress:
            # Nobody higher responded — I am the winner
            await self.become_leader()

        self.election_in_progress = False

    async def become_leader(self):
        if self.role == "leader" and self.leader_id == self.id:
            return  # already leader, don't re-announce

        self.term     += 1
        self.role      = "leader"
        self.leader_id = self.id

        self.log(f"[Server {self.id}] ★ I AM LEADER (term {self.term})")

        if self.on_status_change:
            self.on_status_change(self.id, "LEADER")

        # Tell everyone
        await self.net.broadcast_msg({
            "type":   "COORDINATOR",
            "leader": self.id,
            "term":   self.term,
        })

        # Stop worker heartbeat — we're the leader now
        self._cancel(self._worker_hb_task)
        self._worker_hb_task = None

        # Start broadcasting leader heartbeats
        self._cancel(self._heartbeat_task)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Start monitoring worker heartbeats for fault detection
        self._cancel(self._worker_monitor_task)
        self._worker_monitor_task = asyncio.create_task(self._monitor_workers())

        # Initialize worker tracking — assume all other nodes are workers
        for wid in SERVER_IDS:
            if wid != self.id:
                self.worker_last_hb[wid] = time.time()

        # Start accepting task submissions from clients
        await self.net.consume_task_submission(self.handle_task_submission)

    async def _step_down(self):
        """Called when we were leader but a new leader has been elected."""
        self.log(f"[Server {self.id}] Stepping down from leader role")
        self.role = "worker"
        self._cancel(self._heartbeat_task)
        self._heartbeat_task = None
        self._cancel(self._worker_monitor_task)
        self._worker_monitor_task = None
        self.task_assignments.clear()
        self.task_payloads.clear()

    # ─────────────────────────────────────────────────────────
    # Worker selection (round-robin among known alive workers)
    # ─────────────────────────────────────────────────────────

    def _pick_worker(self) -> int | None:
        """
        Leader picks the next available worker using round-robin.
        Only picks workers that have sent a heartbeat recently.
        """
        now   = time.time()
        alive = [
            wid for wid in SERVER_IDS
            if wid != self.id
            and now - self.worker_last_hb.get(wid, 0) < WORKER_HB_TIMEOUT
        ]
        if not alive:
            return None

        # Simple round-robin via task_counter mod
        return alive[self.task_counter % len(alive)]

    # ─────────────────────────────────────────────────────────
    # Background loops
    # ─────────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """Leader sends heartbeat to all workers periodically."""
        while self.alive and self.role == "leader":
            await self.net.send_heartbeat({
                "type":   "HEARTBEAT",
                "leader": self.id,
                "term":   self.term,
            })
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    def _start_worker_heartbeat(self):
        """Start worker → leader heartbeat loop (if not already running)."""
        if self._worker_hb_task and not self._worker_hb_task.done():
            return
        self._worker_hb_task = asyncio.create_task(self._worker_heartbeat_loop())

    async def _worker_heartbeat_loop(self):
        """Worker sends its own heartbeat to the leader so leader knows it's alive."""
        while self.alive and self.role == "worker":
            if self.leader_id and self.leader_id != self.id:
                await self.net.broadcast_msg({
                    "type": "WORKER_HB",
                    "from": self.id,
                })
            await asyncio.sleep(WORKER_HB_INTERVAL)

    async def _monitor_workers(self):
        """
        Leader monitors worker heartbeats.
        If a worker goes silent → mark dead → reassign its tasks.
        """
        while self.alive and self.role == "leader":
            await asyncio.sleep(1)
            now = time.time()
            for wid in list(self.worker_last_hb.keys()):
                last = self.worker_last_hb.get(wid, 0)
                if now - last > WORKER_HB_TIMEOUT:
                    self.log(f"[Leader {self.id}] Worker {wid} timed out → reassigning tasks")
                    self.worker_last_hb.pop(wid, None)
                    await self._reassign_tasks_from(wid)

    async def _reassign_tasks_from(self, dead_worker_id: int):
        """Reassign all tasks that were assigned to a dead worker."""
        to_reassign = [
            tid for tid, wid in self.task_assignments.items()
            if wid == dead_worker_id
        ]
        for task_id in to_reassign:
            payload   = self.task_payloads.get(task_id)
            if payload is None:
                continue
            new_worker = self._pick_worker()
            if new_worker is None:
                self.log(f"[Leader {self.id}] No workers to reassign task {task_id}")
                continue
            self.task_assignments[task_id] = new_worker
            self.log(f"[Leader {self.id}] Reassigning task {task_id} → Worker {new_worker}")
            await self.net.send_to_worker(new_worker, payload)
            
            


async def execute_task(self, category: str, task: str, msg: dict) -> str:
    """Routes to the right FastAPI endpoint based on task category."""

    if category == "AI/ML":
        return await self.call_api("/ai/sentiment", msg)

    elif category == "File Processing":
        return await self.call_api("/file/resize", msg)

    elif category == "Notification":
        return await self.call_api("/notify/email", msg)

    elif category == "Data Processing":
        return await self.call_api("/data/scrape", msg)

    elif category == "Dev/DevOps":
        return await self.call_api("/dev/test", msg)
    else:
        return f"Unknown category: {category}"


async def call_api(self, endpoint: str, payload: dict) -> str:
    """
    Makes a POST request to the FastAPI server.
    Returns a string summary of the result.
    """
    url = API_BASE_URL + endpoint

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:

                if resp.status == 200:
                    data = await resp.json()
                    self.log(f"[Worker {self.id}] API response: {data}")
                    return str(data)
                else:
                    return f"API error: HTTP {resp.status}"

    except asyncio.TimeoutError:
        return f"API timeout on {endpoint}"

    except aiohttp.ClientConnectorError:
        return f"API unreachable — is api.py running?"

    except Exception as e:
        return f"API error: {e}"