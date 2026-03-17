import { useEffect, useMemo, useState } from "react";
import { api } from "../api/ide";
import FileExplorer from "./FileExplorer";
import CodeEditor from "./CodeEditor";
import DiffViewer from "./DiffViewer";
import TerminalPanel from "./TerminalPanel";
import PatchHistoryPanel from "./PatchHistoryPanel";
import BatchVerifyPanel from "./BatchVerifyPanel";
import ProjectMapPanel from "./ProjectMapPanel";
import PatchPlanPanel from "./PatchPlanPanel";
import FileOpsPanel from "./FileOpsPanel";
import TaskRunnerPanel from "./TaskRunnerPanel";
import TaskHistoryPanel from "./TaskHistoryPanel";
import SupervisorPanel from "./SupervisorPanel";
import Phase19Panel from "./Phase19Panel";
import Phase20Panel from "./Phase20Panel";
import Phase21Panel from "./Phase21Panel";
import StabilizationPreflightPanel from "./StabilizationPreflightPanel";

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
  const [verifyResult, setVerifyResult] = useState(null);
  const [applyLoading, setApplyLoading] = useState(false);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [diffText, setDiffText] = useState("");
  const [diffStats, setDiffStats] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState(null);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null);
  const [stagedPaths, setStagedPaths] = useState([]);
  const [stagedContents, setStagedContents] = useState({});
  const [batchVerifyResult, setBatchVerifyResult] = useState(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [projectMap, setProjectMap] = useState(null);
  const [patchPlan, setPatchPlan] = useState(null);
  const [taskGoal, setTaskGoal] = useState("Добавь безопасное улучшение в текущий файл и подготовь verify.");
  const [taskMode, setTaskMode] = useState("code");
  const [taskRun, setTaskRun] = useState(null);
  const [taskHistoryItems, setTaskHistoryItems] = useState([]);
  const [selectedTaskHistoryId, setSelectedTaskHistoryId] = useState(null);
  const [selectedTaskHistoryItem, setSelectedTaskHistoryItem] = useState(null);
  const [supervisorGoal, setSupervisorGoal] = useState("Построй полный supervisor pipeline для текущей задачи.");
  const [supervisorMode, setSupervisorMode] = useState("code");
  const [supervisorAutoApply, setSupervisorAutoApply] = useState(false);
  const [supervisorRun, setSupervisorRun] = useState(null);
  const [supervisorHistoryItems, setSupervisorHistoryItems] = useState([]);
  const [selectedSupervisorHistoryId, setSelectedSupervisorHistoryId] = useState(null);
  const [phase19Goal, setPhase19Goal] = useState("Сделай multi-file reasoning и подготовь изменения по staged файлам.");
  const [phase19Run, setPhase19Run] = useState(null);
  const [phase19HistoryItems, setPhase19HistoryItems] = useState([]);
  const [selectedPhase19HistoryId, setSelectedPhase19HistoryId] = useState(null);
  const [phase20Goal, setPhase20Goal] = useState("Проанализируй проект и подготовь multi-agent execution plan по staged файлам.");
  const [phase20Run, setPhase20Run] = useState(null);
  const [phase20HistoryItems, setPhase20HistoryItems] = useState([]);
  const [selectedPhase20HistoryId, setSelectedPhase20HistoryId] = useState(null);
  const [phase20PreviewQueue, setPhase20PreviewQueue] = useState(null);
  const [phase20ExecutionState, setPhase20ExecutionState] = useState(null);
  const [phase21Goal, setPhase21Goal] = useState("Запусти автономный execution controller для очереди и checkpoint state.");
  const [phase21Run, setPhase21Run] = useState(null);
  const [phase21HistoryItems, setPhase21HistoryItems] = useState([]);
  const [selectedPhase21HistoryId, setSelectedPhase21HistoryId] = useState(null);
  const [preflightResult, setPreflightResult] = useState(null);

  useEffect(() => {
    loadFiles(); loadProjectMap(); loadTaskHistory(); loadSupervisorHistory(); loadPhase19History(); loadPhase20History(); loadPhase21History();
  }, []);

  useEffect(() => {
    if (selectedPath) loadHistory(selectedPath);
    else { setHistoryItems([]); setSelectedHistoryId(null); setSelectedHistoryItem(null); }
  }, [selectedPath]);

  async function loadFiles() { try { setLoadingFiles(true); const payload = await api.getProjectSnapshot(); setFiles(payload?.files || payload?.items || []); } finally { setLoadingFiles(false); } }
  async function loadProjectMap() { try { setProjectMap(await api.getProjectMap()); } catch {} }
  async function loadTaskHistory() { try { setTaskHistoryItems(await api.listTaskHistory()); } catch {} }
  async function loadSupervisorHistory() { try { setSupervisorHistoryItems(await api.listSupervisorHistory()); } catch {} }
  async function loadPhase19History() { try { setPhase19HistoryItems(await api.listPhase19History()); } catch {} }
  async function loadPhase20History() { try { setPhase20HistoryItems(await api.listPhase20History()); } catch {} }
  async function loadPhase21History() { try { setPhase21HistoryItems(await api.listPhase21History()); } catch {} }
  async function loadHistory(path) { try { setHistoryItems(await api.listPatchHistory(path)); } catch {} }

  async function openFile(file) {
    const payload = await api.getProjectFile(file.path);
    const content = payload?.content || "";
    setSelectedPath(file.path); setEditorValue(content); setOriginalValue(content); setPreviewValue(""); setDiffText(""); setDiffStats(null);
    setStagedContents((prev) => ({ ...prev, [file.path]: content }));
  }

  function appendLog(message) { setLogs((prev) => [`${new Date().toLocaleTimeString()}  ${message}`, ...prev].slice(0, 300)); }
  async function buildDiff(original, updated) { if (!selectedPath) return; const result = await api.diffPatch({ path: selectedPath, original, updated }); setDiffText(result?.diff_text || ""); setDiffStats(result?.stats || null); }

  async function handlePreviewPatch() {
    if (!selectedPath) return appendLog("Сначала выбери файл.");
    try {
      setPreviewLoading(true);
      const payload = await api.previewPatch({ path: selectedPath, instruction, content: editorValue });
      const updated = payload?.updated_content || payload?.content || payload?.answer || "";
      setPreviewValue(updated); await buildDiff(originalValue, updated); appendLog("Preview patch готов.");
    } finally { setPreviewLoading(false); }
  }

  async function handleApplyLocalPreview() {
    if (!previewValue) return appendLog("Нет preview для применения.");
    setEditorValue(previewValue); setVerifyResult(null); setStagedContents((prev) => ({ ...prev, [selectedPath]: previewValue })); await buildDiff(originalValue, previewValue);
  }

  function toggleStage(path) {
    setStagedPaths((prev) => prev.includes(path) ? prev.filter((item) => item !== path) : [...prev, path]);
    setStagedContents((prev) => ({ ...prev, [path]: path === selectedPath ? editorValue : (prev[path] ?? "") }));
  }

  function mergePathsIntoStage(paths) {
    const list = (paths || []).filter(Boolean);
    if (!list.length) return appendLog("Нет файлов для stage.");
    setStagedPaths((prev) => Array.from(new Set([...prev, ...list])));
    appendLog(`Добавлено в stage: ${list.length} файлов.`);
  }

  useEffect(() => { if (selectedPath) setStagedContents((prev) => ({ ...prev, [selectedPath]: editorValue })); }, [editorValue, selectedPath]);

  async function runPreflight() {
    const result = await api.runStabilizationPreflight({
      phase20_queue_items: phase20PreviewQueue?.items || [],
      phase20_execution_state: phase20ExecutionState || {},
      phase21_run: phase21Run || {},
      staged_paths: stagedPaths,
    });
    setPreflightResult(result);
    appendLog(`Preflight: ${result.ready ? "ready" : "blocked"}`);
    return result;
  }

  async function guardedApplyBatch() {
    const result = await runPreflight();
    if (!result?.ready) {
      appendLog("Apply blocked by preflight.");
      return;
    }
    await handleApplyBatch();
  }

  async function guardedVerifyBatch() {
    const result = await runPreflight();
    if (!result?.ready) {
      appendLog("Verify blocked by preflight.");
      return;
    }
    await handleVerifyBatch();
  }

  async function handleApplyToDisk() {
    if (!selectedPath) return appendLog("Нет выбранного файла.");
    try {
      setApplyLoading(true);
      await api.applyPatch({ path: selectedPath, content: editorValue });
      setOriginalValue(editorValue); setPreviewValue(""); setVerifyResult(null); await buildDiff(editorValue, editorValue); await loadHistory(selectedPath);
    } finally { setApplyLoading(false); }
  }

  async function handleApplyBatch() {
    if (!stagedPaths.length) return appendLog("Нет staged файлов.");
    try {
      setBatchLoading(true);
      const items = stagedPaths.map((path) => ({ path, content: path === selectedPath ? editorValue : (stagedContents[path] ?? "") }));
      await api.applyPatchBatch(items);
      if (selectedPath && stagedPaths.includes(selectedPath)) setOriginalValue(editorValue);
      await loadHistory(selectedPath || ""); await loadFiles(); appendLog(`Batch apply: ${items.length} файлов`);
    } finally { setBatchLoading(false); }
  }

  async function handleRollbackDisk() {
    if (!selectedPath) return appendLog("Нет выбранного файла.");
    try {
      setRollbackLoading(true);
      await api.rollbackPatch({ path: selectedPath });
      const payload = await api.getProjectFile(selectedPath);
      const content = payload?.content || "";
      setEditorValue(content); setOriginalValue(content); setPreviewValue(""); setVerifyResult(null);
      setStagedContents((prev) => ({ ...prev, [selectedPath]: content })); await buildDiff(content, content); await loadHistory(selectedPath);
    } finally { setRollbackLoading(false); }
  }

  async function handleVerify() {
    if (!selectedPath) return appendLog("Нет выбранного файла.");
    try {
      setVerifyLoading(true);
      const result = await api.verifyPatch({ path: selectedPath, content: editorValue });
      setVerifyResult(result); setDiffText(result?.diff_text || ""); setDiffStats(result?.stats || null);
    } finally { setVerifyLoading(false); }
  }

  async function handleVerifyBatch() {
    if (!stagedPaths.length) return appendLog("Нет staged файлов для verify.");
    try {
      setBatchLoading(true);
      const items = stagedPaths.map((path) => ({ path, content: path === selectedPath ? editorValue : (stagedContents[path] ?? "") }));
      const result = await api.verifyPatchBatch(items);
      setBatchVerifyResult(result); appendLog(`Batch verify: ${items.length} файлов`);
    } finally { setBatchLoading(false); }
  }

  async function handleSelectHistory(item) { setSelectedHistoryId(item.id); const full = await api.getPatchHistoryItem(item.id); setSelectedHistoryItem(full); setDiffText(full?.diff_text || ""); setDiffStats(full?.stats || null); }
  async function handleBuildPlan() { setPatchPlan(await api.patchPlan({ goal: instruction, current_path: selectedPath, current_content: editorValue, staged_paths: stagedPaths })); }
  async function handleRunTask() { setTaskRun(await api.runTask({ goal: taskGoal, mode: taskMode, current_path: selectedPath, staged_paths: stagedPaths })); await loadTaskHistory(); }
  async function handleSelectTaskHistory(item) { setSelectedTaskHistoryId(item.id); setSelectedTaskHistoryItem(await api.getTaskHistoryItem(item.id)); }
  async function handleRunSupervisor() { setSupervisorRun(await api.runSupervisor({ goal: supervisorGoal, mode: supervisorMode, current_path: selectedPath, staged_paths: stagedPaths, auto_apply: supervisorAutoApply })); await loadSupervisorHistory(); }
  async function handleExecuteSupervisor() {
    if (!selectedPath) return appendLog("Для execute supervisor нужен выбранный файл.");
    const result = await api.executeSupervisor({ goal: supervisorGoal, current_path: selectedPath, current_content: editorValue, auto_apply: supervisorAutoApply });
    setSupervisorRun(result); setPreviewValue(result?.preview?.proposed_content || "");
    if (result?.preview?.current_content !== undefined && result?.preview?.proposed_content !== undefined) await buildDiff(result.preview.current_content, result.preview.proposed_content);
    await loadSupervisorHistory();
  }
  async function handleSelectSupervisorHistory(item) { setSelectedSupervisorHistoryId(item.id); setSupervisorRun(await api.getSupervisorHistoryItem(item.id)); }
  async function handleRunPhase19() { setPhase19Run(await api.runPhase19({ goal: phase19Goal, mode: "multi-file", selected_paths: stagedPaths })); await loadPhase19History(); }
  function handleAutoStagePhase19() { const paths = (phase19Run?.plan || []).filter((item) => item.action === "modify" || item.action === "create").map((item) => item.path); mergePathsIntoStage(paths); }
  async function handleSelectPhase19History(item) { setSelectedPhase19HistoryId(item.id); setPhase19Run(await api.getPhase19HistoryItem(item.id)); }
  async function handleRunPhase20() { const result = await api.runPhase20({ goal: phase20Goal, selected_paths: stagedPaths }); setPhase20Run(result); setPhase20PreviewQueue(null); setPhase20ExecutionState(null); await loadPhase20History(); }
  function handleAutoStagePhase20() { const paths = (phase20Run?.planner?.items || []).filter((item) => item.action === "modify" || item.action === "create").map((item) => item.path); mergePathsIntoStage(paths); }
  async function handleBuildPreviewQueuePhase20() {
    const targets = phase20Run?.execution?.preview_targets || [];
    if (!targets.length) return appendLog("Phase20 queue: нет preview targets.");
    const queue = await api.buildPhase20PreviewQueue({ goal: phase20Goal, targets });
    setPhase20PreviewQueue(queue); appendLog(`Queue: ${queue.count || 0} файлов`);
  }
  async function handleBuildExecutionStatePhase20() {
    if (!phase20PreviewQueue?.items?.length) return appendLog("Phase20 state: сначала собери preview queue.");
    const state = await api.buildPhase20ExecutionState({ goal: phase20Goal, queue_items: phase20PreviewQueue.items, staged_paths: stagedPaths });
    setPhase20ExecutionState(state); appendLog(`Execution state: ${state.state_id || "ok"}`);
  }
  async function handlePreviewExecutionPhase20() {
    const targets = phase20PreviewQueue?.items?.filter((item) => item.status === "queued").map((item) => item.path) || phase20Run?.execution?.preview_targets || [];
    if (!targets.length) return appendLog("Phase20 preview: нет preview targets.");
    const firstTarget = targets[0];
    if (firstTarget !== selectedPath) { const file = files.find((item) => item.path === firstTarget); if (file) await openFile(file); }
    const sourceContent = stagedContents[firstTarget] ?? editorValue ?? "";
    const payload = await api.previewPatch({ path: firstTarget, instruction: phase20Goal, content: sourceContent });
    const updated = payload?.updated_content || payload?.content || payload?.answer || "";
    setPreviewValue(updated);
    const original = firstTarget === selectedPath ? originalValue : sourceContent;
    await buildDiff(original, updated);
    setStagedContents((prev) => ({ ...prev, [firstTarget]: updated }));
    if (phase20PreviewQueue?.items?.length) {
      setPhase20PreviewQueue((prev) => ({
        ...prev,
        items: prev.items.map((item) => item.path === firstTarget && item.status === "queued" ? { ...item, status: "done" } : item),
      }));
    }
    appendLog(`Preview next: ${firstTarget}`);
  }
  async function handleSelectPhase20History(item) { setSelectedPhase20HistoryId(item.id); setPhase20Run(await api.getPhase20HistoryItem(item.id)); }
  async function handleRunPhase21() {
    if (!phase20PreviewQueue?.items?.length) return appendLog("Phase21: сначала собери preview queue.");
    const result = await api.runPhase21({ goal: phase21Goal, queue_items: phase20PreviewQueue.items, execution_state: phase20ExecutionState || {} });
    setPhase21Run(result); await loadPhase21History(); appendLog(`Phase21 controller: ${result.run_id || "ok"}`);
  }
  async function handleSelectPhase21History(item) { setSelectedPhase21HistoryId(item.id); setPhase21Run(await api.getPhase21HistoryItem(item.id)); }
  async function handleCreateFile(path, content) { await api.createFile({ path, content }); await loadFiles(); await loadProjectMap(); }
  async function handleRenameFile(oldPath, newPath) { if (!oldPath || !newPath) return; await api.renameFile({ old_path: oldPath, new_path: newPath }); await loadFiles(); await loadProjectMap(); }
  async function handleDeleteFile(path) { if (!path) return; await api.deleteFile({ path }); await loadFiles(); await loadProjectMap(); }

  const stagedCount = useMemo(() => stagedPaths.length, [stagedPaths]);

  return (
    <div className="code-workspace-v10">
      <div className="code-left">
        <FileExplorer files={files} selectedPath={selectedPath} stagedPaths={stagedPaths} onSelect={openFile} onToggleStage={toggleStage} />
      </div>

      <div className="code-center">
        <CodeEditor filePath={selectedPath} value={editorValue} onChange={setEditorValue} />
        <div className="patch-controls">
          <div className="patch-controls-title">Patch Engine</div>
          <textarea className="patch-instruction" value={instruction} onChange={(e) => setInstruction(e.target.value)} spellCheck={false} />
          <div className="patch-buttons">
            <button className="soft-btn" onClick={handlePreviewPatch} disabled={previewLoading || loadingFiles}>{previewLoading ? "Preview..." : "Preview Patch"}</button>
            <button className="soft-btn" onClick={handleApplyLocalPreview}>Apply to Editor</button>
            <button className="soft-btn" onClick={handleApplyToDisk} disabled={applyLoading}>{applyLoading ? "Applying..." : "Apply Patch"}</button>
            <button className="soft-btn" onClick={handleRollbackDisk} disabled={rollbackLoading}>{rollbackLoading ? "Rollback..." : "Rollback"}</button>
            <button className="soft-btn" onClick={handleVerify} disabled={verifyLoading}>{verifyLoading ? "Verify..." : "Verify"}</button>
          </div>
          <div className="batch-bar">
            <div className="batch-bar-meta">Staged: {stagedCount}</div>
            <div className="patch-buttons">
              <button className="soft-btn" onClick={guardedVerifyBatch} disabled={batchLoading}>{batchLoading ? "Batch..." : "Verify Staged"}</button>
              <button className="soft-btn" onClick={guardedApplyBatch} disabled={batchLoading}>{batchLoading ? "Batch..." : "Apply Staged"}</button>
            </div>
          </div>
        </div>
        <DiffViewer diffText={diffText} stats={diffStats} loading={previewLoading} />
      </div>

      <div className="code-right">
        <StabilizationPreflightPanel
          phase20Queue={phase20PreviewQueue}
          phase20State={phase20ExecutionState}
          phase21Run={phase21Run}
          stagedPaths={stagedPaths}
          result={preflightResult}
          onRun={runPreflight}
        />
        <Phase21Panel
          goal={phase21Goal}
          setGoal={setPhase21Goal}
          previewQueue={phase20PreviewQueue}
          executionState={phase20ExecutionState}
          runResult={phase21Run}
          historyItems={phase21HistoryItems}
          selectedHistoryId={selectedPhase21HistoryId}
          onRun={handleRunPhase21}
          onApplyController={guardedApplyBatch}
          onVerifyController={guardedVerifyBatch}
          onSelectHistory={handleSelectPhase21History}
        />
        <Phase20Panel
          goal={phase20Goal}
          setGoal={setPhase20Goal}
          selectedPaths={stagedPaths}
          runResult={phase20Run}
          historyItems={phase20HistoryItems}
          selectedHistoryId={selectedPhase20HistoryId}
          previewQueue={phase20PreviewQueue}
          executionState={phase20ExecutionState}
          onRun={handleRunPhase20}
          onBuildPreviewQueue={handleBuildPreviewQueuePhase20}
          onBuildExecutionState={handleBuildExecutionStatePhase20}
          onPreviewExecution={handlePreviewExecutionPhase20}
          onAutoStageExecution={handleAutoStagePhase20}
          onApplyExecution={guardedApplyBatch}
          onVerifyExecution={guardedVerifyBatch}
          onSelectHistory={handleSelectPhase20History}
        />
        <Phase19Panel
          goal={phase19Goal}
          setGoal={setPhase19Goal}
          selectedPaths={stagedPaths}
          runResult={phase19Run}
          historyItems={phase19HistoryItems}
          selectedHistoryId={selectedPhase19HistoryId}
          onRun={handleRunPhase19}
          onAutoStagePlan={handleAutoStagePhase19}
          onApplyPlanned={guardedApplyBatch}
          onVerifyPlanned={guardedVerifyBatch}
          onSelectHistory={handleSelectPhase19History}
        />
        <SupervisorPanel
          goal={supervisorGoal}
          setGoal={setSupervisorGoal}
          mode={supervisorMode}
          setMode={setSupervisorMode}
          autoApply={supervisorAutoApply}
          setAutoApply={setSupervisorAutoApply}
          runResult={supervisorRun}
          historyItems={supervisorHistoryItems}
          selectedHistoryId={selectedSupervisorHistoryId}
          onRun={handleRunSupervisor}
          onExecute={handleExecuteSupervisor}
          onSelectHistory={handleSelectSupervisorHistory}
        />
        <TaskRunnerPanel goal={taskGoal} setGoal={setTaskGoal} mode={taskMode} setMode={setTaskMode} taskRun={taskRun} taskHistoryItem={selectedTaskHistoryItem} onRunTask={handleRunTask} />
        <TaskHistoryPanel items={taskHistoryItems} selectedId={selectedTaskHistoryId} onSelect={handleSelectTaskHistory} />
        <PatchPlanPanel plan={patchPlan} onBuildPlan={handleBuildPlan} />
        <ProjectMapPanel projectMap={projectMap} onRefresh={loadProjectMap} />
        <FileOpsPanel onCreate={handleCreateFile} onRename={handleRenameFile} onDelete={handleDeleteFile} selectedPath={selectedPath} />
        <PatchHistoryPanel items={historyItems} selectedId={selectedHistoryId} onSelect={handleSelectHistory} />
        <BatchVerifyPanel result={batchVerifyResult} />
        <TerminalPanel logs={logs} verifyResult={verifyResult} historyItem={selectedHistoryItem} />
      </div>
    </div>
  );
}
