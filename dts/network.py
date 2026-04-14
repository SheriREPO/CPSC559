# Uses asyncio streams. Every node listens on its own port.
# Messages are newline-delimited JSON over persistent TCP connections.
import asyncio
import json
from config import SERVER_IDS, BASE_PORT

def port_for(server_id: int) -> int:
    """Each server listens on BASE_PORT + server_id (e.g. 9001, 9002 ...)"""
    return BASE_PORT + server_id


class Network:
    
    def __init__(self,server_id, log):
        self.id = server_id
        self.log = log
        self.port = port_for(server_id)
        # Maps server_id → StreamWriter for active connections
        self.writers: dict[int, asyncio.StreamWriter] = {}
        
        # callbacks registered by Server
        self._on_broadcast: callable = None
        self._on_heartbeat: callable = None
        self._on_worker_task: callable = None
        self._on_task_submission: callable = None
        
        self._server: asyncio.AbstractServer = None
        self._running = False
        
    # ─────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────      
    async def start(self):
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_connection, 
            host="127.0.0.1",
            port=self.port,
        )
        self.log(f"[Network {self.id}] Listening on port {self.port}")
        
        for peer_id in SERVER_IDS:
            if peer_id != self.id:
                asyncio.create_task(self._connect_to_peer(peer_id))


    async def close(self):
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for writer in list(self._writers.values()):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        self._writers.clear()

    # ─────────────────────────────────────────────
    # Outbound connection management
    # ─────────────────────────────────────────────


    async def _connect_to_peer(self, peer_id: int, retries: int = 20):
        """Try to establish a persistent connection to peer_id."""
        peer_port = port_for(peer_id)
        for attempt in range(retries):
            if not self._running:
                return
            try:
                _,writer = await asyncio.open_connection("127.0.0.1", peer_port)
                self._writers[peer_id] = writer
                self.log(f"[Network {self.id}] Connected -> Server{peer_id} on port {peer_port}")
                return 
            except (ConnectionRefusedError, OSError):
                await asyncio.sleep(0.5)
            self.log(f"[Network {self.id}] Failed to connect to Server{peer_id} on port {peer_port} (attempt {attempt + 1}/{retries})")
            
    async def _ensure_connected(self, peer_id: int):
        """Reconnect if our writer to peer_id is stale/closed."""
        writer = self._writers.get(peer_id)
        if writer is None or writer.is_closing():
            self._writers.pop(peer_id, None)
            await self._connect_to_peer(peer_id, retries=5)





    # ─────────────────────────────────────────────
    # Inbound connection handler
    # ─────────────────────────────────────────────

    async def _handle_incoming(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Called by asyncio for every new inbound TCP connection."""
        addr = writer.get_extra_info("peername")
        try:
            while self._running:
                line = await reader.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode().strip())
                except json.JSONDecodeError:
                    continue
                await self._dispatch(msg)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


    async def _dispatch(self, msg: dict):
        """Route an incoming message to the right callback."""
        msg_type = msg.get("type", "")

        if msg_type == "HEARTBEAT":
            if self._on_heartbeat:
                await self._on_heartbeat(msg)

        elif msg_type in ("TASK", "TASK_SUBMISSION"):
            # A task destined for a worker (TASK) or submitted by a client (TASK_SUBMISSION)
            if msg_type == "TASK_SUBMISSION" and self._on_task_submission:
                await self._on_task_submission(msg)
            elif msg_type == "TASK" and self._on_worker_task:
                await self._on_worker_task(msg)

        else:
            # Everything else: ELECTION, OK, COORDINATOR, LEADER_DEAD,
            # TASK_EXECUTED, TASK_DONE, WORKER_HB …
            if self._on_broadcast:
                await self._on_broadcast(msg)
                
                
    async def _send_to(self, peer_id: int, msg: dict):
        await self._ensure_connected(peer_id)
        writer = self._writers.get(peer_id)
        if writer is None:
            self.log(f"[Network {self.id}] ✗ No connection to Server {peer_id}, dropping: {payload.get('type')}")
            return
        try: 
            data = (json.dumps(msg) + "\n").encode()
            writer.write(data)
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            self.log(f"[Network {self.id}] ✗ Lost connection to Server {peer_id}")
            self._writers.pop(peer_id, None)
            
    
    async def broadcast_msg(self, payload: dict):
        """Send a message to ALL other nodes"""
        self.log(f"[Network {self.id}] → broadcast | {payload}")
        tasks = [self._send_to(pid, payload) for pid in SERVER_IDS if pid != self.id]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def send_heartbeat(self,payload:dict):
        self.log(f"[Network {self.id}] → heartbeat | {payload}")
        tasks = [self._send_to(pid,payload) for pid in SERVER_IDS if pid != self.id]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def send_to_worker(self,worker_id:int, payload:dict):
        self.log(f"[Network {self.id}] → worker_{worker_id} | {payload}")
        await self._send_to(worker_id, payload)
        
    async def submit_task(self, payload: dict):
        # Client submits a task.
        # Sends TASK_SUBMISSION directly to whichever node is currently leader.
        payload["type"] = "TASK_SUBMISSION"
        self.log(f"[Network {self.id}] → task_submission | {payload}")
        await self._send_to(payload["leader_id"], payload)
        
        
    async def consume_broadcast(self, callback):
        """Register handler for all broadcast messages (ELECTION, OK, COORDINATOR, …)."""
        self._on_broadcast = callback

    async def consume_heartbeat(self, callback):
        """Register handler for HEARTBEAT messages."""
        self._on_heartbeat = callback

    async def consume_worker_tasks(self, callback):
        """Register handler for TASK messages sent directly to this worker."""
        self._on_worker_task = callback

    async def consume_task_submission(self, callback):
        """Register handler for TASK_SUBMISSION messages (leader only)."""
        self._on_task_submission = callback
        # Returns a dummy token — server.py stores it; we just return self
        return self