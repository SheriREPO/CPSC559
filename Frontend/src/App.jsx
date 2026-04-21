// App.jsx
import { useWebSocket } from "./hooks/useWebSocket.js";
import ServerGrid      from "./components/ServerGrid.jsx";
import TaskForm        from "./components/TaskForm.jsx";
import LogPanel        from "./components/LogPanel.jsx";
import TaskHistory     from "./components/TaskHistory.jsx";
import ToastContainer  from "./components/Toast.jsx";

export default function App() {
  const { connected, servers, logs, tasks, toasts, removeToast } = useWebSocket();
  const hasLeader = Object.values(servers).some((s) => s.status === "Leader");

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>DISTASK</h1>
          <span className="header-sub">Distributed Task System · Bully Election + RabbitMQ</span>
        </div>
        <div className={`conn-pill ${connected ? "on" : "off"}`}>
          <span className="conn-dot" />
          {connected ? "Live" : "Reconnecting..."}
        </div>
      </header>

      <ServerGrid servers={servers} />
      <TaskForm connected={connected} hasLeader={hasLeader} tasks={tasks} />

      <section className="bottom-grid">
        <LogPanel logs={logs} />
        <TaskHistory tasks={tasks} />
      </section>

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
}