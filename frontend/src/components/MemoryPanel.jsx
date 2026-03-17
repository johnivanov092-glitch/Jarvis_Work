export default function MemoryPanel({
  items,
  onDelete,
}) {
  return (
    <div className="memory-panel">
      <div className="memory-panel-title">Память</div>

      {items.length ? (
        items.map((item) => (
          <div key={item.id} className="memory-card">
            <div className="memory-card-top">
              <div className="memory-card-title">
                {item.title || item.content.slice(0, 56)}
              </div>
              <button className="mini-icon" onClick={() => onDelete(item.id)} title="Удалить из памяти">
                ✕
              </button>
            </div>
            <div className="memory-card-text">{item.content}</div>
            <div className="memory-card-meta">
              {item.pinned ? "Закреплено" : "Сохранено"} • {item.source || "chat"}
            </div>
          </div>
        ))
      ) : (
        <div className="empty-hint">Память пока пустая.</div>
      )}
    </div>
  );
}
