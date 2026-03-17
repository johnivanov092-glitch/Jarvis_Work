import { useMemo, useState } from "react";

export default function FileExplorer({
  files,
  selectedPath,
  onSelect,
}) {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return files;
    return files.filter((item) => item.path.toLowerCase().includes(q));
  }, [files, filter]);

  return (
    <div className="file-explorer">
      <div className="pane-title">Файлы проекта</div>

      <div className="pane-toolbar">
        <input
          className="pane-input"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Фильтр файлов..."
        />
      </div>

      <div className="file-list">
        {filtered.length ? (
          filtered.map((file) => (
            <button
              key={file.path}
              className={`file-row ${selectedPath === file.path ? "active" : ""}`}
              onClick={() => onSelect(file)}
              title={file.path}
            >
              <div className="file-row-name">{file.name || file.path.split("/").pop()}</div>
              <div className="file-row-path">{file.path}</div>
            </button>
          ))
        ) : (
          <div className="pane-empty">Нет файлов по фильтру.</div>
        )}
      </div>
    </div>
  );
}
