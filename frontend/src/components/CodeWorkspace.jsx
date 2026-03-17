import { useEffect, useState } from "react";
import { api } from "../api/ide";
import FileExplorer from "./FileExplorer";
import CodeEditor from "./CodeEditor";
import DiffViewer from "./DiffViewer";
import TerminalPanel from "./TerminalPanel";

export default function CodeWorkspace() {
  const [files, setFiles] = useState([]);
  const [selectedPath, setSelectedPath] = useState("");
  const [editorValue, setEditorValue] = useState("");
  const [originalValue, setOriginalValue] = useState("");
  const [instruction, setInstruction] = useState("Улучши выбранный файл безопасно и без лишних переписываний.");
  const [previewValue, setPreviewValue] = useState("");
  const [logs, setLogs] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    loadFiles();
  }, []);

  async function loadFiles() {
    try {
      setLoadingFiles(true);
      appendLog("Загрузка snapshot проекта...");
      const payload = await api.getProjectSnapshot();
      const items = payload?.files || payload?.items || [];
      setFiles(items);
      appendLog(`Snapshot загружен: ${items.length} файлов.`);
    } catch (e) {
      appendLog(`Ошибка загрузки snapshot: ${e.message || "unknown error"}`);
    } finally {
      setLoadingFiles(false);
    }
  }

  async function openFile(file) {
    try {
      appendLog(`Открытие файла: ${file.path}`);
      setSelectedPath(file.path);
      const payload = await api.getProjectFile(file.path);
      const content = payload?.content || "";
      setEditorValue(content);
      setOriginalValue(content);
      setPreviewValue("");
      appendLog(`Файл открыт: ${file.path}`);
    } catch (e) {
      appendLog(`Ошибка чтения файла: ${e.message || "unknown error"}`);
    }
  }

  function appendLog(message) {
    setLogs((prev) => [
      `${new Date().toLocaleTimeString()}  ${message}`,
      ...prev,
    ].slice(0, 100));
  }

  async function handlePreviewPatch() {
    if (!selectedPath) {
      appendLog("Сначала выбери файл.");
      return;
    }

    try {
      setPreviewLoading(true);
      appendLog(`Preview patch: ${selectedPath}`);
      const payload = await api.previewPatch({
        path: selectedPath,
        instruction,
        content: editorValue,
      });

      const updated =
        payload?.updated_content ||
        payload?.content ||
        payload?.answer ||
        "";

      setPreviewValue(updated);
      appendLog("Preview patch готов.");
    } catch (e) {
      appendLog(`Ошибка preview patch: ${e.message || "unknown error"}`);
    } finally {
      setPreviewLoading(false);
    }
  }

  function handleApplyLocalPreview() {
    if (!previewValue) {
      appendLog("Нет preview для применения.");
      return;
    }
    setEditorValue(previewValue);
    appendLog("Preview применён локально в редактор.");
  }

  function handleRollback() {
    setEditorValue(originalValue);
    setPreviewValue("");
    appendLog("Локальный rollback выполнен.");
  }

  return (
    <div className="code-workspace-v2">
      <div className="code-left">
        <FileExplorer
          files={files}
          selectedPath={selectedPath}
          onSelect={openFile}
        />
      </div>

      <div className="code-center">
        <CodeEditor
          filePath={selectedPath}
          value={editorValue}
          onChange={setEditorValue}
        />

        <div className="patch-controls">
          <div className="patch-controls-title">Patch Engine</div>
          <textarea
            className="patch-instruction"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            spellCheck={false}
          />
          <div className="patch-buttons">
            <button className="soft-btn" onClick={handlePreviewPatch} disabled={previewLoading || loadingFiles}>
              {previewLoading ? "Preview..." : "Preview Patch"}
            </button>
            <button className="soft-btn" onClick={handleApplyLocalPreview}>
              Apply to Editor
            </button>
            <button className="soft-btn" onClick={handleRollback}>
              Rollback
            </button>
          </div>
        </div>

        <DiffViewer
          original={originalValue}
          updated={previewValue}
          loading={previewLoading}
        />
      </div>

      <div className="code-right">
        <TerminalPanel logs={logs} />
      </div>
    </div>
  );
}
