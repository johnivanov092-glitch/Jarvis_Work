export default function Phase21Panel({
  goal,
  setGoal,
  previewQueue,
  executionState,
  runResult,
  historyItems,
  selectedHistoryId,
  onRun,
  onApplyController,
  onVerifyController,
  onSelectHistory,
}) {
  const queueItems = previewQueue?.items || runResult?.queue_items || [];
  const controllerSteps = runResult?.controller?.steps || [];
  const controllerNotes = runResult?.controller?.notes || [];

  return (
    <div className="phase21-panel">
      <div className="pane-title">Phase 21 Autonomous Execution Controller</div>

      <div className="phase21-body">
        <label className="task-field">
          <span>Goal</span>
          <textarea
            className="patch-instruction"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            spellCheck={false}
          />
        </label>

        <div className="phase20-meta">
          Queue: {queueItems.length} • State: {executionState ? "ready" : "empty"}
        </div>

        <div className="patch-buttons">
          <button className="soft-btn" onClick={onRun} disabled={!queueItems.length}>
            Run Phase 21
          </button>
          <button className="soft-btn" onClick={onApplyController} disabled={!queueItems.length}>
            Controller Apply
          </button>
          <button className="soft-btn" onClick={onVerifyController} disabled={!queueItems.length}>
            Controller Verify
          </button>
        </div>

        {runResult ? (
          <div className="phase20-result">
            <div className="task-run-header">
              run #{runResult.run_id || runResult.id}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Controller Steps</div>
              {controllerSteps.map((item, index) => (
                <div key={`${index}-${item.step}`} className="task-run-row">
                  <div className="task-run-action">{item.step}</div>
                  <div className="task-run-path">{item.status}</div>
                  <div className="task-run-reason">controller</div>
                </div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Notes</div>
              {controllerNotes.map((item, index) => (
                <div key={`${index}-${item}`} className="task-run-log">• {item}</div>
              ))}
            </div>
          </div>
        ) : (
          <div className="pane-empty">Здесь появится autonomous execution controller.</div>
        )}

        <div className="phase20-history">
          <div className="task-run-title">Phase 21 History</div>
          <div className="task-history-list">
            {historyItems.length ? historyItems.map((item) => (
              <button
                key={item.id}
                className={`task-history-row ${selectedHistoryId === item.id ? "active" : ""}`}
                onClick={() => onSelectHistory(item)}
              >
                <div className="task-history-top">
                  <span className="task-history-id">#{item.id}</span>
                </div>
                <div className="task-history-goal">{item.goal}</div>
                <div className="task-history-meta">{item.created_at}</div>
              </button>
            )) : <div className="pane-empty">История Phase 21 пока пустая.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
