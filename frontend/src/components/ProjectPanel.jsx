import { useEffect, useState } from "react";
import { api } from "../api/ide";

export default function ProjectPanel() {
  const [project, setProject] = useState(null);
  const [tree, setTree] = useState([]);
  const [pathInput, setPathInput] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState("");
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getAdvancedProjectInfo()
      .then((data) => {
        if (!data?.ok) return;
        setProject(data);
        return loadTree();
      })
      .catch((e) => {
        setError(`Не удалось загрузить проект: ${e.message || ""}`);
      });
  }, []);

  async function openProject() {
    const path = pathInput.trim();
    if (!path) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.openAdvancedProject(path);
      if (data?.ok) {
        setProject(data);
        await loadTree();
      }
    } catch (e) {
      setError(`Не удалось открыть проект: ${e.message || ""}`);
    } finally {
      setLoading(false);
    }
  }

  async function loadTree() {
    try {
      const data = await api.getAdvancedProjectTree({ maxDepth: 3, maxItems: 300 });
      if (data?.ok) setTree(data.items || []);
    } catch (e) {
      setError(`Не удалось загрузить дерево файлов: ${e.message || ""}`);
    }
  }

  async function readFile(path) {
    setSelectedFile(path);
    setError("");
    try {
      const data = await api.readAdvancedProjectFile(path);
      if (data?.ok) {
        setFileContent(data.content || "");
      } else {
        setFileContent(`Ошибка: ${data?.error || "неизвестно"}`);
      }
    } catch (e) {
      const message = e.message || "Ошибка чтения";
      setError(message);
      setFileContent(`Ошибка: ${message}`);
    }
  }

  async function handleSearch() {
    if (!search.trim()) return;
    setError("");
    try {
      const data = await api.searchAdvancedProject(search);
      setSearchResults(data.items || []);
    } catch (e) {
      setError(`Не удалось выполнить поиск: ${e.message || ""}`);
    }
  }

  async function closeProject() {
    try {
      await api.closeAdvancedProject();
      setProject(null);
      setTree([]);
      setSelectedFile(null);
      setFileContent("");
      setSearchResults([]);
      setError("");
    } catch (e) {
      setError(`Не удалось закрыть проект: ${e.message || ""}`);
    }
  }

  const dirs = tree.filter((item) => item.type === "dir");
  const files = tree.filter((item) => item.type === "file");
  const iconFor = (ext) => {
    if ([".py", ".js", ".jsx", ".ts", ".tsx"].includes(ext)) return "●";
    if ([".css", ".html", ".yml", ".json"].includes(ext)) return "◆";
    if ([".md", ".txt"].includes(ext)) return "📄";
    return "○";
  };

  if (!project) {
    return (
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>📂 Открыть проект</div>
        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Укажи путь к папке проекта</div>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && openProject()}
            placeholder="D:\\MyProject или /home/user/project"
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: "var(--bg-input)",
              color: "var(--text-primary)",
              fontSize: 12,
              outline: "none",
            }}
          />
          <button
            onClick={openProject}
            disabled={loading}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: "1px solid var(--accent)",
              background: "var(--accent-dim)",
              color: "var(--accent)",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            {loading ? "..." : "Открыть"}
          </button>
        </div>
        {error && <div style={{ fontSize: 11, color: "#ff6b6b" }}>{error}</div>}
        <div style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.5 }}>
          Elira получит доступ к файлам проекта, сможет анализировать код, искать по содержимому и
          предлагать изменения.
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 13 }}>📂</span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 500,
            color: "var(--text-primary)",
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {project.name || project.path}
        </span>
        <button
          onClick={closeProject}
          style={{ border: "none", background: "transparent", color: "var(--text-muted)", cursor: "pointer", fontSize: 11 }}
        >
          ✕ Закрыть
        </button>
      </div>

      <div style={{ display: "flex", gap: 4, padding: "6px 12px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Поиск по проекту..."
          style={{
            flex: 1,
            padding: "4px 8px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: "var(--bg-input)",
            color: "var(--text-primary)",
            fontSize: 11,
            outline: "none",
          }}
        />
        <button
          onClick={handleSearch}
          style={{
            padding: "4px 8px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: "var(--bg-surface)",
            color: "var(--text-muted)",
            cursor: "pointer",
            fontSize: 11,
          }}
        >
          🔍
        </button>
      </div>

      {error && (
        <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)", fontSize: 11, color: "#ff6b6b" }}>
          {error}
        </div>
      )}

      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "220px 1fr", minHeight: 0 }}>
        <div style={{ borderRight: "1px solid var(--border)", overflow: "auto", padding: "4px 0" }}>
          {searchResults.length > 0 ? (
            <div>
              <div style={{ padding: "4px 12px", fontSize: 10, color: "var(--text-muted)" }}>
                Результаты: {searchResults.length}
              </div>
              {searchResults.map((result) => (
                <button key={`${result.path}:${result.line}`} onClick={() => readFile(result.path)} style={treeItem(selectedFile === result.path)}>
                  <span style={{ fontSize: 10 }}>📌</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 11 }}>
                      {result.path}
                    </div>
                    <div style={{ fontSize: 9, color: "var(--text-muted)" }}>L{result.line}: {result.text?.slice(0, 60)}</div>
                  </div>
                </button>
              ))}
              <button onClick={() => setSearchResults([])} style={{ ...treeItem(false), color: "var(--text-muted)", fontStyle: "italic" }}>
                ← Назад к дереву
              </button>
            </div>
          ) : (
            <>
              <div style={{ padding: "4px 12px", fontSize: 10, color: "var(--text-muted)" }}>
                {files.length} файлов, {dirs.length} папок
              </div>
              {tree.map((item) => (
                <button
                  key={item.path}
                  onClick={() => item.type === "file" && readFile(item.path)}
                  style={treeItem(selectedFile === item.path)}
                  disabled={item.type === "dir"}
                >
                  <span style={{ fontSize: 10, opacity: 0.6 }}>{item.type === "dir" ? "📁" : iconFor(item.ext)}</span>
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      fontSize: 11,
                      color: item.type === "dir" ? "var(--text-muted)" : "var(--text-primary)",
                      paddingLeft: item.path.split("/").length > 1 ? (item.path.split("/").length - 1) * 8 : 0,
                    }}
                  >
                    {item.name}
                  </span>
                </button>
              ))}
            </>
          )}
        </div>

        <div style={{ overflow: "auto" }}>
          {selectedFile ? (
            <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
              <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)", fontSize: 11, color: "var(--text-muted)", flexShrink: 0 }}>
                {selectedFile}
              </div>
              <pre
                style={{
                  flex: 1,
                  margin: 0,
                  padding: 12,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  lineHeight: 1.5,
                  color: "var(--text-primary)",
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {fileContent}
              </pre>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-muted)", fontSize: 12 }}>
              Выбери файл слева
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const treeItem = (active) => ({
  display: "flex",
  alignItems: "center",
  gap: 6,
  width: "100%",
  padding: "3px 12px",
  border: "none",
  cursor: "pointer",
  textAlign: "left",
  background: active ? "var(--bg-surface-active)" : "transparent",
  color: "var(--text-primary)",
  fontSize: 11,
});
