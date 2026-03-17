export default function Phase19Panel({
  goal,
  setGoal,
  selectedPaths,
  runResult,
  historyItems,
  selectedHistoryId,
  onRun,
  onApplyPlanned,
  onVerifyPlanned,
  onSelectHistory,
}) {
  const active = runResult;
  const planItems = active?.plan || [];
  const fileOps = active?.file_operations || [];
  const verifyChecks = active?.verify?.checks || [];

  return (
    <div className="phase19-panel">
      <div className="pane-title">Phase 19 Multi-File Dev Loop</div>

      <div className="phase19-body">
        <label className="task-field">
          <span>Goal</span>
          <textarea
            className="patch-instruction"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            spellCheck={false}
          />
        </label>

        <div className="phase19-meta">
          Selected files: {selectedPaths.length}
        </div>

        <div className="patch-buttons">
          <button className="soft-btn" onClick={onRun}>
            Run Phase 19
          </button>
          <button className="soft-btn" onClick={onApplyPlanned} disabled={!planItems.length}>
            Apply Planned Staged
          </button>
          <button className="soft-btn" onClick={onVerifyPlanned} disabled={!planItems.length}>
            Verify Planned Staged
          </button>
        </div>

        {active ? (
          <div className="phase19-result">
            <div className="task-run-header">
              run #{active.run_id || active.id} • {active.mode}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Project Reasoning</div>
              <div className="task-run-log">
                Scope: {active.reasoning?.scope || "—"}
              </div>
              {(active.reasoning?.advice || []).map((item, index) => (
                <div key={`${index}-${item}`} className="task-run-log">• {item}</div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Plan</div>
              {planItems.map((item, index) => (
                <div key={`${index}-${item.path}`} className="task-run-row">
                  <div className="task-run-action">{item.action}</div>
                  <div className="task-run-path">{item.path}</div>
                  <div className="task-run-reason">{item.reason}</div>
                </div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">File Operations</div>
              {fileOps.map((item, index) => (
                <div key={`${index}-${item.path}`} className="task-run-row">
                  <div className="task-run-action">{item.operation}</div>
                  <div className="task-run-path">{item.path}</div>
                  <div className="task-run-reason">{item.status}</div>
                </div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Verify</div>
              {verifyChecks.map((item, index) => (
                <div key={`${index}-${item}`} className="task-run-log">• {item}</div>
              ))}
            </div>
          </div>
        ) : (
          <div className="pane-empty">Здесь появится multi-file reasoning и plan.</div>
        )}

        <div className="phase19-history">
          <div className="task-run-title">Phase 19 History</div>
          <div className="task-history-list">
            {historyItems.length ? (
              historyItems.map((item) => (
                <button
                  key={item.id}
                  className={`task-history-row ${selectedHistoryId === item.id ? "active" : ""}`}
                  onClick={() => onSelectHistory(item)}
                >
                  <div className="task-history-top">
                    <span className="task-history-id">#{item.id}</span>
                    <span className="task-history-mode">{item.mode}</span>
                  </div>
                  <div className="task-history-goal">{item.goal}</div>
                  <div className="task-history-meta">{item.created_at}</div>
                </button>
              ))
            ) : (
              <div className="pane-empty">История Phase 19 пока пустая.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
