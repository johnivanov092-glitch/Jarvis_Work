import { Bot, Clock3, RotateCcw, ShieldCheck, TriangleAlert, Wrench } from "lucide-react";

function formatTimestamp(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  if (typeof value === "number") {
    const ms = value > 10_000_000_000 ? value : value * 1000;
    try {
      return new Date(ms).toLocaleTimeString();
    } catch {
      return String(value);
    }
  }

  const asNumber = Number(value);
  if (!Number.isNaN(asNumber) && String(value).trim() !== "") {
    const ms = asNumber > 10_000_000_000 ? asNumber : asNumber * 1000;
    try {
      return new Date(ms).toLocaleTimeString();
    } catch {
      return String(value);
    }
  }

  try {
    return new Date(value).toLocaleTimeString();
  } catch {
    return String(value);
  }
}

function formatEventLine(event) {
  if (!event) {
    return "";
  }

  const timestamp = formatTimestamp(event.timestamp || event.created_at || event.time || event.ts);
  const label =
    event.message ||
    event.title ||
    event.event ||
    event.type ||
    event.name ||
    event.status ||
    JSON.stringify(event);

  return [timestamp, label].filter(Boolean).join("  ");
}

function executionLabel(item) {
  if (!item) {
    return "unknown";
  }

  return item.goal || item.title || item.mode || item.execution_id || item.id || "execution";
}

function renderList(items = []) {
  if (!items.length) {
    return <div className="agent-list-empty">—</div>;
  }

  return (
    <ul className="agent-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

export default function TerminalPanel({
  executions = [],
  activeExecutionId = "",
  events = [],
  backups = [],
  agentPlan = null,
  agentResult = null,
  onSelectExecution,
  onRollback,
  onVerify,
  verifying = false,
  rollingBack = false,
}) {
  return (
    <section className="panel terminal-panel">
      <div className="terminal-grid terminal-grid-phase16">
        <div className="terminal-column">
          <div className="panel-header">
            <div className="panel-title">
              <Clock3 size={16} />
              <span>Execution timeline</span>
            </div>
          </div>

          <div className="execution-list">
            {executions.length === 0 ? (
              <div className="empty-state">No executions yet</div>
            ) : (
              executions.map((item, index) => {
                const id = item.execution_id || item.id || item.run_id || `execution-${index}`;
                const active = id === activeExecutionId;

                return (
                  <button
                    key={id}
                    type="button"
                    className={`execution-item ${active ? "active" : ""}`}
                    onClick={() => onSelectExecution?.(id)}
                  >
                    <div className="execution-main">{executionLabel(item)}</div>
                    <div className="execution-meta">
                      {item.status || item.state || item.mode || "unknown"}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div className="terminal-column">
          <div className="panel-header">
            <div className="panel-title">
              <Wrench size={16} />
              <span>Events</span>
            </div>

            <button
              type="button"
              className="action-button ghost"
              onClick={onVerify}
              disabled={verifying}
            >
              <ShieldCheck size={15} />
              <span>{verifying ? "Verifying..." : "Verify"}</span>
            </button>
          </div>

          <pre className="terminal-output">
            {events.length ? events.map(formatEventLine).join("\n") : "[jarvis] no execution events"}
          </pre>
        </div>

        <div className="terminal-column">
          <div className="panel-header">
            <div className="panel-title">
              <Bot size={16} />
              <span>Local agent</span>
            </div>
          </div>

          <div className="agent-section">
            <div className="agent-card">
              <div className="agent-card-title">Plan</div>
              <div className="agent-card-copy">{agentPlan?.summary || "No plan yet"}</div>
              {renderList(agentPlan?.steps || [])}
            </div>

            <div className="agent-card">
              <div className="agent-card-title">Patch result</div>
              <div className="agent-card-copy">{agentResult?.summary || "No patch suggestion yet"}</div>
              {renderList(agentResult?.changes || [])}
            </div>

            <div className="agent-card warning">
              <div className="agent-card-title warning-line">
                <TriangleAlert size={14} />
                <span>Warnings</span>
              </div>
              {renderList([...(agentPlan?.risks || []), ...(agentResult?.warnings || [])])}
            </div>
          </div>
        </div>

        <div className="terminal-column">
          <div className="panel-header">
            <div className="panel-title">
              <RotateCcw size={16} />
              <span>Rollback backups</span>
            </div>
          </div>

          <div className="backup-list">
            {backups.length === 0 ? (
              <div className="empty-state">No backups</div>
            ) : (
              backups.map((item, index) => {
                const id = item.backup_id || item.id || `backup-${index}`;
                const filePath = item.file_path || item.path || "unknown file";

                return (
                  <div key={id} className="backup-item">
                    <div className="backup-text">
                      <div className="backup-path">{filePath}</div>
                      <div className="backup-meta">{id}</div>
                    </div>

                    <button
                      type="button"
                      className="action-button ghost"
                      onClick={() => onRollback?.(id)}
                      disabled={rollingBack}
                    >
                      Rollback
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
