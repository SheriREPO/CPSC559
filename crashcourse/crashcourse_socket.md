
When you open a TCP connection with asyncio:
reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
```

You get back two objects:
```
reader  →  for receiving data (reading from the socket)
writer  →  for sending data   (writing to the socket)
'
What is a StreamWriter?
A StreamWriter is basically a handle to one end of a TCP pipe. When you want to send a message to Server 2, you grab its writer and call:
writer.write(b"hello\n")
await writer.drain()   # actually flushes it out

Why await
drain() is async because flushing data to a network can take a moment — especially if:

The network is slow
The receiver's buffer is full
The OS is busy

await means — wait for the flush to complete, but let other async tasks run in the meantime instead of freezing everything.


What is asyncio.AbstractServer?
When you call asyncio.start_server(...) it returns a server object that represents your listening socket — the thing sitting on a port waiting for incoming connections.
It's called "Abstract" because it's a base class. You don't create it directly, asyncio creates it for you and hands it back.


What and why use asyncio.create_task(...)
this takes that coroutine and says "run this in the background, don't wait for it".

_connect_to_peer retries up to 20 times with 0.5s gaps between each attempt. That means it could take up to 10 seconds per peer.
If you used await instead:
python# BAD — sequential, blocks everything
await self._connect_to_peer(1)   # waits up to 10s
await self._connect_to_peer(2)   # then waits up to 10s
await self._connect_to_peer(3)   # then waits up to 10s
await self._connect_to_peer(4)   # then waits up to 10s
# total: up to 40 seconds before connect() finishes
With create_task:
python# GOOD — all run simultaneously in background
asyncio.create_task(self._connect_to_peer(1))   # starts, runs in background
asyncio.create_task(self._connect_to_peer(2))   # starts, runs in background
asyncio.create_task(self._connect_to_peer(3))   # starts, runs in background
asyncio.create_task(self._connect_to_peer(4))   # starts, runs in background
# connect() finishes immediately
# all 4 connections attempt simultaneously
# total: up to 10s max (not 40s)


await asyncio.gather(*tasks, return_exceptions=True)

 if Server 2 was dead:
results = [
    None,              # send_to(1) succeeded, no return value
    ConnectionError,   # send_to(2) failed, exception stored here
    None,              # send_to(4) succeeded
    None,              # send_to(5) succeeded
]

actually runs everything, waits for all to finish

## Simple Decision Rule
```
Do I need to wait for it to finish before moving on?
  YES → gather (or await)
  NO  → create_task

Do I need to run multiple things at the same time?
  YES + need to wait    → gather
  YES + don't need wait → create_task for each
  NO                    → plain await