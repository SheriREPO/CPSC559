import React from "react";

function getStatusDotClass(status) {
  const normalized = String(status || "").toLowerCase();

  if (normalized === "leader" || normalized === "worker") {
    return "status-dot online";
  }

  if (normalized === "offline") {
    return "status-dot offline";
  }

  return "status-dot";
}

function getServerCardClass(status) {
  const normalized = String(status || "").toLowerCase();

  if (normalized === "leader") {
    return "server-card leader";
  }

  if (normalized === "offline") {
    return "server-card offline";
  }

  return "server-card";
}

function formatLastSeen(lastSeen) {
  if (!lastSeen) {
    return "No activity yet";
  }

  const now = Date.now() / 1000;
  const diff = Math.max(0, Math.floor(now - lastSeen));

  if (diff < 2) {
    return "Just now";
  }

  if (diff < 60) {
    return `${diff}s ago`;
  }

  const minutes = Math.floor(diff / 60);

  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function normalizeServers(servers) {
  if (!servers) {
    return [];
  }

  if (Array.isArray(servers)) {
    return servers;
  }

  return Object.entries(servers).map(([id, data]) => ({
    id: Number(id),
    ...data,
  }));
}

function ServerGrid({ servers = {} }) {
  const serverList = normalizeServers(servers).sort(
    (a, b) => Number(a.id) - Number(b.id)
  );

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Cluster Servers</h2>
          <p className="card-subtitle">
            Current replica states across the distributed task system.
          </p>
        </div>
      </div>

      <div className="card-body">
        {serverList.length > 0 ? (
          <div className="server-grid">
            {serverList.map((server) => {
              const status = server.status || "Unknown";
              const normalized = String(status).toUpperCase();

              return (
                <div
                  key={server.id}
                  className={getServerCardClass(status)}
                >
                  <div className="server-title">
                    <div>
                      <h3 className="server-name">Server {server.id}</h3>
                      <div className="server-role">{normalized}</div>
                    </div>

                    <span className={getStatusDotClass(status)} />
                  </div>

                  <div className="server-info">
                    <div>
                      <strong>Status:</strong> {status}
                    </div>
                    <div>
                      <strong>Last seen:</strong>{" "}
                      {formatLastSeen(server.last_seen)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <h3>No server data yet</h3>
            <p>
              Once the cluster connects and starts broadcasting state, the
              server replicas will appear here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ServerGrid;