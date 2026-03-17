export default function StabilizationPreflightPanel({
  phase20Queue,
  phase20State,
  phase21Run,
  stagedPaths,
  result,
  onRun,
}) {
  const checks = result?.checks || [];
  const warnings = result?.warnings || [];
  const ready = !!result?.ready;

  return (
    <div className="phase21-panel">
      <div className="pane-title">Stabilization Preflight</div>

      <div className="phase21-body">
        <div className="phase20-meta">
          Queue: {phase20Queue?.items?.length || 0} • State: {phase20State ? "ready" : "empty"} • Controller: {phase21Run ? "ready" : "empty"} • Staged: {stagedPaths.length}
        </div>

        <div className="patch-buttons">
          <button className="soft-btn" onClick={onRun}>
            Run Preflight
          </button>
        </div>

        {result ? (
          <>
            <div className="task-run-section">
              <div className="task-run-title">Status</div>
              <div className="task-run-log">• {ready ? "READY" : "BLOCKED"}</div>
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Checks</div>
              {checks.map((item, index) => (
                <div key={`${index}-${item.name}`} className="task-run-row">
                  <div className="task-run-action">{item.name}</div>
                  <div className="task-run-path">{item.ok ? "ok" : "fail"}</div>
                  <div className="task-run-reason">{item.value}</div>
                </div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Warnings</div>
              {warnings.length ? warnings.map((item, index) => (
                <div key={`${index}-${item}`} className="task-run-log">• {item}</div>
              )) : <div className="task-run-log">• No warnings</div>}
            </div>
          </>
        ) : (
          <div className="pane-empty">Здесь появится preflight check перед apply/verify.</div>
        )}
      </div>
    </div>
  );
}
