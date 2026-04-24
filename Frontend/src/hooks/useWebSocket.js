import { useState, useEffect, useRef } from "react";

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [servers, setServers] = useState(
    Object.fromEntries([1, 2, 3, 4, 5].map((id) => [id, { status: "Offline" }]))
  );
  const [logs, setLogs] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [toasts, setToasts] = useState([]);
  const wsRef = useRef(null);
  const prevTasksRef = useRef([]);

  function addToast(type, title, message) {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, type, title, message }]);
  }

  function removeToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  useEffect(() => {
    function connect() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen  = () => setConnected(true);
      ws.onclose = () => { setConnected(false); setTimeout(connect, 2000); };
      ws.onerror = () => ws.close();

      ws.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if (d.type === "state") {
          setServers(d.servers);
          setLogs(d.logs   || []);

          const newTasks = d.tasks || [];

          const prevIds = new Set(prevTasksRef.current.map((t) => t.id));
          const incoming = newTasks.filter((t) => !prevIds.has(t.id));

          incoming.forEach((t) => {
            if (t.success === false) {
              addToast(
                "error",
                `Task #${t.id} failed`,
                t.result?.error || t.task,
              );
            } else {
              addToast(
                "success",
                `Task #${t.id} completed`,
                `${t.task} · Server ${t.worker}`,
              );
            }
          });

          prevTasksRef.current = newTasks;
          setTasks(newTasks);
        }
      };
    }

    connect();
    return () => wsRef.current?.close();
  }, []);

  return { connected, servers, logs, tasks, toasts, removeToast };
}