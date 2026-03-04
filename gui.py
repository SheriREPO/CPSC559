# gui.py
import tkinter as tk
from tkinter import ttk
import asyncio
import threading
from server import Server
from config import SERVER_IDS, TASK_OPTIONS

servers = {}
status_labels = {}
loop = asyncio.new_event_loop()


def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()


threading.Thread(target=start_loop, daemon=True).start()


def log(msg):
    at_bottom = log_box.yview()[1] == 1.0
    log_box.insert(tk.END, msg + "\n")
    if at_bottom:
        log_box.see(tk.END)


def update_status(server_id, status):
    if server_id in status_labels:
        status_labels[server_id].config(
            text=status,
            fg="green" if status == "LEADER" else "blue"
        )


def start_server(server_id):
    if server_id in servers:
        return

    def on_status_change(sid, status):
        root.after(0, lambda: update_status(sid, status))

    server = Server(server_id, log, on_status_change=on_status_change)
    servers[server_id] = server

    asyncio.run_coroutine_threadsafe(server.start(), loop)
    status_labels[server_id].config(text="Joining...", fg="gray")
    log(f"[GUI] Started Server {server_id}")


def stop_server(server_id):
    if server_id in servers:
        server = servers[server_id]
        asyncio.run_coroutine_threadsafe(server.stop(), loop)
        del servers[server_id]
        status_labels[server_id].config(text="—", fg="gray")
        log(f"[GUI] Stopped Server {server_id}")


def submit_task():
    if not servers:
        log("[GUI] No servers running")
        return

    task_display = task_var.get()
    category = next((cat for cat, name in TASK_OPTIONS if name == task_display), "")
    payload = {"type": "TASK", "task": task_display, "category": category}

    def find_leader():
        for s in servers.values():
            if s.leader_id == s.id:
                return s
        return None

    def try_submit(retries_left=25):
        leader = find_leader()
        if leader:
            asyncio.run_coroutine_threadsafe(leader.rabbit.submit_task(payload), loop)
            log(f"[GUI] Task submitted to Leader {leader.id}: {task_display}")
            return

        if retries_left <= 0:
            log("[GUI] No leader elected yet — try again in a moment.")
            return

        root.after(200, lambda: try_submit(retries_left - 1))

    try_submit()


def show_completed_tasks():
    leader = None
    for s in servers.values():
        if s.leader_id == s.id:
            leader = s
            break

    if not leader:
        log("[GUI] No leader right now.")
        return

    tasks = getattr(leader, "completed_tasks", [])
    log(f"[GUI] Leader {leader.id} completed tasks ({len(tasks)}):")

    if not tasks:
        log("  (none)")
        return

    for t in tasks:
        log(f"  - task_id={t['task_id']} | {t['task']} | worker={t['worker']}")


root = tk.Tk()
root.title("Distributed Task System (Bully Election + RabbitMQ)")
root.geometry("1200x700")

style = ttk.Style()
style.configure("TCombobox", font=("Consolas", 14))
style.configure("TButton", font=("Consolas", 14))
style.configure("TLabel", font=("Consolas", 14))

header = tk.Label(
    root,
    text="[ Client → task_submission → Leader → worker_tasks → Workers | Bully election ]",
    font=("Consolas", 14),
    fg="gray"
)
header.pack(pady=5)

server_frame = tk.LabelFrame(root, text="Servers")
server_frame.pack(fill=tk.X, padx=10, pady=5)

for server_id in SERVER_IDS:
    frame = tk.Frame(server_frame)
    frame.pack(fill=tk.X)

    tk.Label(frame, text=f"Server {server_id}", width=10).pack(side=tk.LEFT)

    status_lbl = tk.Label(frame, text="—", width=10, fg="gray")
    status_lbl.pack(side=tk.LEFT, padx=5)
    status_labels[server_id] = status_lbl

    tk.Button(frame, text="Start", command=lambda s=server_id: start_server(s)).pack(side=tk.LEFT, padx=3)
    tk.Button(frame, text="Stop", command=lambda s=server_id: stop_server(s)).pack(side=tk.LEFT, padx=3)

task_frame = tk.LabelFrame(root, text="Submit Task")
task_frame.pack(fill=tk.X, padx=10, pady=5)

task_var = tk.StringVar(value=TASK_OPTIONS[0][1])
task_combo = ttk.Combobox(
    task_frame,
    textvariable=task_var,
    values=[opt[1] for opt in TASK_OPTIONS],
    width=70,
    state="readonly"
)
task_combo.pack(side=tk.LEFT, padx=5, pady=5)

tk.Button(task_frame, text="Submit Task", command=submit_task).pack(side=tk.LEFT, padx=5, pady=5)
tk.Button(task_frame, text="Show Completed (Leader)", command=show_completed_tasks).pack(side=tk.LEFT, padx=5, pady=5)

log_frame = tk.Frame(root)
log_frame.pack(fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(log_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

log_box = tk.Text(
    log_frame,
    height=25,
    width=120,
    yscrollcommand=scrollbar.set,
    font=("Consolas", 14)
)
log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar.config(command=log_box.yview)

root.mainloop()