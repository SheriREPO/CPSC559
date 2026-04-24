import { useState, useRef, useEffect } from "react";
import { TASKS, CATEGORIES } from "../tasks.js";

const STEPS = ["Category", "Task", "Details"];

function DynamicFields({ fields, values, onChange }) {
  const fileInputRef = useRef(null);

  function handleImageChange(e, name) {
    const file = e.target.files[0];
    if (!file) return;
    const previewUrl = URL.createObjectURL(file);
    const reader = new FileReader();
    reader.onload = () => {
      onChange(name, {
        filename: file.name,
        base64: reader.result.split(",")[1],
        preview: previewUrl,
      });
    };
    reader.readAsDataURL(file);
  }

  return (
    <div className="dynamic-fields">
      {fields.map((field) => (
        <div key={field.name} className="field-group">
          <label className="field-label">{field.label}</label>

          {field.type === "text" && (
            <input className="field-input" type="text"
              placeholder={field.placeholder || ""}
              value={values[field.name] || ""}
              onChange={(e) => onChange(field.name, e.target.value)}
            />
          )}

          {field.type === "textarea" && (
            <textarea className="notes-field" rows={4}
              placeholder={field.placeholder || ""}
              value={values[field.name] || ""}
              onChange={(e) => onChange(field.name, e.target.value)}
            />
          )}

          {field.type === "image" && (
            <div className="image-upload-area">
              <input ref={fileInputRef} type="file" accept="image/*"
                style={{ display: "none" }}
                onChange={(e) => handleImageChange(e, field.name)}
              />
              {values[field.name]?.preview ? (
                <div className="image-preview-wrap">
                  <img src={values[field.name].preview} alt="preview" className="image-preview"/>
                  <div className="image-preview-meta">
                    <span className="image-filename">{values[field.name].filename}</span>
                    <button className="btn-ghost btn-small" onClick={() => onChange(field.name, null)}>Remove</button>
                  </div>
                </div>
              ) : (
                <button className="upload-btn" onClick={() => fileInputRef.current.click()}>
                  <span className="upload-icon">↑</span>
                  Click to upload image
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function TaskForm({ connected, hasLeader, tasks }) {
  const [step, setStep] = useState(0);
  const [category, setCategory] = useState(null);
  const [task, setTask] = useState(null);
  const [fieldValues, setFieldValues] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState("idle"); // "idle" | "waiting" | "done" | "failed"
  const [pendingToken, setPendingToken] = useState(null);
  const [completedTask, setCompletedTask] = useState(null);

  const filtered = TASKS.filter((t) => t.category === category);

  useEffect(() => {
    if (status !== "waiting" || pendingToken === null) return;
    const found = tasks.find((t) => t.token === pendingToken);
    if (found) {
      setCompletedTask(found);
      setStatus(found.success === false ? "failed" : "done");
    }
  }, [tasks, pendingToken, status]);

  function handleFieldChange(name, value) {
    setFieldValues((prev) => ({ ...prev, [name]: value }));
  }

  function reset() {
    setStep(0); setCategory(null); setTask(null);
    setFieldValues({}); setStatus("idle"); setPendingToken(null); setCompletedTask(null);
  }

  function isDetailsValid() {
    if (!task?.fields?.length) return true;
    return task.fields.every((f) => {
      const val = fieldValues[f.name];
      if (f.type === "image") return val?.base64;
      return val && val.trim() !== "";
    });
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const details = {};
      if (task.fields) {
        task.fields.forEach((f) => {
          if (f.type === "image") {
            details[f.name] = { filename: fieldValues[f.name]?.filename, base64: fieldValues[f.name]?.base64 };
          } else {
            details[f.name] = fieldValues[f.name] || "";
          }
        });
      }

      const res = await fetch("/api/submit-task", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: task.name, category: task.category, details }),
      });

      const data = await res.json();

      if (data.token) {
        setPendingToken(data.token);
        setStatus("waiting");
      } else {
        setStatus("done");
      }
    } catch (e) {
      setStatus("failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (status === "waiting") return (
    <section className="form-section">
      <h2 className="section-label">Submit Task</h2>
      <div className="form-box success-box">
        <div className="waiting-spinner" />
        <p className="success-title">Processing...</p>
        <p className="success-sub">{task?.icon} {task?.name}</p>
        <p className="success-sub" style={{ marginTop: 4 }}>Waiting for worker to complete</p>
      </div>
    </section>
  );

  if (status === "done") return (
    <section className="form-section">
      <h2 className="section-label">Submit Task</h2>
      <div className="form-box success-box">
        <div className="success-icon">✓</div>
        <p className="success-title">Task completed</p>
        <p className="success-sub">{task?.icon} {task?.name} · Server {completedTask?.worker}</p>
        <button className="btn-primary" onClick={reset}>Submit another</button>
      </div>
    </section>
  );

  if (status === "failed") return (
    <section className="form-section">
      <h2 className="section-label">Submit Task</h2>
      <div className="form-box success-box">
        <div className="success-icon" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>✕</div>
        <p className="success-title">Task failed</p>
        <p className="success-sub">{completedTask?.result?.error || "Unknown error"}</p>
        <button className="btn-primary" onClick={reset}>Try again</button>
      </div>
    </section>
  );

  return (
    <section className="form-section">
      <h2 className="section-label">Submit Task</h2>

      <div className="steps-row">
        {STEPS.map((label, i) => (
          <span key={label} className="step-group">
            <div className={`step-dot ${i < step ? "done" : i === step ? "active" : ""}`}>
              {i < step ? "✓" : i + 1}
            </div>
            <span className={`step-label ${i === step ? "active" : ""}`}>{label}</span>
            {i < STEPS.length - 1 && <div className={`step-line ${i < step ? "done" : ""}`} />}
          </span>
        ))}
      </div>

      <div className="form-box">
        {step === 0 && (
          <div className="step-content">
            <p className="step-prompt">What kind of task is this?</p>
            <div className="choice-grid">
              {CATEGORIES.map((cat) => (
                <button key={cat} className={`choice-btn ${category === cat ? "selected" : ""}`}
                  onClick={() => setCategory(cat)}>{cat}</button>
              ))}
            </div>
            <div className="form-actions">
              <button className="btn-primary" disabled={!category} onClick={() => setStep(1)}>Next →</button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="step-content">
            <p className="step-prompt">Which task in <strong>{category}</strong>?</p>
            <div className="task-list">
              {filtered.map((t) => (
                <button key={t.name}
                  className={`task-option ${task?.name === t.name ? "selected" : ""}`}
                  onClick={() => { setTask(t); setFieldValues({}); }}>
                  <span className="task-option-icon">{t.icon}</span>
                  <span className="task-option-body">
                    <span className="task-option-name">{t.name}</span>
                    <span className="task-option-desc">{t.description}</span>
                  </span>
                </button>
              ))}
            </div>
            <div className="form-actions">
              <button className="btn-ghost" onClick={() => { setTask(null); setStep(0); }}>← Back</button>
              <button className="btn-primary" disabled={!task} onClick={() => setStep(2)}>Next →</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="step-content">
            <p className="step-prompt">{task?.icon} <strong>{task?.name}</strong></p>
            <DynamicFields fields={task?.fields || []} values={fieldValues} onChange={handleFieldChange} />
            {!hasLeader && <p className="warn-text">⚠ No leader elected yet — task will queue</p>}
            <div className="form-actions">
              <button className="btn-ghost" onClick={() => setStep(1)}>← Back</button>
              <button className="btn-primary"
                disabled={submitting || !connected || !isDetailsValid()}
                onClick={handleSubmit}>
                {submitting ? "Sending..." : "Submit Task"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}