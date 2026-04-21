// components/ServerGrid.jsx
export default function ServerGrid({ servers }) {
  return (
    <section className="server-section">
      <h2 className="section-label">Cluster Health</h2>
      <div className="servers-grid">
        {Object.entries(servers).map(([id, state]) => (
          <ServerCard key={id} id={id} status={state.status} />
        ))}
      </div>
    </section>
  );
}

function ServerCard({ id, status }) {
  const cls   = status === "Leader" ? "leader" : status === "Worker" ? "worker" : "offline";
  const icons = { Leader: "★", Worker: "◆", Offline: "○" };
  return (
    <div className={`server-card ${cls}`}>
      <span className="server-icon">{icons[status] ?? "○"}</span>
      <span className="server-name">S{id}</span>
      <span className={`badge ${cls}`}>{status}</span>
    </div>
  );
}
