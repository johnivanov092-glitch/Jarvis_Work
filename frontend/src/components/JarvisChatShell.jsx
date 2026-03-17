import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Globe,
  LoaderCircle,
  Paperclip,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Undo2,
  Wand2,
  X,
} from "lucide-react";

import { api } from "../api/ide";

function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

function normalizeBackups(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.backups)) return payload.backups;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
}

function extractPreviewText(preview) {
  if (!preview) return "";
  return preview.diff || preview.patch || preview.preview || preview.unified_diff || JSON.stringify(preview, null, 2);
}

function newSession() {
  return {
    id: Math.random().toString(36).slice(2, 10),
    title: "New chat",
    messages: [
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          "Jarvis готов. Прикрепляй файлы, проектные файлы и пиши обычным языком — я сам решу, нужен чат, план, код или веб-исследование.",
      },
    ],
    attachmentIds: [],
    attachments: [],
    selectedProjectPaths: [],
    plan: [],
    diffPreview: null,
    codeSuggestion: null,
    webResults: [],
    agentsUsed: [],
    expectedSha: null,
  };
}

function MessageBubble({ message }) {
  return (
    <div className={classNames("message-row", message.role === "user" ? "is-user" : "is-assistant")}>
      <div className="message-avatar">{message.role === "user" ? "Е" : <Bot size={16} />}</div>
      <div className="message-card">
        {message.label ? <div className="message-label">{message.label}</div> : null}
        <div className="message-content">{message.content}</div>
        {Array.isArray(message.plan) && message.plan.length ? (
          <div className="inline-plan">
            {message.plan.map((item, index) => (
              <div key={`${index}-${item}`} className="plan-line">
                <span>{index + 1}.</span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function AttachmentChip({ item, onRemove }) {
  return (
    <div className="attachment-chip">
      <Paperclip size={14} />
      <span>{item.name}</span>
      <button type="button" className="ghost-icon" onClick={() => onRemove?.(item.id)}>
        <X size={14} />
      </button>
    </div>
  );
}

export default function JarvisChatShell() {
  const [sessions, setSessions] = useState([newSession()]);
  const [activeSessionId, setActiveSessionId] = useState(() => sessions?.[0]?.id || newSession().id);
  const [message, setMessage] = useState("");
  const [mode, setMode] = useState("auto");
  const [webEnabled, setWebEnabled] = useState(true);
  const [ollama, setOllama] = useState({ models: [], default_model: "", status: "idle" });
  const [selectedModel, setSelectedModel] = useState("");
  const [projectFiles, setProjectFiles] = useState([]);
  const [projectFilesLoading, setProjectFilesLoading] = useState(false);
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const [projectFilter, setProjectFilter] = useState("");
  const [legacyAgents, setLegacyAgents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [statusLine, setStatusLine] = useState("Jarvis Chat ready");
  const [applyLoading, setApplyLoading] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [backups, setBackups] = useState([]);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  const activeSession = useMemo(
    () => sessions.find((item) => item.id === activeSessionId) || sessions[0],
    [sessions, activeSessionId]
  );

  const filteredProjectFiles = useMemo(() => {
    const q = projectFilter.trim().toLowerCase();
    if (!q) return projectFiles.slice(0, 300);
    return projectFiles.filter((item) => item.path.toLowerCase().includes(q)).slice(0, 300);
  }, [projectFiles, projectFilter]);

  const loadSnapshot = useCallback(async () => {
    setProjectFilesLoading(true);
    try {
      const payload = await api.projectSnapshot();
      setProjectFiles(payload.files || []);
      setStatusLine(`Loaded ${payload.files_count || 0} project files`);
    } catch (error) {
      setProjectFiles([]);
      setStatusLine(`Snapshot error: ${error.message}`);
    } finally {
      setProjectFilesLoading(false);
    }
  }, []);

  const loadOllama = useCallback(async () => {
    try {
      const payload = await api.ollamaStatus();
      setOllama(payload);
      setSelectedModel((current) => current || payload.default_model || payload.models?.[0] || "");
    } catch (error) {
      setOllama({ models: [], default_model: "", status: "error", error: error.message });
      setStatusLine(`Ollama error: ${error.message}`);
    }
  }, []);

  const loadLegacyAgents = useCallback(async () => {
    try {
      const payload = await api.legacyAgents();
      setLegacyAgents(payload.agents || []);
    } catch {
      setLegacyAgents([]);
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

  useEffect(() => {
    loadSnapshot();
    loadOllama();
    loadLegacyAgents();
    loadBackups();
  }, [loadSnapshot, loadOllama, loadLegacyAgents, loadBackups]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeSession?.messages]);

  const updateActiveSession = useCallback((updater) => {
    setSessions((current) =>
      current.map((item) => (item.id === activeSessionId ? (typeof updater === "function" ? updater(item) : updater) : item))
    );
  }, [activeSessionId]);

  const createChat = () => {
    const fresh = newSession();
    setSessions((current) => [fresh, ...current]);
    setActiveSessionId(fresh.id);
    setMessage("");
  };

  const removeAttachment = (attachmentId) => {
    updateActiveSession((session) => ({
      ...session,
      attachments: session.attachments.filter((item) => item.id !== attachmentId),
      attachmentIds: session.attachmentIds.filter((id) => id !== attachmentId),
      selectedProjectPaths: session.selectedProjectPaths.filter((path) => {
        const removed = session.attachments.find((item) => item.id === attachmentId);
        return removed?.project_path ? path !== removed.project_path : true;
      }),
    }));
  };

  const handleUploadFiles = async (files) => {
    const list = Array.from(files || []);
    if (!list.length) return;
    setBusy(true);
    setStatusLine("Uploading attachments...");
    try {
      const uploaded = [];
      for (const file of list) {
        const payload = await api.uploadAttachment(file);
        if (payload?.attachment) uploaded.push(payload.attachment);
      }
      updateActiveSession((session) => ({
        ...session,
        attachments: [...session.attachments, ...uploaded],
        attachmentIds: [...session.attachmentIds, ...uploaded.map((item) => item.id)],
      }));
      setStatusLine(`Attached ${uploaded.length} file(s)`);
    } catch (error) {
      setStatusLine(`Upload error: ${error.message}`);
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const attachProjectFile = async (path) => {
    setBusy(true);
    try {
      const payload = await api.attachProjectFile(path);
      const attachment = payload?.attachment;
      if (!attachment) return;
      updateActiveSession((session) => ({
        ...session,
        attachments: [...session.attachments, attachment],
        attachmentIds: [...session.attachmentIds, attachment.id],
        selectedProjectPaths: Array.from(new Set([...(session.selectedProjectPaths || []), attachment.project_path || path])),
      }));
      setProjectPickerOpen(false);
      setStatusLine(`Project file attached: ${path}`);
    } catch (error) {
      setStatusLine(`Attach project file error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const sendMessage = async () => {
    const text = message.trim();
    if (!text || busy || !activeSession) return;

    const userMessage = { id: crypto.randomUUID(), role: "user", content: text };
    updateActiveSession((session) => ({ ...session, messages: [...session.messages, userMessage] }));
    setMessage("");
    setBusy(true);
    setStatusLine("Jarvis is thinking...");

    try {
      const payload = await api.sendChat({
        message: text,
        model: selectedModel,
        mode,
        webEnabled,
        sessionId: activeSession.id,
        attachmentIds: activeSession.attachmentIds,
        selectedProjectPaths: activeSession.selectedProjectPaths,
      });

      let preview = null;
      let expectedSha = activeSession.expectedSha;
      if (payload?.code_suggestion?.target_path && payload?.code_suggestion?.updated_content) {
        try {
          const currentFile = await api.readFile(payload.code_suggestion.target_path);
          expectedSha = currentFile.sha256 || null;
          preview = await api.previewPatch(payload.code_suggestion.target_path, payload.code_suggestion.updated_content);
        } catch {
          preview = null;
        }
      }

      const assistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        label: `${payload?.route?.mode || "chat"}${payload?.model ? ` • ${payload.model}` : ""}`,
        content: payload?.answer || "Пустой ответ модели.",
        plan: Array.isArray(payload?.plan) ? payload.plan : [],
      };

      updateActiveSession((session) => ({
        ...session,
        title: session.title === "New chat" ? text.slice(0, 32) : session.title,
        messages: [...session.messages, assistantMessage],
        plan: Array.isArray(payload?.plan) ? payload.plan : [],
        webResults: payload?.web_results || [],
        agentsUsed: payload?.agents_used || [],
        diffPreview: preview,
        codeSuggestion: payload?.code_suggestion || null,
        expectedSha,
      }));

      setStatusLine(`Mode: ${payload?.route?.mode || "chat"}`);
    } catch (error) {
      updateActiveSession((session) => ({
        ...session,
        messages: [
          ...session.messages,
          { id: crypto.randomUUID(), role: "assistant", label: "error", content: error.message || "Chat error" },
        ],
      }));
      setStatusLine(`Chat error: ${error.message}`);
    } finally {
      setBusy(false);
    }
  };

  const applyPatch = async () => {
    if (!activeSession?.codeSuggestion?.target_path || !activeSession?.codeSuggestion?.updated_content) return;
    setApplyLoading(true);
    try {
      const payload = await api.applyPatch(
        activeSession.codeSuggestion.target_path,
        activeSession.codeSuggestion.updated_content,
        activeSession.expectedSha || null
      );
      updateActiveSession((session) => ({
        ...session,
        messages: [
          ...session.messages,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            label: "patch",
            content: payload?.status ? `Patch applied: ${payload.status}` : "Patch applied",
          },
        ],
      }));
      await loadBackups();
      setStatusLine("Patch applied");
    } catch (error) {
      setStatusLine(`Apply error: ${error.message}`);
    } finally {
      setApplyLoading(false);
    }
  };

  const verifyPatch = async () => {
    if (!activeSession?.codeSuggestion?.target_path) return;
    setVerifyLoading(true);
    try {
      const payload = await api.verifyPatch(activeSession.codeSuggestion.target_path);
      updateActiveSession((session) => ({
        ...session,
        messages: [
          ...session.messages,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            label: "verify",
            content: payload?.status ? `Verify: ${payload.status}` : "Verify complete",
          },
        ],
      }));
      setStatusLine("Verify complete");
    } catch (error) {
      setStatusLine(`Verify error: ${error.message}`);
    } finally {
      setVerifyLoading(false);
    }
  };

  const rollbackPatch = async (backupId) => {
    if (!backupId) return;
    setRollbackLoading(true);
    try {
      const payload = await api.rollbackPatch(backupId);
      updateActiveSession((session) => ({
        ...session,
        messages: [
          ...session.messages,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            label: "rollback",
            content: payload?.status ? `Rollback: ${payload.status}` : "Rollback complete",
          },
        ],
      }));
      await loadBackups();
      setStatusLine("Rollback complete");
    } catch (error) {
      setStatusLine(`Rollback error: ${error.message}`);
    } finally {
      setRollbackLoading(false);
    }
  };

  return (
    <div className="chat-shell">
      <aside className="chat-sidebar">
        <div className="sidebar-top">
          <button type="button" className="primary-button wide" onClick={createChat}>
            <Plus size={16} />
            <span>New chat</span>
          </button>
          <button type="button" className="ghost-button" onClick={loadSnapshot} disabled={projectFilesLoading}>
            <RefreshCw size={15} />
          </button>
        </div>

        <div className="sidebar-section-label">Chats</div>
        <div className="session-list">
          {sessions.map((item) => (
            <button
              key={item.id}
              type="button"
              className={classNames("session-item", item.id === activeSessionId && "active")}
              onClick={() => setActiveSessionId(item.id)}
            >
              <span>{item.title}</span>
            </button>
          ))}
        </div>

        <div className="sidebar-section-label">Legacy agents</div>
        <div className="agent-mini-list">
          {legacyAgents.slice(0, 8).map((agent) => (
            <div key={agent.id} className="agent-mini-card">
              <div className="agent-mini-title">{agent.title}</div>
              <div className="agent-mini-text">{agent.kind}</div>
            </div>
          ))}
        </div>
      </aside>

      <main className="chat-main">
        <header className="chat-topbar">
          <div className="brand">
            <Sparkles size={16} />
            <span>Jarvis</span>
          </div>

          <div className="toolbar-row">
            <label className="control-chip">
              <span>Mode</span>
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
                <option value="auto">Auto</option>
                <option value="chat">Chat</option>
                <option value="plan">Plan</option>
                <option value="research">Research</option>
                <option value="code">Code</option>
                <option value="analyze">Analyze</option>
              </select>
            </label>

            <label className="control-chip">
              <span>Model</span>
              <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)}>
                {(ollama.models || []).map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              className={classNames("toggle-chip", webEnabled && "is-on")}
              onClick={() => setWebEnabled((current) => !current)}
            >
              <Globe size={15} />
              <span>{webEnabled ? "Web on" : "Web off"}</span>
            </button>
          </div>
        </header>

        <section className="chat-stream">
          <div className="message-list">
            {activeSession?.messages.map((item) => (
              <MessageBubble key={item.id} message={item} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </section>

        <section className="composer-panel">
          {activeSession?.attachments?.length ? (
            <div className="attachment-row">
              {activeSession.attachments.map((item) => (
                <AttachmentChip key={item.id} item={item} onRemove={removeAttachment} />
              ))}
            </div>
          ) : null}

          <div className="composer-actions-row">
            <button type="button" className="ghost-button" onClick={() => fileInputRef.current?.click()}>
              <Paperclip size={15} />
              <span>Attach file</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(event) => handleUploadFiles(event.target.files)}
            />

            <button type="button" className="ghost-button" onClick={() => setProjectPickerOpen(true)}>
              <Search size={15} />
              <span>Attach project file</span>
            </button>
          </div>

          <div className="composer-box">
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Напиши задачу обычным языком. Jarvis сам выберет chat / plan / code / analyze / research."
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
            />
            <button type="button" className="send-button" onClick={sendMessage} disabled={busy || !message.trim()}>
              {busy ? <LoaderCircle size={16} className="spin" /> : <Send size={16} />}
            </button>
          </div>
        </section>
      </main>

      <aside className="inspector-panel">
        <div className="inspector-card">
          <div className="inspector-title">Plan</div>
          {activeSession?.plan?.length ? (
            activeSession.plan.map((item, index) => (
              <div key={`${index}-${item}`} className="plan-line">
                <span>{index + 1}.</span>
                <span>{item}</span>
              </div>
            ))
          ) : (
            <div className="empty-text">No plan yet</div>
          )}
        </div>

        <div className="inspector-card">
          <div className="inspector-title">Patch preview</div>
          <pre className="diff-box">{extractPreviewText(activeSession?.diffPreview) || "No patch suggestion yet"}</pre>
          <div className="action-row">
            <button type="button" className="ghost-button" onClick={applyPatch} disabled={!activeSession?.codeSuggestion || applyLoading}>
              <Wand2 size={15} />
              <span>{applyLoading ? "Applying..." : "Apply patch"}</span>
            </button>
            <button type="button" className="ghost-button" onClick={verifyPatch} disabled={!activeSession?.codeSuggestion || verifyLoading}>
              <ShieldCheck size={15} />
              <span>{verifyLoading ? "Verifying..." : "Verify"}</span>
            </button>
          </div>
        </div>

        <div className="inspector-card">
          <div className="inspector-title">Web sources</div>
          {activeSession?.webResults?.length ? (
            activeSession.webResults.map((item) => (
              <div key={item.url} className="web-card">
                <div className="web-title">{item.title || item.url}</div>
                <div className="web-url">{item.url}</div>
                <div className="web-snippet">{item.snippet}</div>
              </div>
            ))
          ) : (
            <div className="empty-text">No web sources</div>
          )}
        </div>

        <div className="inspector-card">
          <div className="inspector-title">Rollback backups</div>
          {backups.length ? (
            backups.slice(0, 8).map((item) => (
              <div key={item.backup_id || item.id} className="backup-row">
                <div>
                  <div className="backup-path">{item.file_path || item.path || "unknown file"}</div>
                  <div className="backup-id">{item.backup_id || item.id}</div>
                </div>
                <button
                  type="button"
                  className="ghost-button compact"
                  onClick={() => rollbackPatch(item.backup_id || item.id)}
                  disabled={rollbackLoading}
                >
                  <Undo2 size={14} />
                </button>
              </div>
            ))
          ) : (
            <div className="empty-text">No backups</div>
          )}
        </div>
      </aside>

      {projectPickerOpen ? (
        <div className="modal-overlay" onClick={() => setProjectPickerOpen(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div className="inspector-title">Attach project file</div>
              <button type="button" className="ghost-button compact" onClick={() => setProjectPickerOpen(false)}>
                <X size={14} />
              </button>
            </div>
            <div className="search-box">
              <Search size={14} />
              <input value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)} placeholder="Search project file..." />
            </div>
            <div className="project-file-list">
              {filteredProjectFiles.map((item) => (
                <button key={item.path} type="button" className="project-file-item" onClick={() => attachProjectFile(item.path)}>
                  {item.path}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <div className="status-bar">
        <span>{statusLine}</span>
        <span>{selectedModel ? `Ollama • ${selectedModel}` : "No model"}</span>
      </div>
    </div>
  );
}
