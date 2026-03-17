import { useEffect, useMemo, useState } from "react";
import { api } from "../api/ide";
import MemoryPanel from "./MemoryPanel";
import CodeWorkspace from "./CodeWorkspace";

function normalizeArray(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
}

function getChatId(chat) {
  return chat?.id ?? chat?.chat_id ?? chat?.uuid;
}

function getChatTitle(chat) {
  return chat?.title || chat?.name || "Новый чат";
}

function getChatPinned(chat) {
  return Boolean(chat?.pinned ?? chat?.is_pinned);
}

function getMessageRole(message) {
  return message?.role || message?.sender || "assistant";
}

function getMessageContent(message) {
  return (
    message?.content ??
    message?.text ??
    message?.message ??
    message?.answer ??
    ""
  );
}

export default function JarvisChatShell() {
  const [activeLeftTab, setActiveLeftTab] = useState("chats");
  const [activeTopTab, setActiveTopTab] = useState("chat");

  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [composer, setComposer] = useState("");

  const [searchQuery, setSearchQuery] = useState("");
  const [searchChats, setSearchChats] = useState([]);
  const [searchProjects, setSearchProjects] = useState([]);

  const [memoryItems, setMemoryItems] = useState([]);

  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const [models] = useState([{ name: "qwen3:8b" }]);
  const [selectedModel, setSelectedModel] = useState("qwen3:8b");
  const [agentProfile, setAgentProfile] = useState("Сбалансированный");

  useEffect(() => {
    boot();
  }, []);

  useEffect(() => {
    if (selectedChatId) {
      loadMessages(selectedChatId);
    }
  }, [selectedChatId]);

  useEffect(() => {
    if (activeLeftTab === "search" && searchQuery.trim()) {
      const timer = setTimeout(() => {
        runSearch(searchQuery.trim());
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [searchQuery, activeLeftTab]);

  async function boot() {
    try {
      await Promise.all([loadChats(), loadMemory()]);
    } catch (e) {
      setError(e.message || "Не удалось загрузить интерфейс");
    }
  }

  async function loadChats() {
    const payload = await api.listChats();
    const items = normalizeArray(payload);
    setChats(items);
    if (!selectedChatId && items.length) {
      setSelectedChatId(getChatId(items[0]));
    }
  }

  async function loadMessages(chatId) {
    const payload = await api.getMessages(chatId);
    setMessages(normalizeArray(payload));
  }

  async function loadMemory(q = "") {
    const items = await api.listMemory(q);
    setMemoryItems(items);
  }

  async function runSearch(query) {
    try {
      const payload = await api.search(query);
      setSearchChats(normalizeArray(payload?.chats ?? payload));
      setSearchProjects(normalizeArray(payload?.projects ?? []));
      await loadMemory(query);
    } catch {
      setSearchChats([]);
      setSearchProjects([]);
    }
  }

  async function handleCreateChat() {
    try {
      const created = await api.createChat("Новый чат");
      await loadChats();
      const id = getChatId(created);
      if (id) setSelectedChatId(id);
    } catch (e) {
      setError(e.message || "Не удалось создать чат");
    }
  }

  async function handleRenameChat(chat) {
    const current = getChatTitle(chat);
    const title = window.prompt("Новое название чата", current);
    if (!title || title.trim() === current) return;
    try {
      await api.renameChat(getChatId(chat), title.trim());
      await loadChats();
    } catch (e) {
      setError(e.message || "Не удалось переименовать чат");
    }
  }

  async function handleDeleteChat(chat) {
    if (!window.confirm(`Удалить чат "${getChatTitle(chat)}"?`)) return;
    try {
      await api.deleteChat(getChatId(chat));
      await loadChats();
      if (selectedChatId === getChatId(chat)) {
        setSelectedChatId(null);
        setMessages([]);
      }
    } catch (e) {
      setError(e.message || "Не удалось удалить чат");
    }
  }

  async function handleTogglePin(chat) {
    try {
      await api.pinChat(getChatId(chat), !getChatPinned(chat));
      await loadChats();
    } catch (e) {
      setError(e.message || "Не удалось закрепить чат");
    }
  }

  async function handleSaveToMemory(pinned = false) {
    const selectedChat = chats.find((item) => getChatId(item) === selectedChatId);
    const lastAssistant = [...messages].reverse().find((m) => getMessageRole(m) === "assistant");
    const content = lastAssistant?.content || composer.trim();

    if (!content) return;

    try {
      await api.saveMemory({
        chat_id: selectedChatId,
        title: selectedChat ? getChatTitle(selectedChat) : "Чат",
        content,
        source: activeTopTab,
        pinned,
      });
      await loadMemory();
      setActiveLeftTab("memory");
    } catch (e) {
      setError(e.message || "Не удалось сохранить в памяти");
    }
  }

  async function handleDeleteMemory(id) {
    try {
      await api.deleteMemory(id);
      await loadMemory(activeLeftTab === "search" ? searchQuery : "");
    } catch (e) {
      setError(e.message || "Не удалось удалить из памяти");
    }
  }

  async function handleSend() {
    const content = composer.trim();
    if (!content) return;

    let chatId = selectedChatId;
    try {
      setSending(true);
      setError("");

      if (!chatId) {
        const created = await api.createChat(content.slice(0, 40) || "Новый чат");
        chatId = getChatId(created);
        setSelectedChatId(chatId);
        await loadChats();
      }

      await api.addMessage({
        chat_id: chatId,
        role: "user",
        content,
        metadata: {
          model: selectedModel,
          agent_profile: agentProfile,
          route: activeTopTab,
        },
      });

      setMessages((prev) => [
        ...prev,
        { role: "user", content },
      ]);
      setComposer("");

      const exec = await api.execute({
        chat_id: chatId,
        content,
        mode: activeTopTab,
        model: selectedModel,
        agent_profile: agentProfile,
      });

      if (exec?.assistant_content) {
        await api.addMessage({
          chat_id: chatId,
          role: "assistant",
          content: exec.assistant_content,
          metadata: {
            mode: exec.mode,
            model: exec.model,
            agent_profile: exec.agent_profile,
          },
        });
      }

      await loadMessages(chatId);
      await loadChats();
    } catch (e) {
      setError(e.message || "Не удалось отправить сообщение");
    } finally {
      setSending(false);
    }
  }

  const pinnedChats = useMemo(
    () => chats.filter((chat) => getChatPinned(chat)),
    [chats]
  );
  const regularChats = useMemo(
    () => chats.filter((chat) => !getChatPinned(chat)),
    [chats]
  );

  const topTabs = [
    { key: "chat", label: "Chat" },
    { key: "code", label: "Code" },
    { key: "research", label: "Research" },
    { key: "orchestrator", label: "Orchestrator" },
    { key: "image", label: "Text-to-Image" },
  ];

  return (
    <div className="jarvis-app">
      <aside className="sidebar">
        <button className="new-chat-btn" onClick={handleCreateChat}>
          <span className="plus">＋</span>
          <span>Новый чат</span>
        </button>

        <nav className="left-nav">
          <button
            className={`left-nav-item ${activeLeftTab === "search" ? "active" : ""}`}
            onClick={() => setActiveLeftTab("search")}
          >
            <span className="left-nav-icon">⌕</span>
            <span>Поиск</span>
          </button>

          <button
            className={`left-nav-item ${activeLeftTab === "chats" ? "active" : ""}`}
            onClick={() => setActiveLeftTab("chats")}
          >
            <span className="left-nav-icon">☰</span>
            <span>Чаты</span>
          </button>

          <button
            className={`left-nav-item ${activeLeftTab === "memory" ? "active" : ""}`}
            onClick={() => setActiveLeftTab("memory")}
          >
            <span className="left-nav-icon">★</span>
            <span>Память</span>
          </button>

          <button
            className={`left-nav-item ${activeLeftTab === "projects" ? "active" : ""}`}
            onClick={() => setActiveLeftTab("projects")}
          >
            <span className="left-nav-icon">▣</span>
            <span>Проекты</span>
          </button>

          <button
            className={`left-nav-item ${activeLeftTab === "settings" ? "active" : ""}`}
            onClick={() => setActiveLeftTab("settings")}
          >
            <span className="left-nav-icon">⚙</span>
            <span>Настройки</span>
          </button>
        </nav>

        <div className="left-content">
          {activeLeftTab === "chats" ? (
            <div className="chat-groups">
              {[
                { label: "Закреплённые", items: pinnedChats },
                { label: "Все чаты", items: regularChats },
              ].map((group) => (
                <section key={group.label} className="chat-group">
                  <div className="group-title">{group.label}</div>

                  {group.items.length ? (
                    group.items.map((chat) => (
                      <button
                        key={getChatId(chat)}
                        className={`chat-card ${selectedChatId === getChatId(chat) ? "active" : ""}`}
                        onClick={() => setSelectedChatId(getChatId(chat))}
                      >
                        <div className="chat-card-top">
                          <div className="chat-card-title">{getChatTitle(chat)}</div>
                          <div className="chat-card-actions" onClick={(e) => e.stopPropagation()}>
                            <button
                              className={`mini-icon ${getChatPinned(chat) ? "is-pinned" : ""}`}
                              onClick={() => handleTogglePin(chat)}
                              title="Закрепить в памяти"
                            >
                              📌
                            </button>
                            <button
                              className="mini-icon"
                              onClick={() => handleRenameChat(chat)}
                              title="Переименовать"
                            >
                              ✎
                            </button>
                            <button
                              className="mini-icon"
                              onClick={() => handleDeleteChat(chat)}
                              title="Удалить"
                            >
                              🗑
                            </button>
                          </div>
                        </div>
                        <div className="chat-card-meta">Память чатов</div>
                      </button>
                    ))
                  ) : (
                    <div className="empty-hint">Здесь пока пусто.</div>
                  )}
                </section>
              ))}
            </div>
          ) : null}

          {activeLeftTab === "search" ? (
            <div className="search-panel">
              <div className="group-title">Поиск по чатам, памяти и проектам</div>
              <input
                className="sidebar-input"
                placeholder="Ключевые слова..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />

              <div className="search-results">
                <div className="search-block">
                  <div className="search-title">Чаты</div>
                  {searchChats.length ? (
                    searchChats.map((item, index) => (
                      <button
                        key={`${getChatId(item) || "chat"}-${index}`}
                        className="search-item"
                        onClick={() => {
                          const id = getChatId(item);
                          if (id) {
                            setActiveLeftTab("chats");
                            setSelectedChatId(id);
                          }
                        }}
                      >
                        {getChatTitle(item)}
                      </button>
                    ))
                  ) : (
                    <div className="empty-hint">Нет совпадений по чатам.</div>
                  )}
                </div>

                <div className="search-block">
                  <div className="search-title">Память</div>
                  {memoryItems.length ? (
                    memoryItems.map((item) => (
                      <div key={item.id} className="search-item static">
                        {item.title || item.content.slice(0, 60)}
                      </div>
                    ))
                  ) : (
                    <div className="empty-hint">Нет совпадений по памяти.</div>
                  )}
                </div>

                <div className="search-block">
                  <div className="search-title">Проекты</div>
                  {searchProjects.length ? (
                    searchProjects.map((item, index) => (
                      <div key={`project-${index}`} className="search-item static">
                        {item?.name || item?.title || item?.path || "Проект"}
                      </div>
                    ))
                  ) : (
                    <div className="empty-hint">Нет совпадений по проектам.</div>
                  )}
                </div>
              </div>
            </div>
          ) : null}

          {activeLeftTab === "memory" ? (
            <MemoryPanel items={memoryItems} onDelete={handleDeleteMemory} />
          ) : null}

          {activeLeftTab === "projects" ? (
            <div className="placeholder-panel">
              <div className="group-title">Проекты</div>
              <div className="empty-hint">
                Здесь будет проектный контекст, файлы и project brain.
              </div>
            </div>
          ) : null}

          {activeLeftTab === "settings" ? (
            <div className="settings-panel">
              <div className="group-title">Настройки</div>

              <label className="settings-field">
                <span>LLM</span>
                <select
                  className="sidebar-select"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {models.map((model, index) => (
                    <option key={`${model.name}-${index}`} value={model.name}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="settings-field">
                <span>Профиль агента</span>
                <select
                  className="sidebar-select"
                  value={agentProfile}
                  onChange={(e) => setAgentProfile(e.target.value)}
                >
                  <option>Сбалансированный</option>
                  <option>Кодинг</option>
                  <option>Исследование</option>
                  <option>Мульти-агентный</option>
                </select>
              </label>
            </div>
          ) : null}
        </div>
      </aside>

      <section className="main-panel">
        <header className="top-bar">
          <div className="brand-title">Jarvis</div>

          <div className="top-center">
            <div className="jarvis-head">
              <div className="logo-badge">J</div>

              <select
                className="top-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {models.map((model, index) => (
                  <option key={`${model.name}-${index}`} value={model.name}>
                    {model.name}
                  </option>
                ))}
              </select>

              <select
                className="top-select"
                value={agentProfile}
                onChange={(e) => setAgentProfile(e.target.value)}
              >
                <option>Сбалансированный</option>
                <option>Кодинг</option>
                <option>Исследование</option>
                <option>Мульти-агентный</option>
              </select>

              <div className="top-tabs">
                {topTabs.map((tab) => (
                  <button
                    key={tab.key}
                    className={`top-tab ${activeTopTab === tab.key ? "active" : ""}`}
                    onClick={() => setActiveTopTab(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="top-right">
            {selectedModel} • {agentProfile}
          </div>
        </header>

        {activeTopTab === "code" ? (
          <div className="code-shell-wrap">
            <CodeWorkspace />
          </div>
        ) : (
          <div className="chat-area">
            <div className="chat-area-header">
              <div className="section-title">Чаты</div>
              <div className="chat-memory-actions">
                <button className="soft-btn" onClick={() => handleSaveToMemory(false)}>
                  Сохранить в памяти
                </button>
                <button className="soft-btn" onClick={() => handleSaveToMemory(true)}>
                  Закрепить в памяти
                </button>
              </div>
            </div>

            <div className="messages">
              {!selectedChatId && !messages.length ? (
                <div className="assistant-row">
                  <div className="assistant-avatar">✦</div>
                  <div className="assistant-bubble">
                    Jarvis готов. Начни новый чат или напиши сообщение.
                  </div>
                </div>
              ) : null}

              {messages.map((message, index) => {
                const role = getMessageRole(message);
                const content = getMessageContent(message);

                return (
                  <div
                    key={message?.id || `${role}-${index}`}
                    className={`message-row ${role === "user" ? "user" : "assistant"}`}
                  >
                    <div className={`message-avatar ${role === "user" ? "user" : "assistant"}`}>
                      {role === "user" ? "Ты" : "J"}
                    </div>
                    <div className={`message-bubble ${role === "user" ? "user" : "assistant"}`}>
                      {content}
                    </div>
                  </div>
                );
              })}
            </div>

            {error ? <div className="error-banner">{error}</div> : null}

            <div className="composer-wrap">
              <div className="composer-toolbar">
                <button className="attach-btn" title="Добавить">
                  ＋
                </button>
              </div>

              <textarea
                className="composer"
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
                placeholder="Напиши задачу... Jarvis сам выберет режим"
              />

              <div className="composer-footer">
                <div className="composer-meta">
                  Режим: {activeTopTab} • {selectedModel}
                </div>

                <button
                  className="send-btn"
                  onClick={handleSend}
                  disabled={sending || !composer.trim()}
                >
                  ➤
                </button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
