import { useState } from "react";

export default function TaskHistory({ tasks }) {
  const reversed = [...tasks].reverse();
  const [expanded, setExpanded] = useState(null);

  return (
    <div className="panel">
      <div className="panel-header">Task History</div>
      {reversed.length === 0
        ? <span className="empty">No completed tasks yet</span>
        : (
          <div className="table-scroll">
            <table className="task-table">
              <thead>
                <tr><th>#</th><th>Task</th><th>Worker</th><th>Time</th><th></th></tr>
              </thead>
              <tbody>
                {reversed.map((t, i) => (
                  <>
                    <tr key={i} className={t.success === false ? "task-row-failed" : ""}>
                      <td className="dim">{t.id}</td>
                      <td>{t.success === false ? "❌" : "✅"} {t.task}</td>
                      <td className="worker">S{t.worker}</td>
                      <td className="dim">{t.time}</td>
                      <td>
                        {t.result && (
                          <button
                            className="btn-result"
                            onClick={() => setExpanded(expanded === i ? null : i)}
                          >
                            {expanded === i ? "hide" : "result"}
                          </button>
                        )}
                      </td>
                    </tr>
                    {expanded === i && t.result && (
                      <tr key={`${i}-result`}>
                        <td colSpan={5} className="result-cell">
                          <ResultView result={t.result} task={t.task} />
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
    </div>
  );
}

function ResultView({ result, task }) {
  if (!result.success) {
    return <div className="result-error">Error: {result.error}</div>;
  }

  if (result.result_image) {
    const mime = result.format === "PNG" ? "image/png" : "image/jpeg";
    return (
      <div className="result-image-wrap">
        <div className="result-meta">
          {result.original_size} → {result.new_size} · {result.format}
        </div>
        <img
          src={`data:${mime};base64,${result.result_image}`}
          alt="resized"
          className="result-image"
        />
      </div>
    );
  }

  if (result.sent_to) {
    return (
      <div className="result-text">
        📧 Sent to <strong>{result.sent_to}</strong> · Subject: {result.subject}
      </div>
    );
  }

  if (result.simulated) {
    return (
      <div className="result-text">
        🔔 Notification sent to <strong>{result.topic}</strong>: {result.message}
      </div>
    );
  }

  if (result.sentiment) {
    const colors = { positive: "#00e5a0", negative: "#ff5c5c", neutral: "#f0c040" };
    const color = colors[result.sentiment?.toLowerCase()] || "#c8d0db";
    return (
      <div className="result-sentiment">
        <span className="sentiment-badge" style={{ color }}>
          {result.sentiment?.toUpperCase()}
        </span>
        {result.confidence && (
          <span className="dim"> · {(result.confidence * 100).toFixed(0)}% confidence</span>
        )}
        {result.reasoning && (
          <div className="result-reasoning">{result.reasoning}</div>
        )}
      </div>
    );
  }

  if (result.summary) {
    return (
      <div className="result-summary">
        <div className="result-summary-text">{result.summary}</div>
        {result.key_points?.length > 0 && (
          <ul className="result-key-points">
            {result.key_points.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        )}
        {result.word_count && (
          <div className="dim result-wordcount">{result.word_count} words in original</div>
        )}
      </div>
    );
  }

  if (result.category || result.classification) {
    return (
      <div className="result-text">
        <strong>{result.category || result.classification}</strong>
        {result.labels?.length > 0 && (
          <span className="dim"> · {result.labels.join(", ")}</span>
        )}
      </div>
    );
  }

  return (
    <pre className="result-raw">{JSON.stringify(result, null, 2)}</pre>
  );
}
