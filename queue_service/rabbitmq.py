import asyncio
import aio_pika
import json
from typing import Callable
from aio_pika import ExchangeType, DeliveryMode, Message
from aio_pika.abc import AbstractIncomingMessage


class RabbitMQ:
    _instance = None

    def __init__(self, url: str):
        self.url = url
        self._connection = None
        self._read_channel = None
        self._write_channel = None
        self._exchange = None
        self._broadcast_exchange = None

    @classmethod
    def get_instance(cls, url: str = None):
        if cls._instance is None:
            cls._instance = cls(url)
        return cls._instance

    async def connect(self):
        self._connection = await aio_pika.connect_robust(self.url)
        self._read_channel = await self._connection.channel()
        self._write_channel = await self._connection.channel()

        await self._read_channel.set_qos(prefetch_count=1)

        # One shared exchange for the app
        self._exchange = await self._write_channel.declare_exchange(
            "app_exchange",
            ExchangeType.DIRECT,
            durable=True
        )
        # One shared broadcast exchange for the app
        self._broadcast_exchange = await self._write_channel.declare_exchange(
            "broadcast_exchange",
            ExchangeType.FANOUT,
            durable=True
        )
        print("RabbitMQ connected.")

    async def disconnect(self):
        if self._connection:
            await self._connection.close()
            print("RabbitMQ disconnected.")

    async def send_to_queue(self, routing_key: str, payload: dict):
        """Publish a message to a queue via routing key."""
        message = Message(
            body=json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT
        )
        await self._exchange.publish(message, routing_key=routing_key)
        print(f"[→] Sent to '{routing_key}': {payload}")

    async def subscribe_to_queue(self, queue_name: str):
        """Declare and bind a queue to the shared exchange."""
        queue = await self._read_channel.declare_queue(queue_name, durable=True)
        await queue.bind(self._exchange, routing_key=queue_name)
        print(f"[✓] Subscribed to queue: '{queue_name}'")
        return queue

    async def consume_from_queue(self, queue_name: str, callback: Callable):
        """Subscribe and start consuming messages from a queue."""
        queue = await self.subscribe_to_queue(queue_name)

        async def _handle(message: AbstractIncomingMessage):
            async with message.process():
                payload = json.loads(message.body.decode())
                await callback(payload)

        await queue.consume(_handle)
        print(f"[👂] Consuming from queue: '{queue_name}'")
        
        
        
    # for the bully algo
    
    async def send_to_node(self, node_id: int, payload: dict):
        await self.send_to_queue(f"node_{node_id}", payload)
        
        
    async def broadcast(self, payload: dict):
        message = Message(
            body=json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT
        )
        await self._broadcast_exchange.publish(message, routing_key="")
        print(f"[📢] Broadcast: {payload}")
    
    async def subscribe_to_broadcast(self, callback: Callable):
        # Exclusive queue — unique per node instance, auto deleted when node dies
        queue = await self._read_channel.declare_queue(exclusive=True)
        await queue.bind(self._broadcast_exchange)

        async def _handle(message: AbstractIncomingMessage):
            async with message.process():
                payload = json.loads(message.body.decode())
                await callback(payload)
        await queue.consume(_handle)