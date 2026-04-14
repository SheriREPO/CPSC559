# server_runner.py
import asyncio
import os
from server import Server


async def main():
    server_id = int(os.environ.get("SERVER_ID", 1))

    def log(msg):
        print(msg, flush=True)

    log(f"[Runner] Server {server_id} starting — waiting for RabbitMQ...")

    # Stagger startup so all 5 servers don't hammer RabbitMQ at once
    await asyncio.sleep(server_id * 1.5)

    for attempt in range(20):
        try:
            log(f"[Runner] Server {server_id} connecting (attempt {attempt + 1}/20)...")
            # Create a fresh Server instance on every attempt
            server = Server(server_id, log)
            await server.start()
            log(f"[Runner] Server {server_id} connected successfully")
            break
        except Exception as e:
            log(f"[Runner] Server {server_id} failed: {e}")
            await asyncio.sleep(4)
    else:
        log(f"[Runner] Server {server_id} gave up after 20 attempts")
        return

    # Keep running; restart if RabbitMQ connection drops
    while True:
        await asyncio.sleep(5)
        try:
            conn = getattr(server.rabbit, "conn", None)
            if conn is not None and conn.is_closed:
                log(f"[Runner] Server {server_id} lost RabbitMQ connection — restarting")
                await server.stop()
                for attempt in range(20):
                    try:
                        server = Server(server_id, log)
                        await server.start()
                        log(f"[Runner] Server {server_id} reconnected successfully")
                        break
                    except Exception as e:
                        log(f"[Runner] Server {server_id} reconnect attempt {attempt + 1} failed: {e}")
                        await asyncio.sleep(4)
        except Exception as e:
            log(f"[Runner] Server {server_id} health-check error: {e}")


if __name__ == "__main__":
    asyncio.run(main())