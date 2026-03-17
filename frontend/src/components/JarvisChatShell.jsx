import { useEffect, useMemo, useState } from "react";
import { api } from "../api/ide";

const DEFAULT_AGENT_PROFILE = "Сбалансированный";

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
  const [searchData, setSearchData] = useState({ chats: [], projects: [] });
  const [loadingChats, setLoadingChats] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("qwen3:8b");
  const [agentProfile, setAgentProfile] = useState(DEFAULT_AGENT_PROFILE);
  const [error, setError] = useState("");

  useEffect(() => {
    loadBootData();
  }, []);

  useEffect(() => {
    if (selectedChatId) {
      loadMessages(selectedChatId);
    } else {
      setMessages([]);
    }
  }, [selectedChatId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (activeLeftTab === "search" && searchQuery.trim()) {
        runSearch(searchQuery.trim());
      } else if (!searchQuery.trim()) {
        setSearchData({ chats: [], projects: [] });
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, activeLeftTab]);

  async function loadBootData() {
    setError("");
    try {
      await Promise.all([loadChats(), loadSettings(), loadModels()]);
    } catch (e) {
      setError(e.message || "Не удалось загрузить интерфейс");
    }
  }

  async function loadChats() {
    setLoadingChats(true);
    try {
      const payload = await api.listChats();
      const items = normalizeArray(payload);
      setChats(items);

      if (!selectedChatId && items.length) {
        setSelectedChatId(getChatId(items[0]));
      }
    } finally {
      setLoadingChats(false);
    }
  }

  async function loadModels() {
    try {
      const payload = await api.getModels();
      const items = normalizeArray(payload);
      const prepared = items.map((item) =>
        typeof item === "string" ? { name: item } : item
      );
      setModels(prepared);
      if (prepared[0]?.name && !selectedModel) {
        setSelectedModel(prepared[0].name);
      }
    } catch {
      setModels([{ name: "qwen3:8b" }]);
    }
  }

  async function loadSettings() {
    try {
      const payload = await api.getSettings();
      setSelectedModel(
        payload?.model_default || payload?.default_model || "qwen3:8b"
      );
      setAgentProfile(payload?.agent_profile || DEFAULT_AGENT_PROFILE);
    } catch {
      setSelectedModel("qwen3:8b");
      setAgentProfile(DEFAULT_AGENT_PROFILE);
    }
  }

  async function loadMessages(chatId) {
    setLoadingMessages(true);
    setError("");
    try {
      const payload = await api.getMessages(chatId);
      setMessages(normalizeArray(payload));
    } catch (e) {
      setError(e.message || "Не удалось загрузить сообщения");
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }

  async function runSearch(query) {
    try {
      const payload = await api.searchEverything(query);
      setSearchData(payload);
    } catch {
      setSearchData({ chats: [], projects: [] });
    }
  }

  async function handleCreateChat() {
    setError("");
    try {
      const payload = await api.createChat("Новый чат");
      const createdId = getChatId(payload);
      await loadChats();
      if (createdId) {
        setSelectedChatId(createdId);
      }
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
    const ok = window.confirm(`Удалить чат "${getChatTitle(chat)}"?`);
    if (!ok) return;

    try {
      await api.deleteChat(getChatId(chat));
      const deletedId = getChatId(chat);
      await loadChats();

      if (selectedChatId === deletedId) {
        const next = chats.find((item) => getChatId(item) !== deletedId);
        setSelectedChatId(next ? getChatId(next) : null);
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

      const localUserMessage = {
        id: `local-user-${Date.now()}`,
        role: "user",
        content,
      };
      setMessages((prev) => [...prev, localUserMessage]);
      setComposer("");

      await api.addMessage({
        chat_id: chatId,
        role: "user",
        content,
        metadata: {
          saved_in_memory: true,
          pinned_in_memory: false,
          model: selectedModel,
          agent_profile: agentProfile,
          route: activeTopTab,
        },
      });

      let assistantText =
        "Jarvis получил сообщение. Подключи свой текущий обработчик ответа, если нужно вернуть полный LLM-ответ.";

      try {
        await api.addMessage({
          chat_id: chatId,
          role: "assistant",
          content: assistantText,
          metadata: {
            saved_in_memory: true,
            pinned_in_memory: false,
            model: selectedModel,
            agent_profile: agentProfile,
            route: activeTopTab,
          },
        });
      } catch {
        // Если backend сам генерирует assistant message, не дублируем ошибку
      }

      await loadMessages(chatId);
      await loadChats();
    } catch (e) {
      setError(e.message || "Не удалось отправить сообщение");
    } finally {
      setSending(false);
    }
  }

  async function handleSaveCurrentChatToMemory() {
    const chat = chats.find((item) => getChatId(item) === selectedChatId);
    if (!chat) return;

    try {
      await api.pinChat(getChatId(chat), true);
      await loadChats();
    } catch (e) {
      setError(e.message || "Не удалось сохранить чат в памяти");
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

  const chatGroups = [
    { label: "Закреплённые", items: pinnedChats },
    { label: "Все чаты", items: regularChats },
  ];

  const selectedChat = chats.find((chat) => getChatId(chat) === selectedChatId);

  const topTabs = [
    { key: "chat", label: "Chat" },
    { key: "code", label: "Code" },
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
              {chatGroups.map((group) => (
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
                        <div className="chat-card-meta">
                          Память чатов
                        </div>
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
              <div className="group-title">Поиск по чатам и проектам</div>
              <input
                className="sidebar-input"
                placeholder="Ключевые слова..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />

              <div className="search-results">
                <div className="search-block">
                  <div className="search-title">Чаты</div>
                  {searchData.chats.length ? (
                    searchData.chats.map((item, index) => (
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
                  <div className="search-title">Проекты</div>
                  {searchData.projects.length ? (
                    searchData.projects.map((item, index) => (
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

          {activeLeftTab === "projects" ? (
            <div className="placeholder-panel">
              <div className="group-title">Проекты</div>
              <div className="empty-hint">
                Этот раздел оставлен под список проектов и контекст проекта.
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
                  {(models.length ? models : [{ name: "qwen3:8b" }]).map((model, index) => (
                    <option key={`${model.name || model}-${index}`} value={model.name || model}>
                      {model.name || model}
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
          <div className="brand-title">Jarvis Агент ИИ</div>

          <div className="top-center">
            <div className="jarvis-head">
              <div className="logo-badge">J</div>

              <select className="top-select" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
                {(models.length ? models : [{ name: "qwen3:8b" }]).map((model, index) => (
                  <option key={`${model.name || model}-${index}`} value={model.name || model}>
                    {model.name || model}
                  </option>
                ))}
              </select>

              <select className="top-select" value={agentProfile} onChange={(e) => setAgentProfile(e.target.value)}>
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

        <div className="chat-area">
          <div className="chat-area-header">
            <div className="section-title">Чаты</div>
            <div className="chat-memory-actions">
              <button className="soft-btn" onClick={handleSaveCurrentChatToMemory} disabled={!selectedChat}>
                Сохранить в памяти
              </button>
              <button
                className="soft-btn"
                onClick={() => selectedChat && handleTogglePin(selectedChat)}
                disabled={!selectedChat}
              >
                {selectedChat && getChatPinned(selectedChat) ? "Открепить" : "Закрепить в памяти"}
              </button>
            </div>
          </div>

          <div className="messages">
            {!selectedChat && !messages.length ? (
              <div className="assistant-row">
                <div className="assistant-avatar">✦</div>
                <div className="assistant-bubble">
                  Jarvis готов. <strong>Начни новый чат</strong> или напиши сообщение.
                </div>
              </div>
            ) : null}

            {loadingMessages ? <div className="empty-hint">Загрузка сообщений...</div> : null}

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
              <button className="attach-btn" title="Добавить">＋</button>
            </div>

            <textarea
              className="composer"
              value={composer}
              onChange={(e) => setComposer(e.target.value)}
              placeholder="Напиши задачу... Jarvis сам выберет режим"
            />

            <div className="composer-footer">
              <div className="composer-meta">
                {selectedModel} • {agentProfile}
              </div>

              <button className="send-btn" onClick={handleSend} disabled={sending || !composer.trim()}>
                ➤
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
