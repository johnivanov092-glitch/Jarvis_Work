/**
 * ArtifactPanel.jsx — правая панель (как артефакты Claude).
 *
 * Показывает:
 *   • Код из ответов Jarvis (автоматически)
 *   • Кнопка Run для Python
 *   • Вывод выполнения (stdout/stderr)
 *   • Анализ кода (строки, функции, классы)
 *   • Copy / Download
 */
import { useState, useCallback, useMemo } from "react";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

/** Извлекает блоки кода из markdown */
function extractCodeBlocks(messages) {
  const blocks = [];
  for (const msg of messages) {
    if (msg.role !== "assistant") continue;
    const content = msg.content || "";
    const regex = /```(\w*)\n([\s\S]*?)```/g;
    let match;
    while ((match = regex.exec(content)) !== null) {
      const lang = match[1] || "text";
      const code = match[2].trim();
      if (code.length < 10) continue;
      const ext = { python: "py", javascript: "js", jsx: "jsx", typescript: "ts", tsx: "tsx", rust: "rs", go: "go", java: "java", css: "css", html: "html", json: "json", yaml: "yml", bash: "sh", sql: "sql", markdown: "md" }[lang] || lang || "txt";
      blocks.push({
        id: `code-${msg.id}-${blocks.length}`,
        name: `${lang}_${blocks.length + 1}.${ext}`,
        lang,
        code,
      });
    }
  }
  return blocks;
}

/** Определяет можно ли запустить код */
function isRunnable(lang) {
  return ["python", "py"].includes((lang || "").toLowerCase());
}


export default function ArtifactPanel({ messages, streamingCode, onClose }) {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState("code"); // "code" | "output" | "analysis"

  const blocks = useMemo(() => {
    const fromMessages = extractCodeBlocks(messages);
    // Add streaming code if present
    if (streamingCode) {
      const regex = /```(\w*)\n([\s\S]*?)```/g;
      let match;
      while ((match = regex.exec(streamingCode)) !== null) {
        const lang = match[1] || "text";
        const code = match[2].trim();
        if (code.length >= 10) {
          fromMessages.push({ id: `stream-${fromMessages.length}`, name: `streaming.${lang || "txt"}`, lang, code });
        }
      }
    }
    return fromMessages;
  }, [messages, streamingCode]);

  const current = blocks[selectedIdx] || blocks[blocks.length - 1] || null;

  // Auto-select latest block
  useMemo(() => {
    if (blocks.length > 0 && selectedIdx >= blocks.length) {
      setSelectedIdx(blocks.length - 1);
    }
  }, [blocks.length]);

  const handleCopy = useCallback(() => {
    if (!current) return;
    navigator.clipboard.writeText(current.code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [current]);

  const handleDownload = useCallback(() => {
    if (!current) return;
    const blob = new Blob([current.code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = current.name;
    a.click();
    URL.revokeObjectURL(url);
  }, [current]);

  async function handleRun() {
    if (!current || !isRunnable(current.lang)) return;
    setRunning(true);
    setOutput(null);
    setTab("output");
    try {
      const resp = await fetch(`${API}/api/tools/run-python`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: current.code }),
      });
      const data = await resp.json();
      setOutput(data);
    } catch (e) {
      setOutput({ ok: false, error: e.message, stdout: "", stderr: "" });
    } finally {
      setRunning(false);
    }
  }

  async function handleAnalyze() {
    if (!current) return;
    setTab("analysis");
    try {
      const resp = await fetch(`${API}/api/tools/analyze-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: current.code, language: current.lang, filename: current.name }),
      });
      const data = await resp.json();
      setAnalysis(data.analysis || data);
    } catch (e) {
      setAnalysis({ error: e.message });
    }
  }

  if (!blocks.length) return null;

  return (
    <div style={{
      width: 420, minWidth: 340, maxWidth: "45vw",
      borderLeft: "1px solid var(--border)",
      display: "flex", flexDirection: "column",
      background: "var(--bg-sidebar)",
      overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px", borderBottom: "1px solid var(--border)",
        gap: 8,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
          {current?.name || "Код"}
          <span style={{ marginLeft: 6, fontSize: 10, color: "var(--text-muted)", fontWeight: 400 }}>
            {current?.lang}
          </span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {current && isRunnable(current.lang) && (
            <button onClick={handleRun} disabled={running} style={btnStyle("#2d5a2d", "#4ade80")}>
              {running ? "⏳" : "▶"} Run
            </button>
          )}
          <button onClick={handleAnalyze} style={btnStyle()}>📊</button>
          <button onClick={handleCopy} style={btnStyle()}>
            {copied ? "✓" : "⧉"}
          </button>
          <button onClick={handleDownload} style={btnStyle()}>↓</button>
          <button onClick={onClose} style={btnStyle()}>✕</button>
        </div>
      </div>

      {/* Tab bar - if we have blocks */}
      {blocks.length > 1 && (
        <div style={{
          display: "flex", gap: 2, padding: "4px 8px",
          borderBottom: "1px solid var(--border)", overflow: "auto",
        }}>
          {blocks.map((b, i) => (
            <button
              key={b.id}
              onClick={() => { setSelectedIdx(i); setOutput(null); setAnalysis(null); setTab("code"); }}
              style={{
                padding: "3px 8px", borderRadius: 6, border: "none",
                fontSize: 10, cursor: "pointer", whiteSpace: "nowrap",
                background: i === selectedIdx ? "var(--bg-surface-active)" : "transparent",
                color: i === selectedIdx ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              {b.name}
            </button>
          ))}
        </div>
      )}

      {/* Content tabs */}
      <div style={{
        display: "flex", gap: 2, padding: "4px 8px",
        borderBottom: "1px solid var(--border)",
      }}>
        {["code", "output", "analysis"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: "3px 10px", borderRadius: 6, border: "none",
            fontSize: 10, cursor: "pointer", textTransform: "capitalize",
            background: tab === t ? "var(--bg-surface-active)" : "transparent",
            color: tab === t ? "var(--text-primary)" : "var(--text-muted)",
          }}>
            {t === "code" ? "Код" : t === "output" ? "Вывод" : "Анализ"}
          </button>
        ))}
      </div>

      {/* Code view */}
      {tab === "code" && current && (
        <pre style={{
          flex: 1, margin: 0, padding: 12, overflow: "auto",
          fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.55,
          color: "var(--text-primary)", whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>
          {current.code}
        </pre>
      )}

      {/* Output view */}
      {tab === "output" && (
        <div style={{ flex: 1, overflow: "auto", padding: 12 }}>
          {running ? (
            <div style={{ color: "var(--text-muted)", fontSize: 12 }}>⏳ Выполняется...</div>
          ) : output ? (
            <div>
              {output.ok ? (
                <>
                  {output.stdout && (
                    <div>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>STDOUT:</div>
                      <pre style={outputPre}>{output.stdout}</pre>
                    </div>
                  )}
                  {output.stderr && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: "#f0ad4e", marginBottom: 4 }}>STDERR:</div>
                      <pre style={{ ...outputPre, color: "#f0ad4e" }}>{output.stderr}</pre>
                    </div>
                  )}
                  {output.locals && Object.keys(output.locals).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>ПЕРЕМЕННЫЕ:</div>
                      {Object.entries(output.locals).map(([k, v]) => (
                        <div key={k} style={{ fontSize: 11, fontFamily: "var(--font-mono)", marginBottom: 2 }}>
                          <span style={{ color: "var(--accent)" }}>{k}</span> = {v}
                        </div>
                      ))}
                    </div>
                  )}
                  {!output.stdout && !output.stderr && (!output.locals || !Object.keys(output.locals).length) && (
                    <div style={{ color: "var(--text-muted)", fontSize: 12 }}>✓ Код выполнен без вывода</div>
                  )}
                </>
              ) : (
                <div>
                  <div style={{ fontSize: 10, color: "#ff6b6b", marginBottom: 4 }}>ОШИБКА:</div>
                  <pre style={{ ...outputPre, color: "#ff6b6b" }}>{output.error || output.traceback || "Unknown error"}</pre>
                  {output.stdout && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>STDOUT до ошибки:</div>
                      <pre style={outputPre}>{output.stdout}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 12 }}>
              {current && isRunnable(current.lang)
                ? "Нажми ▶ Run чтобы выполнить код"
                : "Выполнение доступно только для Python"}
            </div>
          )}
        </div>
      )}

      {/* Analysis view */}
      {tab === "analysis" && (
        <div style={{ flex: 1, overflow: "auto", padding: 12 }}>
          {analysis ? (
            analysis.error ? (
              <div style={{ color: "#ff6b6b", fontSize: 12 }}>{analysis.error}</div>
            ) : (
              <div style={{ fontSize: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={statRow}><span>Файл:</span><strong>{analysis.filename || "—"}</strong></div>
                <div style={statRow}><span>Язык:</span><strong>{analysis.language}</strong></div>
                <div style={statRow}><span>Строк кода:</span><strong>{analysis.code_lines}</strong></div>
                <div style={statRow}><span>Пустых строк:</span><strong>{analysis.blank_lines}</strong></div>
                <div style={statRow}><span>Комментариев:</span><strong>{analysis.comment_lines}</strong></div>

                {analysis.functions?.length > 0 && (
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: 10, marginBottom: 4 }}>ФУНКЦИИ ({analysis.functions.length}):</div>
                    {analysis.functions.map((f, i) => (
                      <div key={i} style={{ fontFamily: "var(--font-mono)", fontSize: 11, marginBottom: 2 }}>
                        <span style={{ color: "var(--accent)" }}>{f.name}</span>
                        <span style={{ color: "var(--text-muted)" }}> :L{f.line}</span>
                      </div>
                    ))}
                  </div>
                )}

                {analysis.classes?.length > 0 && (
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: 10, marginBottom: 4 }}>КЛАССЫ ({analysis.classes.length}):</div>
                    {analysis.classes.map((c, i) => (
                      <div key={i} style={{ fontFamily: "var(--font-mono)", fontSize: 11, marginBottom: 2 }}>
                        <span style={{ color: "#e2b93d" }}>{c.name}</span>
                        <span style={{ color: "var(--text-muted)" }}> :L{c.line}</span>
                      </div>
                    ))}
                  </div>
                )}

                {analysis.imports?.length > 0 && (
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: 10, marginBottom: 4 }}>ИМПОРТЫ ({analysis.imports.length}):</div>
                    {analysis.imports.map((imp, i) => (
                      <div key={i} style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-secondary)", marginBottom: 1 }}>
                        {imp.text}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 12 }}>Нажми 📊 для анализа кода</div>
          )}
        </div>
      )}
    </div>
  );
}

const btnStyle = (bg, color) => ({
  padding: "3px 8px", borderRadius: 6,
  border: "1px solid var(--border)",
  background: bg || "var(--bg-surface)",
  color: color || "var(--text-secondary)",
  cursor: "pointer", fontSize: 11, display: "flex", alignItems: "center", gap: 3,
});

const outputPre = {
  margin: 0, fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.5,
  whiteSpace: "pre-wrap", wordBreak: "break-word", color: "var(--text-primary)",
};

const statRow = {
  display: "flex", justifyContent: "space-between", padding: "4px 0",
  borderBottom: "1px solid var(--border-light)", color: "var(--text-secondary)",
};
