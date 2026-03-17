import { useMemo, useState } from "react";
import { FileCode2, RefreshCw, Search } from "lucide-react";

function scoreFile(path, normalizedQuery) {
  if (!normalizedQuery) {
    return 0;
  }

  const lowerPath = path.toLowerCase();
  if (lowerPath === normalizedQuery) {
    return 100;
  }
  if (lowerPath.endsWith(`/${normalizedQuery}`)) {
    return 90;
  }
  if (lowerPath.includes(normalizedQuery)) {
    return 70;
  }
  return 0;
}

export default function FileExplorerPanel({
  files = [],
  selectedPath = "",
  loading = false,
  onRefresh,
  onOpen,
}) {
  const [query, setQuery] = useState("");

  const filteredFiles = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return files.slice(0, 500);
    }

    return [...files]
      .filter((file) => file.path.toLowerCase().includes(normalized))
      .sort((a, b) => scoreFile(b.path, normalized) - scoreFile(a.path, normalized))
      .slice(0, 500);
  }, [files, query]);

  return (
    <section className="panel explorer-panel">
      <div className="panel-header">
        <div className="panel-title">
          <FileCode2 size={16} />
          <span>Files</span>
          <span className="panel-count">{files.length}</span>
        </div>

        <button
          type="button"
          className="icon-button"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh snapshot"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      <div className="panel-search">
        <Search size={14} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter files..."
        />
      </div>

      <div className="file-list">
        {filteredFiles.length === 0 ? (
          <div className="empty-state">No files</div>
        ) : (
          filteredFiles.map((file) => {
            const active = file.path === selectedPath;

            return (
              <button
                key={file.path}
                type="button"
                className={`file-item ${active ? "active" : ""}`}
                onClick={() => onOpen?.(file)}
                title={file.path}
              >
                <FileCode2 size={14} />
                <span className="file-path">{file.path}</span>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
}
