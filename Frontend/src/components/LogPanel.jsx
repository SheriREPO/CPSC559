import React from "react";

function LogPanel({ logs = [] }) {
  const hasLogs = Array.isArray(logs) && logs.length > 0;

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">System Logs</h2>
          <p className="card-subtitle">
            Live cluster events, elections, heartbeats, and task activity.
          </p>
        </div>
      </div>

      <div className="card-body">
        {hasLogs ? (
          <div className="log-list">
            {[...logs].reverse().map((log, index) => (
              <div
                key={`${log}-${index}`}
                className="log-item"
                title={log}
              >
                {log}
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <h3>No logs yet</h3>
            <p>
              Cluster activity will appear here once servers start elections,
              send heartbeats, or process tasks.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default LogPanel;