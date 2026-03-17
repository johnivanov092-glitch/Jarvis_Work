export default function SupervisorPanel({
  goal,
  setGoal,
  mode,
  setMode,
  autoApply,
  setAutoApply,
  runResult,
  historyItems,
  selectedHistoryId,
  onRun,
  onSelectHistory,
}) {
  const active = runResult;

  return (
    <div className="supervisor-panel">
      <div className="pane-title">Supervisor</div>

      <div className="supervisor-body">
        <label className="task-field">
          <span>Goal</span>
          <textarea
            className="patch-instruction"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            spellCheck={false}
          />
        </label>

        <label className="task-field">
          <span>Mode</span>
          <select
            className="pane-input"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="code">code</option>
            <option value="chat">chat</option>
            <option value="research">research</option>
            <option value="orchestrator">orchestrator</option>
            <option value="image">image</option>
          </select>
        </label>

        <label className="task-field checkbox-field">
          <input
            type="checkbox"
            checked={autoApply}
            onChange={(e) => setAutoApply(e.target.checked)}
          />
          <span>Auto apply hint</span>
        </label>

        <button className="soft-btn" onClick={onRun}>Run Supervisor</button>

        {active ? (
          <div className="supervisor-result">
            <div className="task-run-header">
              run #{active.run_id} • {active.mode}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Pipeline</div>
              {(active.steps || []).map((item, index) => (
                <div key={`${index}-${item.agent}`} className="task-run-row">
                  <div className="task-run-action">{item.agent}</div>
                  <div className="task-run-path">{item.status}</div>
                  <div className="task-run-reason">{item.details}</div>
                </div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Plan</div>
              {(active.plan || []).map((item, index) => (
                <div key={`${index}-${item.path}`} className="task-run-row">
                  <div className="task-run-action">{item.action}</div>
                  <div className="task-run-path">{item.path}</div>
                  <div className="task-run-reason">{item.reason}</div>
                </div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Next Steps</div>
              {(active.summary?.next_steps || []).map((item, index) => (
                <div key={`${index}-${item}`} className="task-run-log">• {item}</div>
              ))}
            </div>
          </div>
        ) : (
          <div className="pane-empty">Здесь появится supervisor execution pipeline.</div>
        )}

        <div className="supervisor-history">
          <div className="task-run-title">Supervisor History</div>
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
                  <div className="task-history-meta">{item.status} • {item.created_at}</div>
                </button>
              ))
            ) : (
              <div className="pane-empty">История supervisor пока пустая.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
