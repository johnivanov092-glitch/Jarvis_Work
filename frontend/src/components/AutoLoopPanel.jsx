
export default function AutoLoopPanel({
  path,
  goal,
  content,
  onRun,
  result
}) {
  return (
    <div className="autoloop-panel">
      <div className="pane-title">Autonomous Dev Loop</div>

      <div className="auto-body">
        <div className="auto-row">
          <b>Goal:</b> {goal || "—"}
        </div>

        <div className="auto-row">
          <b>File:</b> {path || "—"}
        </div>

        <button
          className="soft-btn"
          onClick={() => onRun(goal, path, content)}
        >
          Run Dev Loop
        </button>

        {result && (
          <div className="auto-result">
            <div className="auto-title">Pipeline</div>

            {result.steps.map((s, i) => (
              <div key={i} className="auto-step">
                {s.step} — {s.status}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
