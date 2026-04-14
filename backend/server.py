import json
# server.py
import asyncio
import time
from rabbitmq import RabbitMQ
from config import RABBIT_URL, HEARTBEAT_TIMEOUT, ELECTION_TIMEOUT, SERVER_IDS
from task_api import execute_task
from storage import (
    init_db, replay_wal, save_task, mark_assigned, mark_completed,
    mark_failed, replicate_task, get_incomplete_tasks, task_exists
)

PING_INTERVAL = 2   # leader pings each worker every 2 seconds
PING_TIMEOUT  = 5   # if no PONG within 5 seconds, worker is considered dead


class Server:

    def __init__(self, server_id, log, on_status_change=None):
        self.id = server_id
        self.log = log
        self.on_status_change = on_status_change
        self.rabbit = RabbitMQ(RABBIT_URL, log)
        self.leader_id = None
        self.last_heartbeat = time.time()
        self.alive = True
        self.election_in_progress = False
        self.received_ok = False
        self.heartbeat_task = None
        self.task_submission_consumer = None
        self.task_counter = 0
        # worker_id -> timestamp of last PONG received (leader only)
        self.worker_last_pong: dict = {}
        # Round-robin index for task allocation
        self.round_robin_index: int = 0
        # In-flight tasks: task_id -> {token, task, category, details, worker, assigned_at}
        self.in_flight: dict = {}

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
        await self.rabbit.close()

    async def start(self):
        # Init DB and replay WAL before anything else
        init_db()
        replay_wal()
        await self.rabbit.connect(server_id=self.id)
        await self.rabbit.consume_broadcast(self.handle_broadcast)
        await self.rabbit.consume_heartbeat(self.handle_heartbeat)
        await self.rabbit.consume_direct(self.handle_direct)
        asyncio.create_task(self.monitor_heartbeat())
        await asyncio.sleep(2)
        await self.evaluate_leadership()

    async def evaluate_leadership(self):
        if self.leader_id is None:
            self.log(f"[Server {self.id}] No known leader -> starting election")
            await self.start_election()
        elif self.leader_id < self.id:
            # Wait before preempting — give any ongoing election time to finish
            # so two servers don't declare themselves leader simultaneously
            self.log(f"[Server {self.id}] ID {self.id} > leader {self.leader_id} -> waiting before election")
            await asyncio.sleep(self.id * 0.5)
            # Re-check — another server may have already won while we waited
            if self.leader_id is None or self.leader_id < self.id:
                self.log(f"[Server {self.id}] Starting preemptive election")
                await self.start_election()
            else:
                self.log(f"[Server {self.id}] Leader {self.leader_id} already elected -> joining as worker")
        else:
            self.log(f"[Server {self.id}] Leader {self.leader_id} has higher ID -> joining as worker")

    async def handle_direct(self, msg):
        msg_type = msg.get("type")

        if msg_type == "PING":
            # Reply with PONG directly back to the leader
            leader_id = msg.get("from")
            await self.rabbit.send_direct(leader_id, {
                "type": "PONG",
                "from": self.id,
            })

        elif msg_type == "PONG":
            # Leader received a pong from a worker
            worker_id = msg.get("from")
            if worker_id is not None:
                self.worker_last_pong[worker_id] = time.time()

        elif msg_type == "TASK":
            # Worker received a task directly from the leader
            await self.handle_worker_task(msg)

    async def handle_broadcast(self, msg):
        msg_type = msg.get("type")

        if msg_type == "ELECTION":
            sender = msg["from"]
            if sender < self.id:
                self.log(f"[Server {self.id}] Election from {sender} (I have higher ID) -> OK")
                await self.rabbit.broadcast_msg({
                    "type": "OK",
                    "to": sender,
                    "from": self.id,
                })
                await self.start_election()

        elif msg_type == "OK":
            if msg.get("to") == self.id:
                self.received_ok = True

        elif msg_type == "TASK_EXECUTED":
            if self.id == self.leader_id:
                task_id   = msg.get("task_id")
                worker_id = msg.get("worker")
                result    = msg.get("result", {})
                self.log(f"[Leader {self.id}] Server {worker_id} executed task {task_id} -> broadcasting done")
                # Remove from in-flight tracking
                self.in_flight.pop(task_id, None)
                await self.rabbit.broadcast_msg({
                    "type": "TASK_DONE", "task_id": task_id, "task": msg["task"],
                    "worker": worker_id, "index": 2, "result": result,
                    "token": msg.get("token", ""),
                })

        elif msg_type == "COORDINATOR":
            new_leader = msg["leader"]
            if new_leader != self.leader_id:
                self.log(f"[Server {self.id}] New Leader: {new_leader}")
            if self.on_status_change:
                self.on_status_change(self.id, "LEADER" if new_leader == self.id else "WORKER")

            # If we think we're leader but a higher ID server claims coordinator,
            # step down immediately — they win per bully algorithm rules
            if self.leader_id == self.id and new_leader != self.id:
                if new_leader > self.id:
                    self.log(f"[Server {self.id}] Higher ID Server {new_leader} is leader -> stepping down")
                if self.heartbeat_task and not self.heartbeat_task.done():
                    self.heartbeat_task.cancel()
                    self.heartbeat_task = None
                if self.task_submission_consumer:
                    try:
                        await self.task_submission_consumer.cancel()
                    except Exception:
                        pass
                    self.task_submission_consumer = None
                    self.log(f"[Server {self.id}] Stepped down - stopped consuming task_submission")

            self.leader_id = new_leader
            self.election_in_progress = False
            self.last_heartbeat = time.time()

            if self.leader_id != self.id and self.heartbeat_task:
                self.heartbeat_task.cancel()
                self.heartbeat_task = None

        elif msg_type == "LEADER_DEAD":
            dead = msg.get("dead_leader")
            self.log(f"[Server {self.id}] Leader {dead} declared dead -> new election")
            if self.leader_id == dead:
                self.leader_id = None
                self.election_in_progress = False

        elif msg_type == "TASK_REPLICATED":
            # A server received replication of an in-flight task from the leader
            # Store it so we can recover if leader crashes
            replicate_task(
                task_id     = msg["task_id"],
                token       = msg.get("token", ""),
                task_name   = msg["task"],
                category    = msg.get("category", ""),
                details     = msg.get("details", {}),
                status      = msg.get("status", "ASSIGNED"),
                assigned_to = msg.get("assigned_to"),
            )

        elif msg_type == "TASK_DONE":
            task_id   = msg.get("task_id")
            task_name = msg.get("task", "Unknown")
            worker_id = msg.get("worker")
            index     = msg.get("index", 2)
            result    = msg.get("result", {})
            # All servers persist completed tasks
            if task_exists(task_id):
                if result.get("success", True):
                    mark_completed(task_id, result)
                else:
                    mark_failed(task_id, result.get("error", "Unknown error"))
            self.log(f"[Server {self.id}] Task {task_id} index {index}: {task_name} done by Server {worker_id}")

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

    async def get_alive_workers(self):
        """Return list of workers that have responded to a PING recently."""
        now = time.time()
        return [
            sid for sid in SERVER_IDS
            if sid != self.id
            and sid in self.worker_last_pong
            and now - self.worker_last_pong[sid] <= PING_TIMEOUT
        ]

    async def handle_task_submission(self, msg):
        if self.id != self.leader_id:
            self.log(f"[Server {self.id}] Not the leader — requeuing task for leader {self.leader_id}")
            raise Exception("not-leader")

        self.task_counter += 1
        task_id = self.task_counter

        token     = msg.get("token", "")
        task_name = msg["task"]
        category  = msg.get("category", "")
        details   = msg.get("details", {})

        # Bug 2 fix: persist task BEFORE worker check so it is never silently lost
        save_task(task_id, token, task_name, category, details)

        # Get currently alive workers
        workers = await self.get_alive_workers()

        if not workers:
            # Bug 3 fix: leader executes the task itself instead of dropping it
            self.log(f"[Leader {self.id}] No alive workers — executing task {task_id} locally")
            mark_assigned(task_id, self.id)
            self.in_flight[task_id] = {
                "token": token, "task": task_name, "category": category,
                "details": details, "worker": self.id, "assigned_at": time.time(),
            }
            asyncio.create_task(self._execute_locally(task_id, task_name, token, details))
            return

        # Pick next worker using round-robin
        self.round_robin_index = self.round_robin_index % len(workers)
        target = workers[self.round_robin_index]
        self.round_robin_index += 1

        self.log(f"[Leader {self.id}] Task {task_id} -> assigning to Server {target} (round-robin, workers={workers})")

        # Persist ASSIGNED to local DB + WAL
        mark_assigned(task_id, target)

        # Track in-flight so we can detect if worker dies
        self.in_flight[task_id] = {
            "token": token, "task": task_name, "category": category,
            "details": details, "worker": target, "assigned_at": __import__("time").time(),
        }

        # Replicate task state to all servers so any new leader can recover
        await self.rabbit.broadcast_msg({
            "type": "TASK_REPLICATED",
            "task_id": task_id,
            "token": token,
            "task": task_name,
            "category": category,
            "details": details,
            "status": "ASSIGNED",
            "assigned_to": target,
        })

        # Send directly to the chosen worker
        await self.rabbit.send_direct(target, {
            "type": "TASK",
            "task_id": task_id,
            "task": task_name,
            "category": category,
            "details": details,
            "token": token,
            "index": 1,
        })

    async def handle_worker_task(self, msg):
        task_id = msg.get("task_id")
        task    = msg.get("task", "Unknown")
        details = msg.get("details", {})
        self.log(f"[Server {self.id}] Executing task {task_id}: {task}")

        # Run the real task implementation
        result = await execute_task(task, details)

        if result.get("success"):
            self.log(f"[Server {self.id}] Task {task_id} completed successfully")
        else:
            self.log(f"[Server {self.id}] Task {task_id} failed: {result.get('error')}")

        if self.leader_id is not None:
            await self.rabbit.broadcast_msg({
                "type": "TASK_EXECUTED",
                "task_id": task_id,
                "task": task,
                "worker": self.id,
                "result": result,
                "token": msg.get("token", ""),
            })
            self.log(f"[Server {self.id}] Task {task_id} result sent to leader")

    async def _execute_locally(self, task_id, task_name, token, details):
        """Leader executes a task itself when no workers are available."""
        self.log(f"[Leader {self.id}] Executing task {task_id} locally: {task_name}")
        result = await execute_task(task_name, details)
        if result.get("success"):
            self.log(f"[Leader {self.id}] Task {task_id} completed locally")
        else:
            self.log(f"[Leader {self.id}] Task {task_id} failed locally: {result.get('error')}")
        self.in_flight.pop(task_id, None)
        await self.rabbit.broadcast_msg({
            "type": "TASK_DONE",
            "task_id": task_id,
            "task": task_name,
            "worker": self.id,
            "result": result,
            "token": token,
        })

    async def recover_tasks(self):
        """
        Called when a new leader is elected.
        Reads local DB for any PENDING or ASSIGNED tasks and re-queues them.
        This handles the case where the previous leader crashed mid-execution.
        """
        await asyncio.sleep(3)  # wait for cluster to stabilize after election
        incomplete = get_incomplete_tasks()
        if not incomplete:
            self.log(f"[Leader {self.id}] Recovery: no incomplete tasks found")
            return

        self.log(f"[Leader {self.id}] Recovery: found {len(incomplete)} incomplete task(s) — re-queuing")
        workers = await self.get_alive_workers()
        if not workers:
            self.log(f"[Leader {self.id}] Recovery: no alive workers to assign to")
            return

        for task in incomplete:
            task_id   = task["task_id"]
            task_name = task["task_name"]
            details   = json.loads(task["details"]) if task["details"] else {}
            token     = task["token"] or ""

            # Pick next worker
            self.round_robin_index = self.round_robin_index % len(workers)
            target = workers[self.round_robin_index]
            self.round_robin_index += 1

            self.log(f"[Leader {self.id}] Recovery: re-assigning task {task_id} to Server {target}")
            mark_assigned(task_id, target)

            self.in_flight[task_id] = {
                "token": token, "task": task_name,
                "category": task.get("category", ""),
                "details": details, "worker": target,
                "assigned_at": __import__("time").time(),
            }

            await self.rabbit.send_direct(target, {
                "type": "TASK",
                "task_id": task_id,
                "task": task_name,
                "category": task.get("category", ""),
                "details": details,
                "token": token,
                "index": 1,
            })

    async def monitor_in_flight(self):
        """
        Leader periodically checks in-flight tasks.
        If the assigned worker has gone offline, reassign to another worker.
        """
        while self.alive and self.leader_id == self.id:
            await asyncio.sleep(5)
            now = __import__("time").time()
            workers = await self.get_alive_workers()
            stale_timeout = PING_TIMEOUT + PING_INTERVAL + 2  # grace period

            for task_id, info in list(self.in_flight.items()):
                worker = info["worker"]
                # Check if assigned worker is still alive
                last_pong = self.worker_last_pong.get(worker, 0)
                worker_dead = (worker not in workers) and (now - last_pong > stale_timeout)

                if worker_dead:
                    self.log(f"[Leader {self.id}] Worker {worker} died with task {task_id} in-flight — reassigning")
                    if not workers:
                        self.log(f"[Leader {self.id}] No alive workers to reassign task {task_id}")
                        continue

                    self.round_robin_index = self.round_robin_index % len(workers)
                    new_target = workers[self.round_robin_index]
                    self.round_robin_index += 1

                    mark_assigned(task_id, new_target)
                    self.in_flight[task_id]["worker"] = new_target
                    self.in_flight[task_id]["assigned_at"] = now

                    await self.rabbit.broadcast_msg({
                        "type": "TASK_REPLICATED",
                        "task_id": task_id,
                        "token": info["token"],
                        "task": info["task"],
                        "category": info["category"],
                        "details": info["details"],
                        "status": "ASSIGNED",
                        "assigned_to": new_target,
                    })

                    await self.rabbit.send_direct(new_target, {
                        "type": "TASK",
                        "task_id": task_id,
                        "task": info["task"],
                        "category": info["category"],
                        "details": info["details"],
                        "token": info["token"],
                        "index": 1,
                    })
                    self.log(f"[Leader {self.id}] Task {task_id} reassigned to Server {new_target}")

    async def ping_loop(self):
        """Leader pings each worker directly every PING_INTERVAL seconds."""
        # Give workers a moment to start up before first ping
        await asyncio.sleep(PING_INTERVAL)
        while self.alive and self.leader_id == self.id:
            for sid in SERVER_IDS:
                if sid == self.id:
                    continue
                try:
                    await self.rabbit.send_direct(sid, {
                        "type": "PING",
                        "from": self.id,
                    })
                except Exception as e:
                    self.log(f"[Leader {self.id}] Failed to ping Server {sid}: {e}")
            await asyncio.sleep(PING_INTERVAL)

    async def heartbeat_loop(self):
        """Leader broadcasts heartbeat every second with list of alive workers."""
        while self.alive and self.leader_id == self.id:
            try:
                now = time.time()
                # Only include workers we have actually received a PONG from recently.
                # Servers not yet in worker_last_pong are unknown — exclude them until
                # they respond to a ping.
                alive_workers = [
                    sid for sid in SERVER_IDS
                    if sid != self.id
                    and sid in self.worker_last_pong
                    and now - self.worker_last_pong[sid] <= PING_TIMEOUT
                ]
                await self.rabbit.send_heartbeat({
                    "leader": self.id,
                    "workers": alive_workers,
                })
            except Exception as e:
                # Bug 4 fix: don't let a RabbitMQ blip kill the heartbeat loop.
                # The robust connection will reconnect; we just keep looping.
                self.log(f"[Leader {self.id}] Heartbeat send failed: {e} — will retry")
            await asyncio.sleep(1)

    async def monitor_heartbeat(self):
        """Workers watch for leader silence and trigger a new election."""
        while self.alive:
            if (
                self.leader_id
                and self.leader_id != self.id
                and time.time() - self.last_heartbeat > HEARTBEAT_TIMEOUT
            ):
                dead_leader = self.leader_id
                self.log(f"[Server {self.id}] Leader {dead_leader} timed out -> new election")
                await self.rabbit.broadcast_msg({
                    "type": "LEADER_DEAD",
                    "dead_leader": dead_leader,
                    "caller": self.id,
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
        self.worker_last_pong = {}    # reset pong tracking for new term
        self.round_robin_index = 0    # reset round-robin for new term
        self.in_flight = {}           # reset in-flight tracking for new term

        if self.on_status_change:
            self.on_status_change(self.id, "LEADER")

        self.log(f"[Server {self.id}] I AM LEADER")
        await self.rabbit.broadcast_msg({
            "type": "COORDINATOR",
            "leader": self.id,
        })

        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        asyncio.create_task(self.ping_loop())
        asyncio.create_task(self.recover_tasks())
        asyncio.create_task(self.monitor_in_flight())

        try:
            self.task_submission_consumer = await self.rabbit.consume_task_submission(
                self.handle_task_submission
            )
        except Exception as e:
            self.log(f"[Server {self.id}] Failed task consumer: {e}")