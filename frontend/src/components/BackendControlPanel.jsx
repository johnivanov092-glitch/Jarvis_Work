import { useEffect, useState } from "react";
import {
  tauriStartBackend,
  tauriStopBackend,
  tauriBackendStatus,
  getDesktopLifecycleConfig,
} from "../api/desktop_lifecycle";

export default function BackendControlPanel() {
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [backend, cfg] = await Promise.all([
        tauriBackendStatus().catch(() => ({ running: false, pid: null, mode: "unknown" })),
        getDesktopLifecycleConfig().catch(() => null),
      ]);
      setStatus(backend);
      setConfig(cfg);
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

  async function handleStart() {
    try {
      await tauriStartBackend();
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleStop() {
    try {
      await tauriStopBackend();
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <section className="workspace-card">
      <div className="section-header">
        <h2>Backend Lifecycle</h2>
        <div className="actions-row">
          <button onClick={handleStart}>Start Backend</button>
          <button className="danger" onClick={handleStop}>Stop Backend</button>
          <button onClick={refresh}>Refresh</button>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card"><span>Running</span><strong>{String(status?.running ?? false)}</strong></div>
        <div className="stat-card"><span>PID</span><strong>{status?.pid ?? "-"}</strong></div>
        <div className="stat-card"><span>Mode</span><strong>{status?.mode ?? "tauri"}</strong></div>
      </div>

      {config ? (
        <div className="json-block">
          <h3>Desktop Launch Config</h3>
          <pre>{JSON.stringify(config, null, 2)}</pre>
        </div>
      ) : null}

      {error ? <div className="panel-error">{error}</div> : null}
    </section>
  );
}
