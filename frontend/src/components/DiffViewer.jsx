export default function DiffViewer({
  original,
  updated,
  loading,
}) {
  return (
    <div className="diff-viewer">
      <div className="pane-title">Diff Preview</div>

      {loading ? <div className="pane-empty">Подготовка preview...</div> : null}

      {!loading && !updated ? (
        <div className="pane-empty">
          Здесь появится предложенное изменение после Preview Patch.
        </div>
      ) : null}

      {!loading && updated ? (
        <div className="diff-grid">
          <div className="diff-col">
            <div className="diff-col-title">Current</div>
            <pre className="diff-code">{original}</pre>
          </div>
          <div className="diff-col">
            <div className="diff-col-title">Proposed</div>
            <pre className="diff-code">{updated}</pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}
