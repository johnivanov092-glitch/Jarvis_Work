import { useEffect, useState } from "react";
import { getAutoDevStatus, runAutoDev } from "../api/autodev";

export default function AutonomousDevPanel() {
  const [goal, setGoal] = useState("");
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [autoApply, setAutoApply] = useState(false);
  const [runChecks, setRunChecks] = useState(false);
  const [commitChanges, setCommitChanges] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const data = await getAutoDevStatus();
      setStatus(data);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleRun() {
    if (!goal.trim()) return;
    try {
      const data = await runAutoDev(goal.trim(), {
        auto_apply: autoApply,
        run_checks: runChecks,
        commit_changes: commitChanges,
      });
      setResult(data);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <section className="workspace-card">
      <div className="section-header">
        <h2>Autonomous Dev Engine</h2>
        <button onClick={refresh}>Refresh</button>
      </div>

      <div className="goal-box">
        <input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Например: Улучши patch pipeline и добавь rollback verification"
        />
        <button onClick={handleRun}>Run Engine</button>
      </div>

      <div className="actions-row" style={{ justifyContent: "flex-start", marginBottom: 12 }}>
        <label><input type="checkbox" checked={autoApply} onChange={(e) => setAutoApply(e.target.checked)} /> auto apply</label>
        <label><input type="checkbox" checked={runChecks} onChange={(e) => setRunChecks(e.target.checked)} /> run checks</label>
        <label><input type="checkbox" checked={commitChanges} onChange={(e) => setCommitChanges(e.target.checked)} /> commit git</label>
      </div>

      {status ? (
        <div className="json-block">
          <h3>Engine Status</h3>
          <pre>{JSON.stringify(status, null, 2)}</pre>
        </div>
      ) : null}

      {result ? (
        <div className="json-block">
          <h3>Last Engine Run</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      ) : null}

      {error ? <div className="panel-error">{error}</div> : null}
    </section>
  );
}
