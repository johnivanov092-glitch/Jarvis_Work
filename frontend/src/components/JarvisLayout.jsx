import { useEffect, useRef, useState } from "react";
import { Bot, Folder, FolderKanban, MessageSquare, Paperclip, Plus, Search, Send, Settings, SlidersHorizontal, Trash2, Pencil, X } from "lucide-react";
import { api } from "../api/ide";

const NAV_ITEMS = [
  { key: "search", label: "Search", icon: Search },
  { key: "chats", label: "Chats", icon: MessageSquare },
  { key: "projects", label: "Projects", icon: Folder },
  { key: "settings", label: "Settings", icon: Settings },
];

const SAMPLE_PROJECTS = [
  { id: 1, name: "Jarvis Work", task: "Главный desktop AI агент" },
  { id: 2, name: "Research Engine", task: "Мультипоиск и разбор страниц" },
  { id: 3, name: "Code Agent", task: "Кодинг, патчи, workflow" },
];

const DEFAULT_SETTINGS = {
  ollama_context: 8192,
  default_model: "qwen3:8b",
  agent_profile: "Сбалансированный",
};

export default function JarvisLayout() {
  const [activeNav, setActiveNav] = useState("chats");
  const [activeTopTab, setActiveTopTab] = useState("chat");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [models, setModels] = useState([]);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [statusText, setStatusText] = useState("Jarvis готов");

  const fileInputRef = useRef(null);
  const chatScrollRef = useRef(null);

  useEffect(() => { loadBoot(); }, []);
  useEffect(() => {
    const el = chatScrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, attachedFiles]);

  async function loadBoot() {
    try {
      const [settingsPayload, modelsPayload, chatsPayload] = await Promise.all([
        api.getSettings(), api.getModels(), api.listChats()
      ]);
      setSettings(settingsPayload || DEFAULT_SETTINGS);
      setModels(modelsPayload?.models || []);
      const items = chatsPayload?.items || [];
      setChats(items);
      if (items.length > 0) {
        setActiveChatId(items[0].id);
        await loadMessages(items[0].id);
      } else {
        const created = await api.createChat("Новый чат");
        await refreshChats(created.id);
      }
      setStatusText(modelsPayload?.ollama_ok ? "Ollama подключен" : "Ollama недоступен");
    } catch (error) {
      setStatusText(`Ошибка загрузки: ${error.message}`);
    }
  }

  async function refreshChats(nextChatId = null) {
    const payload = await api.listChats();
    const items = payload?.items || [];
    setChats(items);
    const targetId = nextChatId || items[0]?.id || null;
    setActiveChatId(targetId);
    if (targetId) await loadMessages(targetId);
    else setMessages([]);
  }

  async function loadMessages(chatId) {
    const payload = await api.getMessages(chatId);
    setMessages(payload?.items || []);
  }

  async function handleCreateChat() {
    const created = await api.createChat("Новый чат");
    await refreshChats(created.id);
  }

  async function handleRenameChat(chat) {
    const title = window.prompt("Новое название чата", chat.title || "Новый чат");
    if (!title) return;
    await api.renameChat(chat.id, title);
    await refreshChats(chat.id);
  }

  async function handleDeleteChat(chat) {
    const ok = window.confirm(`Удалить чат "${chat.title}"?`);
    if (!ok) return;
    await api.deleteChat(chat.id);
    await refreshChats();
  }

  async function handleSaveSettings() {
    const saved = await api.saveSettings(settings);
    setSettings(saved);
    setStatusText("Настройки сохранены в backend");
  }

  const handleAttachFiles = (event) => {
    const list = Array.from(event.target.files || []);
    if (!list.length) return;
    const mapped = list.map((file, index) => ({
      id: `${file.name}-${file.size}-${Date.now()}-${index}`,
      name: file.name,
      size: file.size,
      type: file.type || "file",
    }));
    setAttachedFiles((prev) => [...prev, ...mapped]);
    event.target.value = "";
  };

  const removeAttachedFile = (id) => {
    setAttachedFiles((prev) => prev.filter((item) => item.id !== id));
  };

  async function sendMessage() {
    const text = draft.trim();
    if (!text && attachedFiles.length === 0) return;
    await api.addMessage({ chat_id: activeChatId, role: "user", content: text || "Прикрепил файлы" });
    await api.addMessage({
      chat_id: activeChatId,
      role: "assistant",
      content: activeTopTab === "code"
        ? "Режим Code активен. Jarvis может открыть workflow кодинга, подключить мульти-агентный оркестратор, показать preview кода и подготовить действия по файлам."
        : "Принял задачу. Jarvis обработает чат, код, план или исследование в зависимости от запроса и настроек профиля."
    });
    setDraft("");
    setAttachedFiles([]);
    await loadMessages(activeChatId);
    await refreshChats(activeChatId);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button type="button" className="new-chat-btn" onClick={handleCreateChat}>
          <Plus size={16} /><span>Новый чат</span>
        </button>

        <div className="nav-list">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button type="button" key={item.key} className={`nav-item ${activeNav === item.key ? "active" : ""}`} onClick={() => setActiveNav(item.key)}>
                <Icon size={16} /><span>{item.label}</span>
              </button>
            );
          })}
        </div>

        <div className="sidebar-block">
          <div className="block-title">Все чаты</div>
          <div className="simple-list">
            {chats.map((chat) => (
              <div key={chat.id} className={`chat-row ${chat.id === activeChatId ? "active" : ""}`}>
                <button type="button" className="simple-list-item" onClick={async () => { setActiveChatId(chat.id); await loadMessages(chat.id); }}>
                  {chat.title}
                </button>
                <div className="chat-row-actions">
                  <button type="button" className="mini-btn" onClick={() => handleRenameChat(chat)}><Pencil size={12} /></button>
                  <button type="button" className="mini-btn danger" onClick={() => handleDeleteChat(chat)}><Trash2 size={12} /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-title">Jarvis Агент ИИ</div>
          <div className="top-tabs">
            <button type="button" className={activeTopTab === "chat" ? "active" : ""} onClick={() => setActiveTopTab("chat")}>Чат</button>
            <button type="button" className={activeTopTab === "code" ? "active" : ""} onClick={() => setActiveTopTab("code")}>Code</button>
            <button type="button" className="orchestrator-pill"><FolderKanban size={14} /><span>Мульти агент Оркестратор</span></button>
          </div>
        </header>

        <section className="workspace">
          <div className="center-pane">
            {activeNav === "settings" ? (
              <div className="settings-card">
                <div className="panel-title">Settings</div>
                <label className="settings-field">
                  <span>Контекст Ollama</span>
                  <input type="number" min="1024" step="1024" value={settings.ollama_context} onChange={(e) => setSettings((prev) => ({ ...prev, ollama_context: Number(e.target.value || 0) }))} />
                </label>
                <label className="settings-field">
                  <span>Языковая модель по умолчанию</span>
                  <select value={settings.default_model} onChange={(e) => setSettings((prev) => ({ ...prev, default_model: e.target.value }))}>
                    {models.length > 0 ? models.map((item) => <option key={item.name} value={item.name}>{item.name}</option>) : <option value="qwen3:8b">qwen3:8b</option>}
                  </select>
                </label>
                <label className="settings-field">
                  <span>Профиль агента</span>
                  <select value={settings.agent_profile} onChange={(e) => setSettings((prev) => ({ ...prev, agent_profile: e.target.value }))}>
                    <option value="Сбалансированный">Сбалансированный</option>
                    <option value="Кодинг">Кодинг</option>
                    <option value="Исследование">Исследование</option>
                    <option value="Мульти-агентный оркестратор">Мульти-агентный оркестратор</option>
                  </select>
                </label>
                <button type="button" className="save-settings-btn" onClick={handleSaveSettings}>Сохранить настройки</button>
                <div className="settings-note">{statusText}</div>
              </div>
            ) : activeNav === "projects" ? (
              <div className="panel-card">
                <div className="panel-title">Projects</div>
                <div className="projects-list">
                  {SAMPLE_PROJECTS.map((project) => (
                    <div key={project.id} className="project-row">
                      <div><div className="project-name">{project.name}</div><div className="project-task">{project.task}</div></div>
                      <button type="button" className="row-action">Открыть</button>
                    </div>
                  ))}
                </div>
              </div>
            ) : activeNav === "search" ? (
              <div className="panel-card">
                <div className="panel-title">Search</div>
                <div className="panel-text">Здесь будет поиск по чатам, проектам и полной памяти.</div>
              </div>
            ) : (
              <div className="chat-layout">
                <div className="chat-header-line">
                  <div className="panel-title">Чаты</div>
                  <div className="panel-subtitle">{settings.default_model} • {settings.agent_profile}</div>
                </div>

                <div className="chat-scroll" ref={chatScrollRef}>
                  {messages.length === 0 ? (
                    <div className="message-row assistant">
                      <div className="message-avatar"><Bot size={16} /></div>
                      <div className="message-bubble">Jarvis готов. Начни новый чат или напиши сообщение.</div>
                    </div>
                  ) : messages.map((message) => (
                    <div key={message.id} className={`message-row ${message.role === "user" ? "user" : "assistant"}`}>
                      <div className="message-avatar">{message.role === "assistant" ? <Bot size={16} /> : "E"}</div>
                      <div className="message-bubble"><div>{message.content}</div></div>
                    </div>
                  ))}
                </div>

                <div className="composer-fixed">
                  {attachedFiles.length > 0 && (
                    <div className="attach-strip">
                      {attachedFiles.map((file) => (
                        <div key={file.id} className="attach-chip">
                          <Paperclip size={13} />
                          <span>{file.name}</span>
                          <button type="button" onClick={() => removeAttachedFile(file.id)}><X size={12} /></button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="composer-card">
                    <button type="button" className="attach-btn" onClick={() => fileInputRef.current?.click()} title="Добавить файл"><Plus size={18} /></button>
                    <input ref={fileInputRef} type="file" multiple className="hidden-input" onChange={handleAttachFiles} />
                    <textarea value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Напиши задачу… Jarvis сам выберет режим" onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }} />
                    <div className="composer-actions">
                      <div className="composer-mode"><span>{settings.default_model}</span><span className="dot">•</span><span>{settings.agent_profile}</span></div>
                      <button type="button" className="send-btn" onClick={sendMessage}><Send size={16} /></button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
