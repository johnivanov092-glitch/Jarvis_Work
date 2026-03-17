export default function TaskHistoryPanel({
  items,
  selectedId,
  onSelect,
}) {
  return (
    <div className="task-history-panel">
      <div className="pane-title">Task History</div>

      <div className="task-history-list">
        {items.length ? (
          items.map((item) => (
            <button
              key={item.id}
              className={`task-history-row ${selectedId === item.id ? "active" : ""}`}
              onClick={() => onSelect(item)}
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
          <div className="pane-empty">История задач пока пустая.</div>
        )}
      </div>
    </div>
  );
}
