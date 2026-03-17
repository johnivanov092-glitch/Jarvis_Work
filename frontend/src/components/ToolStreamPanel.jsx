import { useEffect, useState } from "react";
import { Activity, Bot, Wrench, RefreshCw } from "lucide-react";
import { getRunHistory, getSupervisorStatus, getPhase12Executions } from "../api/ide";

export default function ToolStreamPanel() {
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [runs, executions, supervisor] = await Promise.all([
        getRunHistory(10).catch(() => []),
        getPhase12Executions(10).catch(() => []),
        getSupervisorStatus().catch(() => null),
      ]);

      const merged = [
        ...runs.map((r) => ({
          id: r.id,
          type: "run",
          title: r.goal,
          status: r.status,
          source: r.source || "run-history",
        })),
        ...executions.map((e) => ({
          id: e.id,
          type: "execution",
          title: e.goal,
          status: e.status,
          source: e.source || "phase12",
        })),
      ].slice(0, 20);

      setItems(merged);
      setMeta(supervisor);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <section className="ide-panel ide-tool-stream">
      <div className="ide-panel-header">
        <div>
          <h3><Activity size={16} /> Tool Stream</h3>
          <p>Live agent activity</p>
        </div>
        <button className="ide-ghost-button" onClick={refresh}><RefreshCw size={14} /></button>
      </div>

      {meta ? (
        <div className="ide-mini-stats">
          <div><Bot size={14} /> {meta.agents_count ?? 0} agents</div>
          <div><Wrench size={14} /> {meta.runs_count ?? 0} runs</div>
        </div>
      ) : null}

      <div className="ide-stream-list">
        {items.map((item) => (
          <div key={`${item.type}-${item.id}`} className="ide-stream-item">
            <div className={`ide-stream-dot ${item.status || "idle"}`} />
            <div className="ide-stream-content">
              <div className="ide-stream-title">{item.title}</div>
              <div className="ide-stream-meta">{item.type} · {item.source} · {item.status}</div>
            </div>
          </div>
        ))}
      </div>

      {error ? <div className="ide-error">{error}</div> : null}
    </section>
  );
}
