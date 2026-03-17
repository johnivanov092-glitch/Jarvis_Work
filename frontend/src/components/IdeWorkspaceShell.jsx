import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bot,
  Check,
  Eye,
  Play,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";

import { api } from "../api/ide";
import FileExplorerPanel from "./FileExplorerPanel";
import TerminalPanel from "./TerminalPanel";

function normalizeExecutions(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.executions)) return payload.executions;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
}

function normalizeBackups(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.backups)) return payload.backups;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
}

function normalizeEvents(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.events)) return payload.events;
  return [];
}

function extractPreviewText(preview) {
  if (!preview) return "";
  return (
    preview.diff ||
    preview.patch ||
    preview.preview ||
    preview.unified_diff ||
    JSON.stringify(preview, null, 2)
  );
}

function buildReferenceFiles(files = [], selectedPath = "", prompt = "") {
  const normalizedPrompt = prompt.toLowerCase();
  const keywords = normalizedPrompt
    .split(/[^a-zа-яё0-9_./-]+/i)
    .map((item) => item.trim())
    .filter((item) => item.length >= 3)
    .slice(0, 8);

  const ranked = files
    .filter((file) => file.path !== selectedPath)
    .map((file) => {
      let score = 0;
      if (selectedPath) {
        const selectedDir = selectedPath.split("/").slice(0, -1).join("/");
        if (selectedDir && file.path.startsWith(selectedDir)) {
          score += 3;
        }
      }
      keywords.forEach((keyword) => {
        if (file.path.toLowerCase().includes(keyword)) {
          score += 2;
        }
      });
      if (file.path.endsWith("package.json") || file.path.endsWith("requirements.txt")) {
        score += 1;
      }
      return { path: file.path, score };
    })
    .sort((a, b) => b.score - a.score || a.path.localeCompare(b.path))
    .slice(0, 6)
    .map((item) => item.path);

  return ranked;
}

export default function IdeWorkspaceShell() {
  const [prompt, setPrompt] = useState("Сделай безопасное улучшение в выбранном файле");
  const [files, setFiles] = useState([]);
  const [filesLoading, setFilesLoading] = useState(false);

  const [selectedFile, setSelectedFile] = useState(null);
  const [editorValue, setEditorValue] = useState("");
  const [originalValue, setOriginalValue] = useState("");
  const [expectedSha, setExpectedSha] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);

  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [applyLoading, setApplyLoading] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [rollbackLoading, setRollbackLoading] = useState(false);

  const [backups, setBackups] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [activeExecutionId, setActiveExecutionId] = useState("");
  const [events, setEvents] = useState([]);

  const [ollamaStatus, setOllamaStatus] = useState({ status: "idle", models: [], default_model: "" });
  const [selectedModel, setSelectedModel] = useState("");
  const [agentPlanning, setAgentPlanning] = useState(false);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentPlan, setAgentPlan] = useState(null);
  const [agentResult, setAgentResult] = useState(null);

  const [statusLine, setStatusLine] = useState("Jarvis IDE ready");

  const dirty = useMemo(
    () => selectedFile && editorValue !== originalValue,
    [selectedFile, editorValue, originalValue]
  );

  const loadSnapshot = useCallback(async () => {
    setFilesLoading(true);
    try {
      const snapshot = await api.projectSnapshot();
      setFiles(snapshot.files || []);
      setStatusLine(`Loaded ${snapshot.files_count || 0} files`);
    } catch (error) {
      setStatusLine(`Snapshot error: ${error.message}`);
      setFiles([]);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  const loadBackups = useCallback(async () => {
    try {
      const payload = await api.listBackups(20);
      setBackups(normalizeBackups(payload));
    } catch {
      setBackups([]);
    }
  }, []);

  const loadExecutions = useCallback(async () => {
    try {
      const payload = await api.listExecutions(20);
      const items = normalizeExecutions(payload);
      setExecutions(items);

      if (!activeExecutionId && items.length > 0) {
        const firstId = items[0].execution_id || items[0].id || items[0].run_id || "";
        setActiveExecutionId(firstId);
      }
    } catch {
      setExecutions([]);
    }
  }, [activeExecutionId]);

  const loadExecutionEvents = useCallback(async (executionId) => {
    if (!executionId) {
      setEvents([]);
      return;
    }

    try {
      const payload = await api.executionEvents(executionId);
      setEvents(normalizeEvents(payload));
    } catch {
      setEvents([]);
    }
  }, []);

  const loadOllamaStatus = useCallback(async () => {
    try {
      const payload = await api.ollamaStatus();
      setOllamaStatus(payload);
      setSelectedModel((current) => current || payload.default_model || payload.models?.[0] || "");
    } catch (error) {
      setOllamaStatus({ status: "error", models: [], default_model: "", error: error.message });
      setSelectedModel("");
    }
  }, []);

  const openFile = useCallback(async (file) => {
    if (!file?.path) {
      return;
    }

    setSelectedFile(file);
    setFileLoading(true);
    setPreview(null);
    setAgentResult(null);
    setAgentPlan(null);

    try {
      const payload = await api.readFile(file.path);
      setEditorValue(payload.content || "");
      setOriginalValue(payload.content || "");
      setExpectedSha(payload.sha256 || null);
      setStatusLine(`Opened ${payload.path}`);
    } catch (error) {
      setEditorValue("");
      setOriginalValue("");
      setExpectedSha(null);
      setStatusLine(`Open file error: ${error.message}`);
    } finally {
      setFileLoading(false);
    }
  }, []);

  const previewPatch = useCallback(async () => {
    if (!selectedFile?.path) {
      return;
    }

    setPreviewLoading(true);
    try {
      const payload = await api.previewPatch(selectedFile.path, editorValue);
      setPreview(payload);
      setStatusLine(`Preview ready for ${selectedFile.path}`);
    } catch (error) {
      setPreview(null);
      setStatusLine(`Preview error: ${error.message}`);
    } finally {
      setPreviewLoading(false);
    }
  }, [selectedFile, editorValue]);

  const applyPatch = useCallback(async () => {
    if (!selectedFile?.path) {
      return;
    }

    setApplyLoading(true);
    try {
      const payload = await api.applyPatch(selectedFile.path, editorValue, expectedSha);
      setStatusLine(
        payload?.status ? `Patch applied: ${payload.status}` : `Patch applied for ${selectedFile.path}`
      );

      await openFile(selectedFile);
      await loadBackups();
      await loadExecutions();
    } catch (error) {
      setStatusLine(`Apply error: ${error.message}`);
    } finally {
      setApplyLoading(false);
    }
  }, [selectedFile, editorValue, expectedSha, openFile, loadBackups, loadExecutions]);

  const verifyPatch = useCallback(async () => {
    if (!selectedFile?.path) {
      return;
    }

    setVerifyLoading(true);
    try {
      const payload = await api.verifyPatch(selectedFile.path);
      setStatusLine(
        payload?.status ? `Verify: ${payload.status}` : `Verify complete for ${selectedFile.path}`
      );
      await loadExecutions();
    } catch (error) {
      setStatusLine(`Verify error: ${error.message}`);
    } finally {
      setVerifyLoading(false);
    }
  }, [selectedFile, loadExecutions]);

  const rollbackPatch = useCallback(
    async (backupId) => {
      if (!backupId) {
        return;
      }

      setRollbackLoading(true);
      try {
        const payload = await api.rollbackPatch(backupId);
        setStatusLine(payload?.status ? `Rollback: ${payload.status}` : "Rollback complete");

        await loadBackups();
        await loadExecutions();

        if (selectedFile?.path) {
          await openFile(selectedFile);
        }
      } catch (error) {
        setStatusLine(`Rollback error: ${error.message}`);
      } finally {
        setRollbackLoading(false);
      }
    },
    [selectedFile, openFile, loadBackups, loadExecutions]
  );

  const runExecution = useCallback(async () => {
    if (!prompt.trim()) {
      return;
    }

    try {
      const payload = await api.startExecution(prompt, "autonomous_dev", {
        source: "ide",
        file_path: selectedFile?.path || null,
      });

      const executionId = payload?.execution_id || payload?.id || payload?.run_id || "";

      if (executionId) {
        setActiveExecutionId(executionId);
        await loadExecutionEvents(executionId);
      }

      await loadExecutions();
      setStatusLine("Execution started");
    } catch (error) {
      setStatusLine(`Run error: ${error.message}`);
    }
  }, [prompt, selectedFile, loadExecutions, loadExecutionEvents]);

  const planWithOllama = useCallback(async () => {
    if (!selectedFile?.path || !editorValue.trim()) {
      setStatusLine("Open a real file before planning with Ollama");
      return;
    }

    setAgentPlanning(true);
    try {
      const payload = await api.ollamaPlan({
        goal: prompt,
        selectedPath: selectedFile.path,
        selectedContent: editorValue,
        model: selectedModel || undefined,
      });
      setAgentPlan(payload);
      setStatusLine(`Plan ready from ${payload.model || "ollama"}`);
    } catch (error) {
      setStatusLine(`Plan error: ${error.message}`);
    } finally {
      setAgentPlanning(false);
    }
  }, [prompt, selectedFile, editorValue, selectedModel]);

  const runLocalAgent = useCallback(async () => {
    if (!selectedFile?.path || !editorValue.trim()) {
      setStatusLine("Open a file before running the local agent");
      return;
    }

    setAgentRunning(true);
    try {
      const payload = await api.ollamaRun({
        goal: prompt,
        selectedPath: selectedFile.path,
        selectedContent: editorValue,
        model: selectedModel || undefined,
        projectFiles: buildReferenceFiles(files, selectedFile.path, prompt),
      });

      setAgentResult(payload);

      if (payload.changed && payload.replacement_content) {
        setEditorValue(payload.replacement_content);
        const previewPayload = await api.previewPatch(selectedFile.path, payload.replacement_content);
        setPreview(previewPayload);
        setStatusLine(`Agent patch ready from ${payload.model || "ollama"}`);
      } else {
        setStatusLine(payload.summary || "Agent finished without patch");
      }
    } catch (error) {
      setStatusLine(`Agent error: ${error.message}`);
    } finally {
      setAgentRunning(false);
    }
  }, [prompt, selectedFile, editorValue, selectedModel, files]);

  const resetEditorToOriginal = useCallback(() => {
    setEditorValue(originalValue);
    setPreview(null);
    setAgentResult(null);
    setStatusLine("Editor reverted to current file content");
  }, [originalValue]);

  useEffect(() => {
    loadSnapshot();
    loadBackups();
    loadExecutions();
    loadOllamaStatus();
  }, [loadSnapshot, loadBackups, loadExecutions, loadOllamaStatus]);

  useEffect(() => {
    loadExecutionEvents(activeExecutionId);
  }, [activeExecutionId, loadExecutionEvents]);

  useEffect(() => {
    const timer = setInterval(() => {
      loadExecutions();
      if (activeExecutionId) {
        loadExecutionEvents(activeExecutionId);
      }
    }, 4000);

    return () => clearInterval(timer);
  }, [activeExecutionId, loadExecutions, loadExecutionEvents]);

  return (
    <div className="ide-shell">
      <header className="ide-topbar">
        <div className="ide-title">
          <Sparkles size={16} />
          <span>Jarvis IDE</span>
        </div>

        <div className="topbar-right">
          <div className="agent-provider-chip">
            <Bot size={14} />
            <span>
              {ollamaStatus.status === "ok"
                ? `Ollama · ${selectedModel || "model not selected"}`
                : "Ollama offline"}
            </span>
          </div>
          <div className="ide-status">{statusLine}</div>
        </div>
      </header>

      <main className="ide-layout">
        <aside className="ide-sidebar">
          <FileExplorerPanel
            files={files}
            loading={filesLoading}
            selectedPath={selectedFile?.path || ""}
            onRefresh={loadSnapshot}
            onOpen={openFile}
          />
        </aside>

        <section className="ide-main">
          <div className="prompt-bar prompt-bar-phase16">
            <input
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Describe the task for Jarvis..."
            />

            <select
              className="model-select"
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              disabled={ollamaStatus.status !== "ok" || !ollamaStatus.models?.length}
            >
              {(ollamaStatus.models || []).map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
              {!ollamaStatus.models?.length ? <option value="">No local models</option> : null}
            </select>

            <button type="button" className="action-button" onClick={runExecution}>
              <Play size={15} />
              <span>Run</span>
            </button>

            <button
              type="button"
              className="action-button"
              onClick={planWithOllama}
              disabled={!selectedFile || agentPlanning || ollamaStatus.status !== "ok"}
            >
              <Wand2 size={15} />
              <span>{agentPlanning ? "Planning..." : "Plan"}</span>
            </button>

            <button
              type="button"
              className="action-button"
              onClick={runLocalAgent}
              disabled={!selectedFile || agentRunning || ollamaStatus.status !== "ok"}
            >
              <Bot size={15} />
              <span>{agentRunning ? "Thinking..." : "Local Agent"}</span>
            </button>

            <button
              type="button"
              className="action-button ghost"
              onClick={previewPatch}
              disabled={!selectedFile || previewLoading}
            >
              <Eye size={15} />
              <span>{previewLoading ? "Previewing..." : "Preview Patch"}</span>
            </button>

            <button
              type="button"
              className="action-button ghost"
              onClick={applyPatch}
              disabled={!selectedFile || !dirty || applyLoading}
            >
              <Save size={15} />
              <span>{applyLoading ? "Applying..." : "Apply Patch"}</span>
            </button>

            <button
              type="button"
              className="action-button ghost"
              onClick={verifyPatch}
              disabled={!selectedFile || verifyLoading}
            >
              <ShieldCheck size={15} />
              <span>{verifyLoading ? "Verifying..." : "Verify"}</span>
            </button>

            <button
              type="button"
              className="action-button ghost"
              onClick={resetEditorToOriginal}
              disabled={!selectedFile || fileLoading || !dirty}
            >
              <Check size={15} />
              <span>Reset</span>
            </button>

            <button
              type="button"
              className="action-button ghost"
              onClick={() => {
                loadSnapshot();
                loadOllamaStatus();
              }}
              disabled={filesLoading}
            >
              <RefreshCw size={15} />
              <span>Refresh</span>
            </button>
          </div>

          <div className="editor-grid">
            <section className="panel editor-panel">
              <div className="panel-header">
                <div className="panel-title">
                  <Check size={16} />
                  <span>{selectedFile?.path || "No file selected"}</span>
                </div>
                <div className="panel-meta">
                  {fileLoading ? "Loading..." : dirty ? "Modified" : "Saved"}
                </div>
              </div>

              <textarea
                className="code-editor"
                spellCheck={false}
                value={editorValue}
                onChange={(event) => setEditorValue(event.target.value)}
                placeholder="Select a file from the explorer"
              />
            </section>

            <section className="panel diff-panel">
              <div className="panel-header">
                <div className="panel-title">
                  <Eye size={16} />
                  <span>Patch preview</span>
                </div>
                <div className="panel-meta">{agentResult?.model || "phase11 diff"}</div>
              </div>

              <pre className="diff-output">
                {extractPreviewText(preview) || "No preview generated yet"}
              </pre>
            </section>
          </div>

          <TerminalPanel
            executions={executions}
            activeExecutionId={activeExecutionId}
            events={events}
            backups={backups}
            agentPlan={agentPlan}
            agentResult={agentResult}
            verifying={verifyLoading}
            rollingBack={rollbackLoading}
            onSelectExecution={setActiveExecutionId}
            onRollback={rollbackPatch}
            onVerify={verifyPatch}
          />
        </section>
      </main>
    </div>
  );
}
