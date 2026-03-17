export default function CodeEditor({
  filePath,
  value,
  onChange,
}) {
  const lineCount = Math.max(1, value.split("\n").length);
  const lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1).join("\n");

  return (
    <div className="code-editor-shell">
      <div className="pane-title">Редактор</div>
      <div className="editor-subtitle">{filePath || "Файл не выбран"}</div>

      <div className="editor-wrap">
        <pre className="editor-lines">{lineNumbers}</pre>
        <textarea
          className="editor-textarea"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          placeholder="Открой файл слева"
        />
      </div>
    </div>
  );
}
