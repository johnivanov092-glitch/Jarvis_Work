export default function TaskRunnerPanel({
  goal,
  setGoal,
  mode,
  setMode,
  taskRun,
  taskHistoryItem,
  onRunTask,
}) {
  const active = taskHistoryItem?.result || taskRun;

  return (
    <div className="task-runner-panel">
      <div className="pane-title">Task Runner</div>

      <div className="task-runner-body">
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

        <button className="soft-btn" onClick={onRunTask}>Run Task</button>

        {active ? (
          <div className="task-run-result">
            <div className="task-run-header">
              {active.mode} • {active.started_at || taskHistoryItem?.created_at}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Supervisor Pipeline</div>
              {(active.pipeline || []).map((item, index) => (
                <div key={`${index}-${item.agent}`} className="task-run-row">
                  <div className="task-run-action">{item.agent}</div>
                  <div className="task-run-path">{item.status}</div>
                  <div className="task-run-reason">{item.description}</div>
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
              <div className="task-run-title">Logs</div>
              {((taskHistoryItem?.logs) || active.logs || []).map((line, index) => (
                <div key={`${index}-${line}`} className="task-run-log">{line}</div>
              ))}
            </div>

            <div className="task-run-section">
              <div className="task-run-title">Next Steps</div>
              {(active.next_steps || []).map((line, index) => (
                <div key={`${index}-${line}`} className="task-run-log">• {line}</div>
              ))}
            </div>
          </div>
        ) : (
          <div className="pane-empty">Здесь появится результат запуска задачи.</div>
        )}
      </div>
    </div>
  );
}
