export default function Phase20Panel({
  goal,
  setGoal,
  selectedPaths,
  runResult,
  historyItems,
  selectedHistoryId,
  previewQueue,
  executionState,
  onRun,
  onBuildPreviewQueue,
  onBuildExecutionState,
  onPreviewExecution,
  onAutoStageExecution,
  onApplyExecution,
  onVerifyExecution,
  onSelectHistory,
}) {
  const active = runResult;
  const plannerItems = active?.planner?.items || [];
  const previewTargets = active?.execution?.preview_targets || [];
  const queueItems = previewQueue?.items || [];
  const checkpoints = executionState?.checkpoints || [];
  const rollbackAdvice = executionState?.rollback?.advice || [];

  return (
    <div className="phase20-panel">
      <div className="pane-title">Phase 20 Autonomous Project Agent</div>

      <div className="phase20-body">
        <label className="task-field">
          <span>Goal</span>
          <textarea
            className="patch-instruction"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            spellCheck={false}
          />
        </label>

        <div className="phase20-meta">Selected files: {selectedPaths.length}</div>

        <div className="patch-buttons">
          <button className="soft-btn" onClick={onRun}>Run Phase 20</button>
          <button className="soft-btn" onClick={onBuildPreviewQueue} disabled={!previewTargets.length}>Build Preview Queue</button>
          <button className="soft-btn" onClick={onBuildExecutionState} disabled={!queueItems.length}>Build Execution State</button>
          <button className="soft-btn" onClick={onPreviewExecution} disabled={!previewTargets.length}>Preview Next</button>
          <button className="soft-btn" onClick={onAutoStageExecution} disabled={!previewTargets.length}>Stage Execution Files</button>
          <button className="soft-btn" onClick={onApplyExecution} disabled={!previewTargets.length}>Apply Execution</button>
          <button className="soft-btn" onClick={onVerifyExecution} disabled={!previewTargets.length}>Verify Execution</button>
        </div>

        {previewQueue ? (
          <div className="task-run-section">
            <div className="task-run-title">Preview Queue</div>
            {queueItems.map((item) => (
              <div key={`${item.order}-${item.path}`} className="task-run-row">
                <div className="task-run-action">{item.order}</div>
                <div className="task-run-path">{item.path}</div>
                <div className="task-run-reason">{item.status}</div>
              </div>
            ))}
          </div>
        ) : null}

        {executionState ? (
          <>
            <div className="task-run-section">
              <div className="task-run-title">Execution Checkpoints</div>
              {checkpoints.map((item, index) => (
                <div key={`${index}-${item.step}`} className="task-run-row">
                  <div className="task-run-action">{item.step}</div>
                  <div className="task-run-path">{item.status}</div>
                  <div className="task-run-reason">checkpoint</div>
                </div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Rollback Strategy</div>
              {rollbackAdvice.map((item, index) => (
                <div key={`${index}-${item}`} className="task-run-log">• {item}</div>
              ))}
            </div>
          </>
        ) : null}

        {active ? (
          <div className="phase20-result">
            <div className="task-run-header">run #{active.run_id || active.id}</div>
            <div className="task-run-section">
              <div className="task-run-title">Planner</div>
              {plannerItems.map((item, index) => (
                <div key={`${index}-${item.path}`} className="task-run-row">
                  <div className="task-run-action">{item.action}</div>
                  <div className="task-run-path">{item.path}</div>
                  <div className="task-run-reason">{item.reason}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="pane-empty">Здесь появится multi-agent reasoning по проекту.</div>
        )}

        <div className="phase20-history">
          <div className="task-run-title">Phase 20 History</div>
          <div className="task-history-list">
            {historyItems.length ? historyItems.map((item) => (
              <button
                key={item.id}
                className={`task-history-row ${selectedHistoryId === item.id ? "active" : ""}`}
                onClick={() => onSelectHistory(item)}
              >
                <div className="task-history-top"><span className="task-history-id">#{item.id}</span></div>
                <div className="task-history-goal">{item.goal}</div>
                <div className="task-history-meta">{item.created_at}</div>
              </button>
            )) : <div className="pane-empty">История Phase 20 пока пустая.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
