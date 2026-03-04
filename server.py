# server.py
import asyncio
import time
from rabbitmq import RabbitMQ
from config import RABBIT_URL, HEARTBEAT_TIMEOUT, ELECTION_TIMEOUT


class Server:
    def __init__(self, server_id, log, on_status_change=None):
        self.id = server_id
        self.log = log
        self.on_status_change = on_status_change

        self.rabbit = RabbitMQ(RABBIT_URL, log, server_id)

        self.leader_id = None
        self.last_heartbeat = time.time()
        self.alive = True

        self.election_in_progress = False
        self.received_ok = False

        self.heartbeat_task = None
        self.task_submission_consumer = None

        self.task_counter = 0

         # list of dicts: {task_id, task, worker}
        self.completed_tasks = [] 

        # prevent repeatedly spamming state requests
        self._state_requested = False

    async def stop(self):
        self.alive = False

        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.task_submission_consumer:
            try:
                await self.task_submission_consumer.cancel()
            except Exception:
                pass
            self.task_submission_consumer = None

        await self.rabbit.unbind_task_submission()
        await self.rabbit.close()

    async def start(self):
        await self.rabbit.connect()

        await self.rabbit.consume_broadcast(self.handle_broadcast)
        await self.rabbit.consume_heartbeat(self.handle_heartbeat)
        await self.rabbit.consume_worker_tasks(self.handle_worker_task)

        asyncio.create_task(self.monitor_heartbeat())

        # Give time for subscriptions to attach, then ask for state
        asyncio.create_task(self.request_state_soon())

        await asyncio.sleep(2)
        await self.evaluate_leadership()

    async def request_state_soon(self):
        await asyncio.sleep(0.5)
        if not self._state_requested:
            self._state_requested = True
            await self.rabbit.broadcast_msg({"type": "STATE_REQUEST", "from": self.id})

    async def evaluate_leadership(self):
        if self.leader_id is None:
            self.log(f"[Server {self.id}] No known leader → starting election")
            await self.start_election()
        elif self.leader_id < self.id:
            self.log(f"[Server {self.id}] ID {self.id} > leader {self.leader_id} → starting election (preempt)")
            await self.start_election()
        else:
            self.log(f"[Server {self.id}] Leader {self.leader_id} has higher ID → joining as worker")

    async def handle_broadcast(self, msg):
        msg_type = msg.get("type")

        # ---------------------------
        # State sync for joiners
        # ---------------------------
        if msg_type == "STATE_REQUEST":
            requester = msg.get("from")
            # Only leader replies with authoritative state
            if self.id == self.leader_id and requester is not None:
                await self.rabbit.broadcast_msg({
                    "type": "STATE_RESPONSE",
                    "to": requester,
                    "from": self.id,
                    "leader": self.id,
                    "completed_tasks": self.completed_tasks,
                })

        elif msg_type == "STATE_RESPONSE":
            if msg.get("to") == self.id:
                incoming = msg.get("completed_tasks", [])
                # Replace local copy with leader-provided snapshot
                self.completed_tasks = list(incoming)
                self.log(f"[Server {self.id}] Loaded state from Leader {msg.get('from')}: {len(self.completed_tasks)} completed tasks")

        # ---------------------------
        # Bully election messages
        # ---------------------------
        elif msg_type == "ELECTION":
            if msg["from"] < self.id:
                self.log(f"[Server {self.id}] Election from {msg['from']} (I have higher ID) → OK")
                await self.rabbit.broadcast_msg({"type": "OK", "to": msg["from"], "from": self.id})
                await self.start_election()

        elif msg_type == "OK":
            if msg.get("to") == self.id:
                self.received_ok = True

        elif msg_type == "COORDINATOR":
            new_leader = msg["leader"]

            if new_leader != self.leader_id:
                self.log(f"[Server {self.id}] New Leader: {new_leader}")

            if self.on_status_change:
                self.on_status_change(self.id, "LEADER" if new_leader == self.id else "WORKER")

            # If I was leader and someone else became leader, step down
            if self.leader_id == self.id and new_leader != self.id:
                if self.task_submission_consumer:
                    try:
                        await self.task_submission_consumer.cancel()
                    except Exception:
                        pass
                    self.task_submission_consumer = None

                await self.rabbit.unbind_task_submission()
                self.log(f"[Server {self.id}] Stepped down - stopped consuming task_submission")

            self.leader_id = new_leader
            self.election_in_progress = False
            self.last_heartbeat = time.time()

            if self.leader_id != self.id and self.heartbeat_task:
                self.heartbeat_task.cancel()
                self.heartbeat_task = None

            # When leader changes, request state once (helps late joiners)
            if self.id != self.leader_id:
                asyncio.create_task(self.request_state_soon())

        elif msg_type == "LEADER_DEAD":
            dead = msg.get("dead_leader")
            self.log(f"[Server {self.id}] Leader {dead} declared dead → new election")
            if self.leader_id == dead:
                self.leader_id = None
                self.election_in_progress = False

        # ---------------------------
        # Task pipeline messages
        # ---------------------------
        elif msg_type == "TASK_EXECUTED":
            # Only leader commits completion
            if self.id == self.leader_id:
                task_id = msg.get("task_id")
                worker_id = msg.get("worker")
                task_name = msg.get("task")

                self.log(f"[Leader {self.id}] Response from Server {worker_id}: task {task_id} executed → broadcasting completed")

                await self.rabbit.broadcast_msg({
                    "type": "TASK_DONE",
                    "task_id": task_id,
                    "task": task_name,
                    "worker": worker_id,
                    "index": 2,
                })

        elif msg_type == "TASK_DONE":
            task_id = msg.get("task_id")
            task_name = msg.get("task", "Unknown")
            worker_id = msg.get("worker")
            index = msg.get("index", 2)

            
            self.completed_tasks.append({
                "task_id": task_id,
                "task": task_name,
                "worker": worker_id,
            })

            self.log(f"[Server {self.id}] Task {task_id} index {index}: {task_name} completed by Server {worker_id} (replicated)")

    async def handle_heartbeat(self, msg):
        leader = msg.get("leader")
        if leader == self.leader_id:
            self.last_heartbeat = time.time()
        elif self.leader_id is None:
            self.leader_id = leader
            self.last_heartbeat = time.time()
            self.log(f"[Server {self.id}] Learned leader {leader} from heartbeat")
            if self.on_status_change:
                self.on_status_change(self.id, "WORKER")
            asyncio.create_task(self.request_state_soon())

    async def handle_task_submission(self, msg):
        if self.id != self.leader_id:
            return

        self.task_counter += 1
        task_id = task_id = f"leader_{self.id}_task_{self.task_counter}"

        self.log(f"[Leader {self.id}] Received task from client → index 1: assigning task {task_id} to worker")

        await self.rabbit.publish_to_workers({
            "type": "TASK",
            "task_id": task_id,
            "task": msg["task"],
            "category": msg.get("category", ""),
            "index": 1,
        })

    async def handle_worker_task(self, msg):
        task_id = msg.get("task_id")
        task = msg.get("task", "Unknown")

        self.log(f"[Server {self.id}] Executing task {task_id}: {task}")
        await asyncio.sleep(2)

        if self.leader_id is not None:
            await self.rabbit.broadcast_msg({
                "type": "TASK_EXECUTED",
                "task_id": task_id,
                "task": task,
                "worker": self.id,
            })
            self.log(f"[Server {self.id}] Task {task_id} executed → response to leader")

    async def monitor_heartbeat(self):
        while self.alive:
            if (
                self.leader_id
                and self.leader_id != self.id
                and time.time() - self.last_heartbeat > HEARTBEAT_TIMEOUT
            ):
                dead_leader = self.leader_id
                self.log(f"[Server {self.id}] Leader {dead_leader} heartbeat timeout → new election")

                await self.rabbit.broadcast_msg({
                    "type": "LEADER_DEAD",
                    "dead_leader": dead_leader,
                    "caller": self.id
                })

                self.leader_id = None
                await self.start_election()

            await asyncio.sleep(1)

    async def start_election(self):
        if self.election_in_progress:
            return

        self.election_in_progress = True
        self.received_ok = False

        self.log(f"[Server {self.id}] Starting election")
        await self.rabbit.broadcast_msg({"type": "ELECTION", "from": self.id})

        await asyncio.sleep(ELECTION_TIMEOUT)

        if not self.received_ok:
            await self.become_leader()

        self.election_in_progress = False

    async def become_leader(self):
        if self.leader_id == self.id:
            return

        self.leader_id = self.id

        if self.on_status_change:
            self.on_status_change(self.id, "LEADER")

        self.log(f"[Server {self.id}] I AM LEADER")

        await self.rabbit.broadcast_msg({"type": "COORDINATOR", "leader": self.id})

        
        await self.rabbit.bind_task_submission()

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

        try:
            self.task_submission_consumer = await self.rabbit.consume_task_submission(self.handle_task_submission)
        except Exception as e:
            self.log(f"[Server {self.id}] Failed task consumer: {e}")

    async def heartbeat_loop(self):
        while self.alive and self.leader_id == self.id:
            await self.rabbit.send_heartbeat({"leader": self.id})
            await asyncio.sleep(1)