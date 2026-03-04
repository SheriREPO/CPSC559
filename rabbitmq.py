# rabbitmq.py
import json
import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode
from config import TASK_SUBMISSION_QUEUE, WORKER_TASKS_QUEUE


class RabbitMQ:
    def __init__(self, url: str, log, server_id: int):
        self.url = url
        self.log = log
        self.server_id = server_id

        self.conn = None
        self.channel = None

        self.direct = None
        self.broadcast = None
        self.heartbeat = None

        self.task_submission_queue_name = None
        self.task_submission_queue = None

        self.worker_tasks_queue = None

    async def connect(self):
        self.conn = await aio_pika.connect_robust(self.url)
        self.channel = await self.conn.channel()

        self.direct = await self.channel.declare_exchange(
            "direct_exchange", ExchangeType.DIRECT, durable=True
        )
        self.broadcast = await self.channel.declare_exchange(
            "broadcast_exchange", ExchangeType.FANOUT, durable=True
        )
        self.heartbeat = await self.channel.declare_exchange(
            "heartbeat_exchange", ExchangeType.FANOUT, durable=True
        )


        # Not bound by default; only leader binds it.
        self.task_submission_queue_name = f"{TASK_SUBMISSION_QUEUE}.{self.server_id}"
        self.task_submission_queue = await self.channel.declare_queue(
            self.task_submission_queue_name, durable=True
        )

        # Shared worker tasks queue
        self.worker_tasks_queue = await self.channel.declare_queue(
            WORKER_TASKS_QUEUE, durable=True
        )
        await self.worker_tasks_queue.bind(self.direct, routing_key=WORKER_TASKS_QUEUE)

        self.log("[RabbitMQ] Connected")

    async def close(self):
        if self.conn and not self.conn.is_closed:
            await self.conn.close()

    # ----------------------------
    # Leader-only bind/unbind
    # ----------------------------
    async def bind_task_submission(self):
        await self.task_submission_queue.bind(self.direct, routing_key=TASK_SUBMISSION_QUEUE)
        self.log(f"[RabbitMQ] Bound {self.task_submission_queue_name} to {TASK_SUBMISSION_QUEUE}")

    async def unbind_task_submission(self):
        try:
            await self.task_submission_queue.unbind(self.direct, routing_key=TASK_SUBMISSION_QUEUE)
            self.log(f"[RabbitMQ] Unbound {self.task_submission_queue_name} from {TASK_SUBMISSION_QUEUE}")
        except Exception:
            pass

    # ----------------------------
    # Publishing
    # ----------------------------
    async def submit_task(self, payload: dict):
        self.log(f"[RabbitMQ] → task_submission | {payload}")
        msg = Message(
            json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await self.direct.publish(msg, routing_key=TASK_SUBMISSION_QUEUE)

    async def publish_to_workers(self, payload: dict):
        self.log(f"[RabbitMQ] → worker_tasks | {payload}")
        msg = Message(
            json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await self.direct.publish(msg, routing_key=WORKER_TASKS_QUEUE)

    # ----------------------------
    # Consuming
    # ----------------------------
    async def consume_task_submission(self, callback):
        async def handler(msg: aio_pika.IncomingMessage):
            async with msg.process():
                body = json.loads(msg.body.decode())
                self.log(f"[RabbitMQ] ← task_submission | {body}")
                await callback(body)

        consumer_tag = await self.task_submission_queue.consume(handler)
        return consumer_tag

    async def consume_worker_tasks(self, callback):
        async def handler(msg: aio_pika.IncomingMessage):
            async with msg.process():
                body = json.loads(msg.body.decode())
                self.log(f"[RabbitMQ] ← worker_tasks | {body}")
                await callback(body)

        await self.worker_tasks_queue.consume(handler)

    # ----------------------------
    # Broadcast + heartbeat
    # ----------------------------
    async def broadcast_msg(self, payload: dict):
        self.log(f"[RabbitMQ] → broadcast | {payload}")
        msg = Message(json.dumps(payload).encode())
        await self.broadcast.publish(msg, routing_key="")

    async def send_heartbeat(self, payload: dict):
        msg = Message(json.dumps(payload).encode())
        await self.heartbeat.publish(msg, routing_key="")

    async def consume_broadcast(self, callback):
        queue = await self.channel.declare_queue(exclusive=True)
        await queue.bind(self.broadcast)

        async def handler(msg: aio_pika.IncomingMessage):
            async with msg.process():
                body = json.loads(msg.body.decode())
                self.log(f"[RabbitMQ] ← broadcast | {body}")
                await callback(body)

        await queue.consume(handler)

    async def consume_heartbeat(self, callback):
        queue = await self.channel.declare_queue(exclusive=True)
        await queue.bind(self.heartbeat)

        async def handler(msg: aio_pika.IncomingMessage):
            async with msg.process():
                body = json.loads(msg.body.decode())
                await callback(body)

        await queue.consume(handler)