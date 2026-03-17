
export default function SupervisorAutoApplyPanel({
  path,
  previewContent,
  onApply
}) {
  if (!path) {
    return (
      <div className="supervisor-auto">
        <div className="pane-title">Auto Apply</div>
        <div className="pane-empty">Выбери файл для auto apply.</div>
      </div>
    );
  }

  return (
    <div className="supervisor-auto">
      <div className="pane-title">Auto Apply</div>

      <div className="auto-body">
        <div className="auto-path">{path}</div>

        <button
          className="soft-btn"
          onClick={() => onApply(path, previewContent)}
        >
          Apply Preview To Disk
        </button>
      </div>
    </div>
  );
}
