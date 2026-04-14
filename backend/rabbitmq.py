# rabbitmq.py
import aio_pika
import json
from aio_pika import ExchangeType, Message, DeliveryMode
from config import TASK_SUBMISSION_QUEUE, WORKER_TASKS_QUEUE


class RabbitMQ:
    def __init__(self, url, log):
        self.url = url
        self.log = log

    async def connect(self, server_id=None):
        self.conn = await aio_pika.connect_robust(self.url)
        self.channel = await self.conn.channel()

        # ── Exchanges ────────────────────────────────────────────────────────
        self.direct = await self.channel.declare_exchange(
            "direct_exchange", ExchangeType.DIRECT, durable=True
        )
        self.broadcast = await self.channel.declare_exchange(
            "broadcast_exchange", ExchangeType.FANOUT, durable=True
        )
        self.heartbeat = await self.channel.declare_exchange(
            "heartbeat_exchange", ExchangeType.FANOUT, durable=True
        )

        # ── Shared queues ────────────────────────────────────────────────────
        self.task_submission_queue = await self.channel.declare_queue(
            TASK_SUBMISSION_QUEUE, durable=True
        )
        await self.task_submission_queue.bind(self.direct, routing_key=TASK_SUBMISSION_QUEUE)

        self.worker_tasks_queue = await self.channel.declare_queue(
            WORKER_TASKS_QUEUE, durable=True
        )
        await self.worker_tasks_queue.bind(self.direct, routing_key=WORKER_TASKS_QUEUE)

        # ── Per-server direct queue (for PING/PONG) ──────────────────────────
        # Each server gets its own queue named "server_<id>" so the leader
        # can ping a specific worker and the worker can reply directly back.
        if server_id is not None:
            self.server_id = server_id
            queue_name = f"server_{server_id}"
            self.direct_queue = await self.channel.declare_queue(
                queue_name, durable=True
            )
            await self.direct_queue.bind(self.direct, routing_key=queue_name)

        self.log("[RabbitMQ] Connected")

    async def close(self):
        if hasattr(self, "conn") and self.conn and not self.conn.is_closed:
            await self.conn.close()

    # ── Task submission ───────────────────────────────────────────────────────
    async def submit_task(self, payload):
        self.log(f"[RabbitMQ] → task_submission | {payload}")
        msg = Message(
            json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT
        )
        await self.direct.publish(msg, routing_key=TASK_SUBMISSION_QUEUE)

    async def publish_to_workers(self, payload):
        self.log(f"[RabbitMQ] → worker_tasks | {payload}")
        msg = Message(
            json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT
        )
        await self.direct.publish(msg, routing_key=WORKER_TASKS_QUEUE)

    async def consume_task_submission(self, callback):
        async def handler(msg):
            async with msg.process(requeue=True):
                body = json.loads(msg.body.decode())
                self.log(f"[RabbitMQ] ← task_submission | {body}")
                await callback(body)

        consumer = await self.task_submission_queue.consume(handler)
        return consumer

    async def consume_worker_tasks(self, callback):
        async def handler(msg):
            async with msg.process():
                body = json.loads(msg.body.decode())
                self.log(f"[RabbitMQ] ← worker_tasks | {body}")
                await callback(body)

        await self.worker_tasks_queue.consume(handler)

    # ── Broadcast (fanout) ────────────────────────────────────────────────────
    async def broadcast_msg(self, payload):
        self.log(f"[RabbitMQ] → broadcast | {payload}")
        msg = Message(json.dumps(payload).encode())
        await self.broadcast.publish(msg, routing_key="")

    async def consume_broadcast(self, callback):
        queue = await self.channel.declare_queue(exclusive=True)
        await queue.bind(self.broadcast)

        async def handler(msg):
            async with msg.process():
                body = json.loads(msg.body.decode())
                self.log(f"[RabbitMQ] ← broadcast | {body}")
                await callback(body)

        await queue.consume(handler)

    # ── Heartbeat (fanout) ────────────────────────────────────────────────────
    async def send_heartbeat(self, payload):
        msg = Message(json.dumps(payload).encode())
        await self.heartbeat.publish(msg, routing_key="")

    async def consume_heartbeat(self, callback):
        queue = await self.channel.declare_queue(exclusive=True)
        await queue.bind(self.heartbeat)

        async def handler(msg):
            async with msg.process():
                body = json.loads(msg.body.decode())
                await callback(body)

        await queue.consume(handler)

    # ── Direct PING/PONG (point-to-point) ────────────────────────────────────
    async def send_direct(self, target_server_id, payload):
        """Send a message directly to a specific server's queue."""
        msg = Message(json.dumps(payload).encode())
        await self.direct.publish(msg, routing_key=f"server_{target_server_id}")

    async def consume_direct(self, callback):
        """Consume messages from this server's own direct queue."""
        async def handler(msg):
            async with msg.process():
                body = json.loads(msg.body.decode())
                await callback(body)

        await self.direct_queue.consume(handler)