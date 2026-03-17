export default function TerminalPanel({
  logs,
}) {
  return (
    <div className="terminal-panel">
      <div className="pane-title">Терминал / События</div>
      <div className="terminal-log">
        {logs.length ? (
          logs.map((line, index) => (
            <div key={`${index}-${line}`} className="terminal-line">
              {line}
            </div>
          ))
        ) : (
          <div className="pane-empty">Пока нет событий.</div>
        )}
      </div>
    </div>
  );
}
