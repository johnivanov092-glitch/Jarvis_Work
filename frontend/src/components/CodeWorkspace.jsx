export default function CodeWorkspace() {
  return (
    <div className="code-workspace">
      <div className="code-column files">
        <div className="pane-title">Файлы</div>
        <div className="pane-body">
          Здесь будет File Explorer из IDE режима.
        </div>
      </div>

      <div className="code-column editor">
        <div className="pane-title">Редактор</div>
        <div className="pane-body code-placeholder">
{`// Phase 17.2
// Code tab закреплён внутри общего chat-first shell.
// Следующий шаг: подключить project_brain snapshot/file и diff preview.`}
        </div>
      </div>

      <div className="code-column terminal">
        <div className="pane-title">Терминал</div>
        <div className="pane-body">
          Execution / Patch / Verify будут подключены следующим патчем.
        </div>
      </div>
    </div>
  );
}
