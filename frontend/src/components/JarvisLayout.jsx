import { useEffect, useMemo, useState } from "react";
import { api } from "../api/ide";

function formatBytes(value) {
  if (!Number.isFinite(value)) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function detectLanguage(path = "") {
  const lower = path.toLowerCase();

  if (lower.endsWith(".py")) return "python";
  if (lower.endsWith(".js") || lower.endsWith(".jsx")) return "javascript";
  if (lower.endsWith(".ts") || lower.endsWith(".tsx")) return "typescript";
  if (lower.endsWith(".json")) return "json";
  if (lower.endsWith(".css")) return "css";
  if (lower.endsWith(".html")) return "html";
  if (lower.endsWith(".rs")) return "rust";
  if (lower.endsWith(".md")) return "markdown";
  if (lower.endsWith(".yml") || lower.endsWith(".yaml")) return "yaml";
  return "text";
}

function buildLineNumbers(text) {
  const count = Math.max(1, text.split("\n").length);
  return Array.from({ length: count }, (_, i) => i + 1).join("\n");
}

export default function JarvisLayout() {
  const [files, setFiles] = useState([]);
  const [filesCount, setFilesCount] = useState(0);
  const [selectedPath, setSelectedPath] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [editorValue, setEditorValue] = useState("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [sidebarError, setSidebarError] = useState("");
  const [editorError, setEditorError] = useState("");
  const [activity, setActivity] = useState([]);
  const [planBusy, setPlanBusy] = useState(false);
  const [runBusy, setRunBusy] = useState(false);
  const [goal, setGoal] = useState("Open selected file and prepare safe Phase 15 patch preview.");
  const [agentResult, setAgentResult] = useState(null);
  const [ollamaStatus, setOllamaStatus] = useState(null);

  useEffect(() => {
    loadSnapshot();
    loadOllamaStatus();
  }, []);

  async function loadSnapshot() {
    setBusy(true);
    setSidebarError("");
    try {
      const data = await api.getProjectSnapshot();
      setFiles(data.files || []);
      setFilesCount(data.files_count || 0);
      pushActivity("snapshot", `Loaded project snapshot: ${data.files_count || 0} files`);
    } catch (error) {
      setSidebarError(error.message || "Не удалось загрузить дерево проекта");
      pushActivity("error", `Snapshot error: ${error.message || "unknown error"}`);
    } finally {
      setBusy(false);
    }
  }

  async function loadOllamaStatus() {
    try {
      const data = await api.getOllamaStatus();
      setOllamaStatus(data);
    } catch {
      setOllamaStatus(null);
    }
  }

  async function openFile(path) {
    setSelectedPath(path);
    setEditorError("");
    setSelectedFile(null);
    setAgentResult(null);

    try {
      const data = await api.getProjectFile(path);
      setSelectedFile(data);
      setEditorValue(data.content || "");
      pushActivity("open", `Opened ${path}`);
    } catch (error) {
      setSelectedFile(null);
      setEditorValue("");
      setEditorError(error.message || "Не удалось открыть файл");
      pushActivity("error", `Open error for ${path}: ${error.message || "unknown error"}`);
    }
  }

  function pushActivity(type, text) {
    setActivity((prev) => [
      {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        type,
        text,
        ts: new Date().toLocaleTimeString(),
      },
      ...prev,
    ].slice(0, 40));
  }

  const filteredFiles = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return files;
    return files.filter((item) => item.path.toLowerCase().includes(q));
  }, [files, filter]);

  async function handlePlan() {
    if (!selectedFile) return;

    setPlanBusy(true);
    setAgentResult(null);

    try {
      const result = await api.runOllamaPlan({
        goal,
        selected_path: selectedFile.path,
        selected_content: editorValue,
        model: ollamaStatus?.default_model || "",
      });

      setAgentResult({
        type: "plan",
        payload: result,
      });

      pushActivity("plan", `Plan ready for ${selectedFile.path}`);
    } catch (error) {
      pushActivity("error", `Plan error: ${error.message || "unknown error"}`);
      setAgentResult({
        type: "error",
        payload: { message: error.message || "Plan failed" },
      });
    } finally {
      setPlanBusy(false);
    }
  }

  async function handleRun() {
    if (!selectedFile) return;

    setRunBusy(true);
    setAgentResult(null);

    try {
      const result = await api.runOllamaCode({
        goal,
        selected_path: selectedFile.path,
        selected_content: editorValue,
        project_files: [selectedFile.path],
        mode: "code",
        model: ollamaStatus?.default_model || "",
      });

      setAgentResult({
        type: "code",
        payload: result,
      });

      pushActivity("code", `Generated patch candidate for ${result.target_path || selectedFile.path}`);
    } catch (error) {
      pushActivity("error", `Code error: ${error.message || "unknown error"}`);
      setAgentResult({
        type: "error",
        payload: { message: error.message || "Code run failed" },
      });
    } finally {
      setRunBusy(false);
    }
  }

  const lineNumbers = useMemo(() => buildLineNumbers(editorValue), [editorValue]);
  const language = detectLanguage(selectedPath);

  return (
    <div className="jarvis-shell">
      <aside className="sidebar">
        <div className="panel-header">
          <div>
            <div className="eyebrow">Jarvis Work</div>
            <h1>Phase 15 IDE</h1>
          </div>
          <button className="ghost-btn" onClick={loadSnapshot} disabled={busy}>
            {busy ? "..." : "Refresh"}
          </button>
        </div>

        <div className="meta-card">
          <div className="meta-row">
            <span>Files</span>
            <strong>{filesCount}</strong>
          </div>
          <div className="meta-row">
            <span>Ollama</span>
            <strong>{ollamaStatus?.status === "ok" ? "online" : "offline"}</strong>
          </div>
          <div className="meta-row">
            <span>Model</span>
            <strong>{ollamaStatus?.default_model || "—"}</strong>
          </div>
        </div>

        <input
          className="search-input"
          placeholder="Фильтр файлов..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />

        {sidebarError ? <div className="error-box">{sidebarError}</div> : null}

        <div className="file-list">
          {filteredFiles.map((item) => (
            <button
              key={item.path}
              className={`file-item ${selectedPath === item.path ? "active" : ""}`}
              onClick={() => openFile(item.path)}
              title={item.path}
            >
              <div className="file-main">
                <span className="file-name">{item.name}</span>
                <span className="file-ext">{item.suffix || "file"}</span>
              </div>
              <div className="file-path">{item.path}</div>
            </button>
          ))}

          {!filteredFiles.length ? (
            <div className="empty-state">Нет файлов по фильтру.</div>
          ) : null}
        </div>
      </aside>

      <main className="workspace">
        <section className="workspace-top">
          <div className="editor-panel">
            <div className="editor-toolbar">
              <div className="editor-title-group">
                <div className="editor-title">
                  {selectedFile?.path || "Выбери файл слева"}
                </div>
                <div className="editor-subtitle">
                  {selectedFile
                    ? `${selectedFile.suffix || "text"} • ${formatBytes(selectedFile.size)} • ${language}`
                    : "project_brain/file endpoint"}
                </div>
              </div>

              <div className="editor-actions">
                <button
                  className="ghost-btn"
                  onClick={handlePlan}
                  disabled={!selectedFile || planBusy}
                >
                  {planBusy ? "Planning..." : "Preview Patch"}
                </button>
                <button
                  className="primary-btn"
                  onClick={handleRun}
                  disabled={!selectedFile || runBusy}
                >
                  {runBusy ? "Running..." : "Verify"}
                </button>
              </div>
            </div>

            {editorError ? <div className="error-box editor-error">{editorError}</div> : null}

            <div className="editor-wrap">
              <pre className="line-numbers">{lineNumbers}</pre>
              <textarea
                className="code-editor"
                value={editorValue}
                onChange={(e) => setEditorValue(e.target.value)}
                spellCheck={false}
                placeholder="Открой файл, чтобы увидеть код"
              />
            </div>
          </div>

          <div className="side-panels">
            <section className="panel">
              <div className="panel-header compact">
                <h2>Agent Goal</h2>
              </div>
              <textarea
                className="goal-input"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                spellCheck={false}
              />
            </section>

            <section className="panel">
              <div className="panel-header compact">
                <h2>Result</h2>
              </div>

              {!agentResult ? (
                <div className="empty-state">
                  Здесь появится plan или candidate patch.
                </div>
              ) : agentResult.type === "error" ? (
                <div className="error-box">{agentResult.payload.message}</div>
              ) : agentResult.type === "plan" ? (
                <div className="result-box">
                  <div className="result-title">{agentResult.payload.summary || "Plan"}</div>
                  <ul className="result-list">
                    {(agentResult.payload.steps || []).map((item, idx) => (
                      <li key={`${idx}-${item}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="result-box">
                  <div className="result-title">
                    {agentResult.payload.target_path || selectedPath}
                  </div>
                  <div className="result-meta">{agentResult.payload.answer || "Patch candidate created"}</div>
                  <pre className="result-code">
{agentResult.payload.updated_content || "// Empty response"}
                  </pre>
                </div>
              )}
            </section>
          </div>
        </section>

        <section className="timeline-panel">
          <div className="panel-header compact">
            <h2>Execution Activity</h2>
          </div>

          <div className="timeline-list">
            {activity.length ? (
              activity.map((item) => (
                <div key={item.id} className={`timeline-item timeline-${item.type}`}>
                  <div className="timeline-time">{item.ts}</div>
                  <div className="timeline-text">{item.text}</div>
                </div>
              ))
            ) : (
              <div className="empty-state">Пока нет событий.</div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
