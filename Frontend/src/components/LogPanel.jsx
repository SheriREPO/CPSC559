// components/LogPanel.jsx
import { useEffect, useRef } from "react";

export default function LogPanel({ logs }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  return (
    <div className="panel">
      <div className="panel-header">Live Event Log</div>
      <div className="log-box" ref={ref}>
        {logs.length === 0
          ? <span className="empty">Waiting for events...</span>
          : logs.map((line, i) => (
              <div key={i} className={`log-line ${i === logs.length - 1 ? "fresh" : ""}`}>
                {line}
              </div>
            ))
        }
      </div>
    </div>
  );
}
