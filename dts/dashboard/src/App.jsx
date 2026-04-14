import { useState, useEffect, useRef, useCallback } from "react";

// ── CONFIG ────────────────────────────────────────────────────────
const DASH_API  = "http://127.0.0.1:8001";   // dashboard bridge  (server.py state)
const TASK_API  = "http://127.0.0.1:8000";   // task FastAPI      (does real work)
const SERVER_IDS = [1, 2, 3, 4, 5];

const TASK_OPTIONS = [
  { category: "AI/ML",           task: "Running sentiment analysis on text",           endpoint: "/ai/sentiment",  icon: "🤖" },
  { category: "AI/ML",           task: "Generating summaries using an LLM API",        endpoint: "/ai/summarize",  icon: "🤖" },
  { category: "File Processing", task: "Image resizing/compression",                   endpoint: "/file/resize",   icon: "📁" },
  { category: "File Processing", task: "File format conversion (docx → pdf)",          endpoint: "/file/convert",  icon: "📁" },
  { category: "Notification",    task: "Send emails (welcome, password reset, alerts)", endpoint: "/notify/email", icon: "🔔" },
  { category: "Notification",    task: "Slack/Discord webhook messages",                endpoint: "/notify/slack", icon: "🔔" },
  { category: "Data Processing", task: "Scraping and storing web data",                 endpoint: "/data/scrape",  icon: "🗃️" },
  { category: "Data Processing", task: "Aggregating analytics (daily reports)",         endpoint: "/data/report",  icon: "🗃️" },
  { category: "Dev/DevOps",      task: "Running tests on code submissions",             endpoint: "/dev/test",     icon: "⚙️" },
  { category: "Dev/DevOps",      task: "Linting and formatting code",                   endpoint: "/dev/lint",     icon: "⚙️" },
];

const CAT_COLORS = {
  "AI/ML":           { bg: "rgba(244,114,182,0.12)", border: "rgba(244,114,182,0.4)",  text: "#f472b4" },
  "File Processing": { bg: "rgba(96,165,250,0.12)",  border: "rgba(96,165,250,0.4)",   text: "#60a5fa" },
  "Notification":    { bg: "rgba(167,139,250,0.12)", border: "rgba(167,139,250,0.4)",  text: "#a78bfa" },
  "Data Processing": { bg: "rgba(52,211,153,0.12)",  border: "rgba(52,211,153,0.4)",   text: "#34d399" },
  "Dev/DevOps":      { bg: "rgba(251,146,60,0.12)",  border: "rgba(251,146,60,0.4)",   text: "#fb923c" },
};

// ── STYLES ────────────────────────────────────────────────────────
const css = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;700&family=Bebas+Neue&display=swap');

  :root {
    --bg:      #060a0f;
    --s1:      #0b1018;
    --s2:      #101820;
    --border:  #182030;
    --border2: #1e2d40;
    --leader:  #f59e0b;
    --worker:  #34d399;
    --dead:    #ef4444;
    --elec:    #818cf8;
    --text:    #c9d8e8;
    --dim:     #3d5470;
  }
  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  body {
    background:var(--bg); font-family:'IBM Plex Mono',monospace;
    color:var(--text); min-height:100vh; overflow-x:hidden;
  }
  body::before {
    content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
    background-image:radial-gradient(circle,rgba(34,211,238,0.04) 1px,transparent 1px);
    background-size:28px 28px;
  }
  .app { position:relative; z-index:1; max-width:1400px; margin:0 auto; padding:32px 24px 80px; }

  /* HEADER */
  .hdr { display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:36px; }
  .hdr h1 { font-family:'Bebas Neue'; font-size:clamp(32px,6vw,68px); letter-spacing:0.04em; line-height:0.9; color:#fff; }
  .hdr h1 span { color:var(--leader); }
  .hdr-sub { font-size:9px; color:var(--dim); letter-spacing:0.2em; text-transform:uppercase; margin-top:8px; }
  .hdr-right { display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
  .api-pill {
    display:flex; align-items:center; gap:6px; font-size:9px;
    padding:4px 10px; border-radius:20px; border:1px solid;
  }
  .api-pill.ok  { color:var(--worker); border-color:rgba(52,211,153,0.3); background:rgba(52,211,153,0.06); }
  .api-pill.err { color:var(--dead);   border-color:rgba(239,68,68,0.3);  background:rgba(239,68,68,0.06); }
  .dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
  .dot.ok  { background:var(--worker); animation:pulse 2s ease-in-out infinite; }
  .dot.err { background:var(--dead); }

  /* STATS */
  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }
  .stat { padding:14px 16px; background:var(--s1); border:1px solid var(--border2); border-radius:8px; }
  .stat-val { font-family:'Bebas Neue'; font-size:34px; letter-spacing:0.04em; line-height:1; }
  .stat-key { font-size:8px; letter-spacing:0.2em; text-transform:uppercase; color:var(--dim); margin-top:3px; }

  /* ELECTION BANNER */
  .elec-banner {
    display:flex; align-items:center; gap:10px; padding:10px 16px;
    background:rgba(129,140,248,0.08); border:1px solid rgba(129,140,248,0.35);
    border-radius:6px; font-size:10px; color:var(--elec); margin-bottom:20px;
    animation:elecPulse 1s ease-in-out infinite;
  }
  @keyframes elecPulse { 0%,100%{border-color:rgba(129,140,248,0.35)} 50%{border-color:rgba(129,140,248,0.75)} }

  /* PANEL */
  .panel { background:var(--s1); border:1px solid var(--border2); border-radius:10px; overflow:hidden; margin-bottom:20px; }
  .panel-hdr {
    padding:11px 18px; border-bottom:1px solid var(--border2);
    display:flex; justify-content:space-between; align-items:center;
  }
  .panel-title { font-size:9px; letter-spacing:0.2em; text-transform:uppercase; color:var(--dim); }
  .panel-body  { padding:18px; }

  /* NODES */
  .nodes-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }
  .node-card {
    background:var(--s2); border:1px solid var(--border);
    border-radius:8px; padding:14px 12px; position:relative; overflow:hidden;
    transition:all 0.2s;
  }
  .node-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:var(--nc,var(--border)); }
  .node-card.alive:hover { transform:translateY(-2px); border-color:var(--nc,var(--border2)); }
  .node-card.off { opacity:0.45; }

  .node-id { font-family:'Bebas Neue'; font-size:30px; letter-spacing:0.05em; color:var(--nc,var(--text)); line-height:1; margin-bottom:5px; }
  .node-role {
    font-size:8px; font-weight:700; letter-spacing:0.15em; text-transform:uppercase;
    padding:2px 7px; border-radius:2px; display:inline-block; margin-bottom:8px;
  }
  .role-leader   { background:rgba(245,158,11,0.15); color:var(--leader); border:1px solid rgba(245,158,11,0.4); }
  .role-worker   { background:rgba(52,211,153,0.1);  color:var(--worker); border:1px solid rgba(52,211,153,0.3); }
  .role-election { background:rgba(129,140,248,0.1); color:var(--elec);   border:1px solid rgba(129,140,248,0.3); }
  .role-off      { background:rgba(255,255,255,0.04);color:var(--dim);    border:1px solid var(--border); }

  .node-hb { width:6px; height:6px; border-radius:50%; position:absolute; top:10px; right:10px; }
  .node-hb.on  { background:var(--worker); animation:pulse 1.5s ease-in-out infinite; }
  .node-hb.off { background:var(--dim); opacity:0.3; }

  .node-meta { font-size:9px; color:var(--dim); line-height:1.8; }

  .node-btns { display:flex; gap:6px; margin-top:10px; }
  .btn-sm {
    flex:1; padding:5px 0; font-size:8px; font-family:'IBM Plex Mono'; font-weight:700;
    letter-spacing:0.1em; text-transform:uppercase; border-radius:3px; cursor:pointer;
    border:1px solid; transition:all 0.15s;
  }
  .btn-start { background:rgba(52,211,153,0.08); color:var(--worker); border-color:rgba(52,211,153,0.3); }
  .btn-start:hover:not(:disabled) { background:rgba(52,211,153,0.18); }
  .btn-stop  { background:rgba(239,68,68,0.08);  color:var(--dead);   border-color:rgba(239,68,68,0.3); }
  .btn-stop:hover:not(:disabled)  { background:rgba(239,68,68,0.18); }
  .btn-sm:disabled { opacity:0.35; cursor:not-allowed; }

  /* TASK SUBMIT */
  .task-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:14px; }
  .task-opt {
    padding:9px 12px; border-radius:6px; cursor:pointer;
    border:1px solid var(--border); background:var(--s2);
    transition:all 0.15s; display:flex; align-items:center; gap:8px;
  }
  .task-opt:hover  { border-color:var(--border2); }
  .task-opt.active { border-color:var(--tc-b,var(--border2)); background:var(--tc-bg,var(--s2)); }
  .task-icon { font-size:14px; flex-shrink:0; }
  .task-cat  { font-size:8px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--dim); }
  .task-cat.active { color:var(--tc,var(--dim)); }
  .task-name { font-size:9px; color:var(--text); line-height:1.4; margin-top:1px;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

  .submit-btn {
    width:100%; padding:12px; font-family:'Bebas Neue'; font-size:18px; letter-spacing:0.1em;
    background:rgba(245,158,11,0.1); color:var(--leader);
    border:1px solid rgba(245,158,11,0.4); border-radius:6px; cursor:pointer;
    transition:all 0.2s;
  }
  .submit-btn:hover:not(:disabled) { background:rgba(245,158,11,0.2); }
  .submit-btn:disabled { opacity:0.4; cursor:not-allowed; }
  .submit-hint { margin-top:8px; font-size:9px; color:var(--dead); text-align:center; }

  /* TASK LIST */
  .task-list { display:flex; flex-direction:column; gap:6px; max-height:340px; overflow-y:auto; }
  .task-row {
    display:flex; align-items:center; gap:8px; padding:8px 10px;
    border-radius:5px; border:1px solid var(--border); background:var(--s2); font-size:9px;
    animation:slideIn 0.2s ease both;
  }
  .task-seq   { color:var(--dim); min-width:22px; flex-shrink:0; }
  .task-badge { font-size:7px; font-weight:700; padding:2px 6px; border-radius:2px; letter-spacing:0.08em; flex-shrink:0; }
  .task-desc  { flex:1; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .task-wkr   { color:var(--dim); flex-shrink:0; font-size:9px; }
  .task-res   { color:var(--worker); font-size:8px; flex-shrink:0; max-width:130px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .st-running  { background:rgba(52,211,153,0.1);  color:var(--worker); border:1px solid rgba(52,211,153,0.3); }
  .st-done     { background:rgba(255,255,255,0.05);color:var(--dim);    border:1px solid var(--border); }
  .st-reassign { background:rgba(239,68,68,0.1);   color:var(--dead);   border:1px solid rgba(239,68,68,0.3); }

  /* LOG */
  .log-box { height:240px; overflow-y:auto; font-size:9px; line-height:2; }
  .log-line { display:flex; gap:8px; animation:slideIn 0.15s ease both; }
  .log-time { color:var(--dim); flex-shrink:0; font-size:8px; }
  .log-msg   { flex:1; }
  .c-leader { color:var(--leader); }
  .c-worker { color:var(--worker); }
  .c-elec   { color:var(--elec); }
  .c-err    { color:var(--dead); }
  .c-done   { color:#34d399; }
  .c-def    { color:var(--text); }

  /* GRID */
  .two-col { display:grid; grid-template-columns:1fr 1fr; gap:20px; }

  ::-webkit-scrollbar { width:3px; }
  ::-webkit-scrollbar-thumb { background:var(--border2); border-radius:2px; }

  @keyframes pulse    { 0%,100%{opacity:0.6;transform:scale(1)} 50%{opacity:1;transform:scale(1.35)} }
  @keyframes slideIn  { from{opacity:0;transform:translateX(-6px)} to{opacity:1;transform:translateX(0)} }
`;

// ── HELPERS ──────────────────────────────────────────────────────
function ts() {
  return new Date().toLocaleTimeString("en-CA", { hour12: false });
}

function msgClass(text) {
  if (!text) return "c-def";
  const t = text.toLowerCase();
  if (t.includes("★") || t.includes("coordinator") || t.includes("i am leader")) return "c-elec";
  if (t.includes("election") || t.includes("ok") || t.includes("bully"))         return "c-elec";
  if (t.includes("leader"))   return "c-leader";
  if (t.includes("✓") || t.includes("done") || t.includes("completed"))          return "c-done";
  if (t.includes("✗") || t.includes("error") || t.includes("dead") || t.includes("timed out") || t.includes("fail")) return "c-err";
  if (t.includes("worker"))   return "c-worker";
  return "c-def";
}

async function apiFetch(path, opts = {}) {
  const r = await fetch(DASH_API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ── APP ───────────────────────────────────────────────────────────
export default function App() {
  // ── Real state from backend ──
  const [nodes,     setNodes]     = useState(() =>
    Object.fromEntries(SERVER_IDS.map(id => [id, {
      id, role: "off", leader_id: null, term: 0,
      alive: false, tasks_done: 0, election_active: false,
    }]))
  );
  const [tasks,     setTasks]     = useState([]);
  const [leaderId,  setLeaderId]  = useState(null);

  // ── Connection status ──
  const [dashOnline, setDashOnline] = useState(false);
  const [taskOnline, setTaskOnline] = useState(false);

  // ── UI state ──
  const [logs,       setLogs]      = useState([]);
  const [selected,   setSelected]  = useState(TASK_OPTIONS[0]);
  const [submitting, setSubmitting] = useState(false);
  const [loading,    setLoading]   = useState({});   // node_id → true while starting/stopping

  const logRef    = useRef(null);
  const prevNodes = useRef({});

  // ── Add log entry ──
  const addLog = useCallback((text) => {
    setLogs(p => [...p.slice(-300), { id: Date.now() + Math.random(), time: ts(), text }]);
  }, []);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  // ── Poll /state every second ──
  useEffect(() => {
    let alive = true;

    const poll = async () => {
      try {
        const data = await apiFetch("/state");
        if (!alive) return;

        setDashOnline(true);
        setNodes(data.nodes);
        setLeaderId(data.leader_id);
        setTasks(data.tasks || []);

        // Generate log lines from state changes
        const prev = prevNodes.current;
        Object.values(data.nodes).forEach(n => {
          const p = prev[n.id];
          if (!p) return;
          if (p.role !== n.role) {
            if (n.role === "leader")
              addLog(`[Server ${n.id}] ★ I AM LEADER (term ${n.term})`);
            else if (n.role === "worker" && p.role === "leader")
              addLog(`[Server ${n.id}] Stepped down → WORKER`);
            else if (n.role === "worker" && p.role === "off")
              addLog(`[Server ${n.id}] Joined as WORKER`);
          }
          if (!p.election_active && n.election_active)
            addLog(`[Server ${n.id}] Starting election (term ${n.term + 1})`);
        });
        prevNodes.current = data.nodes;

      } catch {
        if (alive) setDashOnline(false);
      }
    };

    poll();
    const t = setInterval(poll, 1000);
    return () => { alive = false; clearInterval(t); };
  }, [addLog]);

  // ── Check task API health ──
  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch(`${TASK_API}/health`, { signal: AbortSignal.timeout(2000) });
        setTaskOnline(r.ok);
      } catch { setTaskOnline(false); }
    };
    check();
    const t = setInterval(check, 5000);
    return () => clearInterval(t);
  }, []);

  // ── Start node ──
  const startNode = useCallback(async (id) => {
    setLoading(p => ({ ...p, [id]: true }));
    addLog(`[GUI] Starting Server ${id}...`);
    try {
      await apiFetch(`/node/${id}/start`, { method: "POST" });
      addLog(`[GUI] Server ${id} started`);
    } catch (e) {
      addLog(`[GUI] ✗ Failed to start Server ${id}: ${e.message}`);
    }
    setLoading(p => ({ ...p, [id]: false }));
  }, [addLog]);

  // ── Stop node ──
  const stopNode = useCallback(async (id) => {
    setLoading(p => ({ ...p, [id]: true }));
    addLog(`[GUI] Stopping Server ${id}...`);
    try {
      await apiFetch(`/node/${id}/stop`, { method: "POST" });
      addLog(`[GUI] Server ${id} stopped`);
    } catch (e) {
      addLog(`[GUI] ✗ Failed to stop Server ${id}: ${e.message}`);
    }
    setLoading(p => ({ ...p, [id]: false }));
  }, [addLog]);

  // ── Submit task ──
  const submitTask = useCallback(async () => {
    if (!dashOnline) { addLog("[Error] Dashboard API offline — run main.py first"); return; }
    if (!leaderId)   { addLog("[Error] No leader elected — start some servers first"); return; }

    setSubmitting(true);
    addLog(`[GUI] Submitting: ${selected.task}`);

    try {
      const resp = await apiFetch("/submit", {
        method: "POST",
        body: JSON.stringify({ task: selected.task, category: selected.category }),
      });
      addLog(`[Leader ${resp.leader_id}] Received task → assigning to worker`);
    } catch (e) {
      addLog(`[GUI] ✗ Submit failed: ${e.message}`);
    }
    setSubmitting(false);
  }, [dashOnline, leaderId, selected, addLog]);

  // ── Derived ──
  const runningCount   = Object.values(nodes).filter(n => n.alive).length;
  const electionActive = Object.values(nodes).some(n => n.election_active);
  const currentTerm    = leaderId ? (nodes[leaderId]?.term ?? 0) : 0;
  const doneTasks      = tasks.filter(t => t.status === "done").length;

  // ── Node colour ──
  function nodeColor(n) {
    if (n.role === "leader") return "var(--leader)";
    if (n.role === "worker") return "var(--worker)";
    return "var(--dim)";
  }

  return (
    <>
      <style>{css}</style>
      <div className="app">

        {/* ── HEADER ── */}
        <div className="hdr">
          <div>
            <h1>DISTRIBUTED<br/>TASK <span>QUEUE</span></h1>
            <div className="hdr-sub">CPSC 559 · Bully Election · TCP Sockets · Live Backend</div>
          </div>
          <div className="hdr-right">
            <div className={`api-pill ${dashOnline ? "ok" : "err"}`}>
              <div className={`dot ${dashOnline ? "ok" : "err"}`}></div>
              Dashboard API {dashOnline ? "ONLINE :8001" : "OFFLINE — run main.py"}
            </div>
            <div className={`api-pill ${taskOnline ? "ok" : "err"}`}>
              <div className={`dot ${taskOnline ? "ok" : "err"}`}></div>
              Task API {taskOnline ? "ONLINE :8000" : "OFFLINE — run api.py"}
            </div>
          </div>
        </div>

        {/* ── ELECTION BANNER ── */}
        {electionActive && (
          <div className="elec-banner">
            <span style={{ fontSize: 16 }}>🗳</span>
            BULLY ELECTION IN PROGRESS — highest alive node ID will become leader...
          </div>
        )}

        {/* ── STATS ── */}
        <div className="stats">
          <div className="stat">
            <div className="stat-val" style={{ color: "var(--worker)" }}>{runningCount}</div>
            <div className="stat-key">Nodes Online</div>
          </div>
          <div className="stat">
            <div className="stat-val" style={{ color: "var(--leader)" }}>
              {leaderId ? `S${leaderId}` : "—"}
            </div>
            <div className="stat-key">Current Leader</div>
          </div>
          <div className="stat">
            <div className="stat-val" style={{ color: "var(--elec)" }}>{currentTerm}</div>
            <div className="stat-key">Election Term</div>
          </div>
          <div className="stat">
            <div className="stat-val" style={{ color: "var(--text)" }}>{doneTasks}</div>
            <div className="stat-key">Tasks Completed</div>
          </div>
        </div>

        {/* ── NODES ── */}
        <div className="panel">
          <div className="panel-hdr">
            <span className="panel-title">Node Cluster — Real State from server.py</span>
            <span style={{ fontSize: 9, color: "var(--dim)" }}>{runningCount}/5 running</span>
          </div>
          <div className="panel-body">
            <div className="nodes-grid">
              {SERVER_IDS.map(id => {
                const n  = nodes[id] || { role: "off", alive: false, term: 0, tasks_done: 0 };
                const nc = nodeColor(n);
                const isOff = !n.alive;
                const busy  = loading[id];
                const roleClass =
                  n.role === "leader"   ? "role-leader" :
                  n.role === "worker"   ? "role-worker" :
                  n.election_active     ? "role-election" : "role-off";

                return (
                  <div
                    key={id}
                    className={`node-card ${isOff ? "off" : "alive"}`}
                    style={{ "--nc": nc }}
                  >
                    <div className={`node-hb ${isOff ? "off" : "on"}`}></div>
                    <div className="node-id">S{id}</div>
                    <div className={`node-role ${roleClass}`}>
                      {n.election_active ? "ELECTION" : n.role.toUpperCase()}
                    </div>
                    <div className="node-meta">
                      {n.alive ? (
                        <>
                          <div>term {n.term}</div>
                          <div>✓ {n.tasks_done} tasks</div>
                          {n.leader_id && n.role !== "leader" && (
                            <div style={{ color: "var(--leader)", fontSize: 8 }}>→ leader S{n.leader_id}</div>
                          )}
                        </>
                      ) : (
                        <div>not running</div>
                      )}
                    </div>
                    <div className="node-btns">
                      <button
                        className="btn-sm btn-start"
                        onClick={() => startNode(id)}
                        disabled={n.alive || busy || !dashOnline}
                      >{busy && !n.alive ? "..." : "Start"}</button>
                      <button
                        className="btn-sm btn-stop"
                        onClick={() => stopNode(id)}
                        disabled={!n.alive || busy || !dashOnline}
                      >{busy && n.alive ? "..." : "Stop"}</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── BOTTOM GRID ── */}
        <div className="two-col">

          {/* ── TASK SUBMIT ── */}
          <div className="panel" style={{ marginBottom: 0 }}>
            <div className="panel-hdr">
              <span className="panel-title">Submit Task</span>
              {leaderId && (
                <span style={{ fontSize: 9, color: "var(--leader)" }}>→ Leader S{leaderId}</span>
              )}
            </div>
            <div className="panel-body">
              <div className="task-grid">
                {TASK_OPTIONS.map((opt, i) => {
                  const cc     = CAT_COLORS[opt.category] || {};
                  const active = selected.task === opt.task;
                  return (
                    <div
                      key={i}
                      className={`task-opt ${active ? "active" : ""}`}
                      style={active ? { "--tc-bg": cc.bg, "--tc-b": cc.border } : {}}
                      onClick={() => setSelected(opt)}
                    >
                      <span className="task-icon">{opt.icon}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className={`task-cat ${active ? "active" : ""}`}
                             style={active ? { color: cc.text } : {}}>{opt.category}</div>
                        <div className="task-name">{opt.task}</div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <button
                className="submit-btn"
                onClick={submitTask}
                disabled={submitting || !leaderId || !dashOnline}
              >
                {submitting ? "SUBMITTING..." : "▶  SUBMIT TASK TO LEADER"}
              </button>

              {!dashOnline && (
                <div className="submit-hint">Run: python main.py</div>
              )}
              {dashOnline && !leaderId && (
                <div className="submit-hint">Start at least one server node first</div>
              )}
            </div>
          </div>

          {/* ── TASK LIST ── */}
          <div className="panel" style={{ marginBottom: 0 }}>
            <div className="panel-hdr">
              <span className="panel-title">Task Queue — Live from Leader</span>
              <span style={{ fontSize: 9, color: "var(--dim)" }}>{tasks.length} tasks</span>
            </div>
            <div className="panel-body">
              {tasks.length === 0 ? (
                <div style={{ textAlign: "center", color: "var(--dim)", fontSize: 10, padding: "48px 0" }}>
                  No tasks yet — submit one to get started
                </div>
              ) : (
                <div className="task-list">
                  {tasks.map(t => {
                    const cc = CAT_COLORS[t.category] || {};
                    return (
                      <div key={t.task_id} className="task-row">
                        <span className="task-seq">#{t.task_id}</span>
                        <span className="task-badge"
                              style={{ background: cc.bg, color: cc.text, border: `1px solid ${cc.border}` }}>
                          {t.category}
                        </span>
                        <span className="task-desc">{t.task}</span>
                        <span className="task-wkr">W{t.worker}</span>
                        <span className={`task-badge st-${t.status}`}>{t.status?.toUpperCase()}</span>
                        {t.result && <span className="task-res">{t.result}</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── LOG ── */}
        <div className="panel" style={{ marginTop: 20 }}>
          <div className="panel-hdr">
            <span className="panel-title">System Log — State Changes from server.py</span>
            <button
              onClick={() => setLogs([])}
              style={{
                fontSize: 8, padding: "2px 8px", background: "transparent",
                color: "var(--dim)", border: "1px solid var(--border)",
                borderRadius: 3, cursor: "pointer", fontFamily: "inherit",
              }}
            >CLEAR</button>
          </div>
          <div className="panel-body" style={{ padding: "12px 18px" }}>
            <div className="log-box" ref={logRef}>
              {logs.length === 0 ? (
                <div style={{ color: "var(--dim)", fontSize: 10 }}>
                  {dashOnline
                    ? "Start server nodes to see activity..."
                    : "Waiting for dashboard API — run: python main.py"}
                </div>
              ) : logs.map(l => (
                <div key={l.id} className="log-line">
                  <span className="log-time">{l.time}</span>
                  <span className={`log-msg ${msgClass(l.text)}`}>{l.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </>
  );
}
