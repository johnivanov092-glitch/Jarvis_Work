/**
 * JarvisChatShell.jsx — v2
 *
 * Claude-like chat UI:
 *   • Compact sidebar (smaller font, аккуратные чаты)
 *   • Центрированный composer с выбором модели/профиля под ним
 *   • Топбар без описания профиля/модели
 *   • Стриминг + история + Markdown
 *   • Skills кнопки в настройках
 *   • PDF support (text extraction)
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { api, executeStream } from "../api/ide";
import IdeWorkspaceShell from "./IdeWorkspaceShell";
import MarkdownRenderer from "./MarkdownRenderer";
import "../styles/markdown.css";

const LIBRARY_KEY = "jarvis_library_files_v7";
const CHAT_CONTEXT_KEY = "jarvis_chat_context_map_v7";
const MAX_HISTORY_PAIRS = 10;

const PROFILE_DESCRIPTIONS = {
  "Универсальный": "Ясный, структурированный и профессиональный тон.",
  "Программист": "Код, исправления, архитектура, рефакторинг.",
  "Оркестратор": "Планирование, multi-agent, пайплайны.",
  "Исследователь": "Факты, источники, web-поиск.",
  "Аналитик": "Выводы, риски, декомпозиция.",
  "Сократ": "Обучение через вопросы.",
};

const SKILLS = [
  { id: "web_search", label: "🌐 Веб-поиск", desc: "Поиск в интернете для актуальной информации" },
  { id: "code_analysis", label: "🔍 Анализ кода", desc: "Разбор структуры и качества кода" },
  { id: "file_context", label: "📄 Контекст файлов", desc: "Использование загруженных файлов в ответах" },
  { id: "memory", label: "🧠 Память", desc: "Запоминание важных фактов между чатами" },
  { id: "python_exec", label: "🐍 Python", desc: "Выполнение Python-скриптов" },
  { id: "project_patch", label: "🔧 Патчинг", desc: "Автоматическое изменение файлов проекта" },
  { id: "pdf_reader", label: "📑 PDF Reader", desc: "Извлечение текста из PDF-файлов" },
  { id: "reflection", label: "🪞 Рефлексия", desc: "Двойная проверка ответов для сложных задач" },
];

/* ── helpers ──────────────────────────────────────────────── */
function loadJson(key, fb) { try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fb)); } catch { return fb; } }
function saveJson(key, v) { localStorage.setItem(key, JSON.stringify(v)); }
function loadLibraryFiles() { return loadJson(LIBRARY_KEY, []); }
function saveLibraryFiles(items) { saveJson(LIBRARY_KEY, items); }
function loadChatContextMap() { return loadJson(CHAT_CONTEXT_KEY, {}); }
function saveChatContextMap(v) { saveJson(CHAT_CONTEXT_KEY, v); }
function makeId(p = "id") { return `${p}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`; }
function deriveChatTitle(t) { const c = String(t || "").trim().replace(/\s+/g, " "); if (!c) return "Новый чат"; return c.length > 28 ? `${c.slice(0, 28)}…` : c; }

function normalizeErrorMessage(error, fallback = "Ошибка") {
  const v = error?.message ?? error?.detail ?? error;
  if (!v) return fallback;
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.map(i => normalizeErrorMessage(i, "")).filter(Boolean).join(" | ") || fallback;
  if (typeof v === "object") {
    if (typeof v.message === "string") return v.message;
    if (typeof v.msg === "string") return v.msg;
    try { return JSON.stringify(v); } catch { return fallback; }
  }
  return String(v);
}

async function fileToLibraryRecord(file) {
  let textPreview = "";
  const isText = file.type.startsWith("text/") || file.name.match(/\.(txt|md|json|js|jsx|ts|tsx|py|css|html|yml|yaml|xml|csv|log|ini|toml)$/i);
  const isPdf = file.name.match(/\.pdf$/i);

  if (isText) {
    try { textPreview = (await file.text()).slice(0, 12000); } catch {}
  } else if (isPdf) {
    // PDF text extraction — try backend
    try {
      const formData = new FormData();
      formData.append("file", file);
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"}/api/files/extract-text`, {
        method: "POST",
        body: formData,
      });
      if (resp.ok) {
        const data = await resp.json();
        textPreview = (data.text || "").slice(0, 12000);
      }
    } catch {}
  }

  return {
    id: makeId("lib"),
    name: file.name,
    size: file.size,
    type: file.type || "unknown",
    uploaded_at: new Date().toISOString(),
    preview: textPreview,
    use_in_context: true,
    source: "chat-upload",
  };
}

function getContextFilesForChat(chatId, lib) {
  if (!chatId) return [];
  const ids = (loadChatContextMap()[chatId]) || [];
  return lib.filter(i => ids.includes(i.id));
}

function buildHistoryForLLM(msgs) {
  if (!msgs?.length) return [];
  const pairs = msgs.filter(m => m.role === "user" || m.role === "assistant").map(m => ({ role: m.role, content: m.content || "" }));
  const limit = MAX_HISTORY_PAIRS * 2;
  return pairs.length > limit ? pairs.slice(-limit) : pairs;
}


/* ══════════════════════════════════════════════════════════════
   COMPONENT
   ══════════════════════════════════════════════════════════════ */

export default function JarvisChatShell() {
  const fileInputRef = useRef(null);
  const msgStreamRef = useRef(null);
  const textareaRef = useRef(null);
  const streamRef = useRef(null);

  const [mainTab, setMainTab] = useState("chat");
  const [sideTab, setSideTab] = useState("chats");

  const [model, setModel] = useState("qwen3:8b");
  const [modelOpts, setModelOpts] = useState([]);
  const [profile, setProfile] = useState("Универсальный");
  const [enabledSkills, setEnabledSkills] = useState(["web_search", "file_context", "memory", "pdf_reader"]);

  const [chats, setChats] = useState([]);
  const [chatId, setChatId] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sideSearch, setSideSearch] = useState("");
  const [libSearch, setLibSearch] = useState("");
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [working, setWorking] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");

  const [libraryFiles, setLibraryFiles] = useState(loadLibraryFiles());
  const [selLibId, setSelLibId] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [renameVal, setRenameVal] = useState("");

  useEffect(() => { init(); }, []);
  useEffect(() => { msgStreamRef.current && (msgStreamRef.current.scrollTop = msgStreamRef.current.scrollHeight); }, [messages, chatId, streamText]);
  useEffect(() => { if (!textareaRef.current) return; textareaRef.current.style.height = "36px"; textareaRef.current.style.height = `${Math.min(120, textareaRef.current.scrollHeight)}px`; }, [input]);

  async function init() {
    try {
      const [models, chatItems] = await Promise.all([api.listOllamaModels(), api.listChats()]);
      const ml = Array.isArray(models?.models) ? models.models : Array.isArray(models) ? models : [];
      setModelOpts(ml);
      const pref = ml.find(i => (i.name || i) === "qwen3:8b");
      if (pref) setModel(pref.name || pref); else if (ml.length) setModel(ml[0].name || ml[0]);
      if (chatItems?.length) { setChats(chatItems); setChatId(chatItems[0].id); setMessages(await api.getMessages({ chatId: chatItems[0].id }) || []); }
      else { const c = await newChat(true); if (c?.id) setMessages([]); }
    } catch (e) { setError(normalizeErrorMessage(e, "Ошибка инициализации")); }
  }

  async function loadChats(sel = "") { const items = await api.listChats(); setChats(items || []); if (sel) setChatId(sel); }

  async function newChat(silent = false) {
    try {
      setMessages([]); setInput(""); setRenaming(false); setStreamText(""); setStreaming(false);
      const c = await api.createChat({ title: "Новый чат", clean: true });
      await loadChats(c.id); setChatId(c.id); setMessages([]); setSideTab("chats");
      if (!silent) setError("");
      return c;
    } catch (e) { setError(normalizeErrorMessage(e)); return null; }
  }

  async function openChat(id) {
    try {
      streamRef.current?.abort(); streamRef.current = null; setStreamText(""); setStreaming(false);
      setChatId(id); setMessages(await api.getMessages({ chatId: id }) || []); setSideTab("chats"); setMainTab("chat"); setRenaming(false);
    } catch (e) { setError(normalizeErrorMessage(e)); }
  }

  async function renameActive() {
    const t = renameVal.trim(); if (!t || !chatId) return;
    try { await api.renameChat({ id: chatId, title: t }); await loadChats(chatId); setRenaming(false); } catch (e) { setError(normalizeErrorMessage(e)); }
  }

  async function autoRename(text) {
    const active = chats.find(c => c.id === chatId);
    if (!chatId || !active || (active.title && active.title !== "Новый чат")) return;
    try { await api.renameChat({ id: chatId, title: deriveChatTitle(text) }); await loadChats(chatId); } catch {}
  }

  /* ── SEND ─────────────────────────────────────────────────── */
  async function handleSend() {
    const text = input.trim();
    if (!text || !chatId || working) return;
    try {
      setWorking(true); setStreaming(true); setStreamText(""); setError("");
      const userMsg = await api.addMessage({ chatId, role: "user", content: text });
      setMessages(prev => [...prev, userMsg]); setInput(""); await autoRename(text);

      const history = buildHistoryForLLM(messages);
      const ctxFiles = getContextFilesForChat(chatId, libraryFiles).filter(f => f.use_in_context);
      const ctxPrefix = ctxFiles.length ? "\n\nКонтекст из библиотеки:\n" + ctxFiles.map(f => `- ${f.name}${f.preview ? `: ${f.preview.slice(0, 1200)}` : ""}`).join("\n") : "";

      let fullText = "";
      const ctrl = executeStream(
        { model_name: model, profile_name: profile, user_input: `${text}${ctxPrefix}`, history, use_memory: enabledSkills.includes("memory"), use_library: enabledSkills.includes("file_context") },
        {
          onToken(t) { fullText += t; setStreamText(fullText); },
          onPhase(ev) { if (ev.phase === "reflection_replace" && ev.full_text) { fullText = ev.full_text; setStreamText(fullText); } },
          async onDone({ full_text }) {
            const final = full_text || fullText;
            try { const p = await api.addMessage({ chatId, role: "assistant", content: final }); setMessages(prev => [...prev, p]); }
            catch { setMessages(prev => [...prev, { id: `a-${Date.now()}`, role: "assistant", content: final }]); }
            setStreamText(""); setStreaming(false); setWorking(false); streamRef.current = null;
          },
          onError(msg) { setError(msg); setStreamText(""); setStreaming(false); setWorking(false); streamRef.current = null; },
        }
      );
      streamRef.current = ctrl;
    } catch (e) { setError(normalizeErrorMessage(e)); setStreamText(""); setStreaming(false); setWorking(false); }
  }

  async function deleteChat(id) {
    try {
      await api.deleteChat({ id }); const next = chats.filter(c => c.id !== id); setChats(next);
      if (chatId === id) { if (next.length) await openChat(next[0].id); else { const c = await newChat(true); if (c?.id) await openChat(c.id); } }
    } catch (e) { setError(normalizeErrorMessage(e)); }
  }

  async function pinChat(id, pinned) { try { await api.pinChat({ id, pinned: !pinned }); await loadChats(chatId); } catch (e) { setError(normalizeErrorMessage(e)); } }
  async function saveToMemory(id, saved) { try { await api.saveChatToMemory({ id, saved: !saved }); await loadChats(chatId); } catch (e) { setError(normalizeErrorMessage(e)); } }

  /* ── Files ────────────────────────────────────────────────── */
  async function handleFiles(fileList) {
    const files = Array.from(fileList || []); if (!files.length) return;
    const records = []; for (const f of files) records.push(await fileToLibraryRecord(f));
    const next = [...records, ...libraryFiles]; setLibraryFiles(next); saveLibraryFiles(next); setSideTab("library"); setSelLibId(records[0]?.id || "");
    if (chatId) { const map = loadChatContextMap(); map[chatId] = Array.from(new Set([...records.map(r => r.id), ...(map[chatId] || [])])); saveChatContextMap(map); }
  }

  function onDrop(e) { e.preventDefault(); e.stopPropagation(); setDragActive(false); handleFiles(e.dataTransfer.files); }
  function onDragOver(e) { e.preventDefault(); e.stopPropagation(); setDragActive(true); }
  function onDragLeave(e) { e.preventDefault(); e.stopPropagation(); setDragActive(false); }
  function removeLib(id) {
    const next = libraryFiles.filter(i => i.id !== id); setLibraryFiles(next); saveLibraryFiles(next);
    const map = loadChatContextMap(); const up = Object.fromEntries(Object.entries(map).map(([k, v]) => [k, (v || []).filter(x => x !== id)])); saveChatContextMap(up);
    if (selLibId === id) setSelLibId(next[0]?.id || "");
  }
  function toggleLibCtx(id, on) {
    const next = libraryFiles.map(i => i.id === id ? { ...i, use_in_context: on } : i); setLibraryFiles(next); saveLibraryFiles(next);
    if (!chatId) return; const map = loadChatContextMap(); const s = new Set(map[chatId] || []); on ? s.add(id) : s.delete(id); map[chatId] = Array.from(s); saveChatContextMap(map);
  }
  function toggleSkill(id) { setEnabledSkills(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]); }

  function handleKeyDown(e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }

  /* ── memos ────────────────────────────────────────────────── */
  const filteredChats = useMemo(() => { const q = sideSearch.trim().toLowerCase(); return q ? chats.filter(c => (c.title || "").toLowerCase().includes(q)) : chats; }, [sideSearch, chats]);
  const pinnedChats = useMemo(() => filteredChats.filter(c => c.pinned), [filteredChats]);
  const regularChats = useMemo(() => filteredChats.filter(c => !c.pinned), [filteredChats]);
  const memoryChats = useMemo(() => chats.filter(c => c.memory_saved), [chats]);
  const filteredLib = useMemo(() => { const q = libSearch.trim().toLowerCase(); return q ? libraryFiles.filter(i => `${i.name} ${i.preview || ""}`.toLowerCase().includes(q)) : libraryFiles; }, [libSearch, libraryFiles]);
  const selLibItem = useMemo(() => libraryFiles.find(i => i.id === selLibId) || libraryFiles[0] || null, [libraryFiles, selLibId]);
  const ctxFiles = useMemo(() => chatId ? getContextFilesForChat(chatId, libraryFiles).filter(f => f.use_in_context) : [], [chatId, libraryFiles]);

  if (mainTab === "code") return <IdeWorkspaceShell libraryFiles={libraryFiles} setLibraryFiles={setLibraryFiles} onBackToChat={() => setMainTab("chat")} />;

  /* ══════════════════════════════════════════════════════════
     RENDER
     ══════════════════════════════════════════════════════════ */
  return (
    <div className="jarvis-shell">
      {/* ── SIDEBAR ───────────────────────────────────────── */}
      <aside className="jarvis-sidebar">
        <button className="sidebar-newchat-btn" onClick={() => newChat(false)}>+ Новый чат</button>

        <div className="sidebar-nav">
          {[["chats","☰ Чаты"],["memory","★ Память"],["settings","⚙ Настройки"],["library","📚 Файлы"]].map(([k,l]) => (
            <button key={k} className={`sidebar-nav-item ${sideTab === k ? "active" : ""}`} onClick={() => setSideTab(k)}>{l}</button>
          ))}
        </div>

        <div className="sidebar-nav-item search-shell">
          <span style={{opacity:0.4,fontSize:11}}>⌕</span>
          <input className="sidebar-search-input" value={sideSearch} onChange={e => setSideSearch(e.target.value)} placeholder="Поиск" />
        </div>

        {sideTab === "chats" && (
          <div className="chat-list" style={{flex:1,minHeight:0}}>
            {pinnedChats.length > 0 && <div className="sidebar-section-title">Закреплённые</div>}
            {pinnedChats.map(c => (
              <button key={c.id} className={`chat-list-item simple ${chatId === c.id ? "active" : ""}`} onClick={() => openChat(c.id)}>
                <span className="chat-list-title truncate">{c.title || "Новый чат"}</span>
              </button>
            ))}
            {regularChats.length > 0 && <div className="sidebar-section-title">Чаты</div>}
            {regularChats.map(c => (
              <button key={c.id} className={`chat-list-item simple ${chatId === c.id ? "active" : ""}`} onClick={() => openChat(c.id)}>
                <span className="chat-list-title truncate">{c.title || "Новый чат"}</span>
              </button>
            ))}
            {!filteredChats.length && <div className="sidebar-empty">Пусто</div>}
          </div>
        )}
        {sideTab === "memory" && (
          <div className="chat-list" style={{flex:1,minHeight:0}}>
            {memoryChats.length ? memoryChats.map(c => (
              <button key={c.id} className={`chat-list-item simple ${chatId === c.id ? "active" : ""}`} onClick={() => openChat(c.id)}>
                <span className="chat-list-title truncate">{c.title || "Новый чат"}</span>
              </button>
            )) : <div className="sidebar-empty">Нет сохранённых чатов</div>}
          </div>
        )}
        {sideTab === "settings" && <div className="sidebar-empty">Настройки в центре →</div>}
        {sideTab === "library" && <div className="sidebar-empty">Файлы в центре →</div>}
      </aside>

      {/* ── MAIN ──────────────────────────────────────────── */}
      <main className="jarvis-main">
        <div className="jarvis-topbar slim">
          <div className="jarvis-brand">Jarvis</div>
          <div className="topbar-tabs">
            <button className={`soft-btn ${mainTab === "chat" ? "active" : ""}`} onClick={() => setMainTab("chat")}>Chat</button>
            <button className={`soft-btn ${mainTab === "code" ? "active" : ""}`} onClick={() => setMainTab("code")}>Code</button>
          </div>
        </div>

        <div className="chat-page">
          {/* Header actions */}
          <div className="chat-header-row">
            <div className="chat-page-title">
              {sideTab === "chats" && "Чат"}{sideTab === "memory" && "Память"}{sideTab === "settings" && "Настройки"}{sideTab === "library" && "Библиотека"}
            </div>
            {sideTab === "chats" && chatId && (
              <div className="chat-header-actions icon-actions" style={{display:"flex"}}>
                <div className={`working-chip ${working ? "active" : ""}`}>{working ? "⏳ Работает" : "○ Готов"}</div>
                <button className="soft-btn icon-btn" title="Память" onClick={() => saveToMemory(chatId, chats.find(c => c.id === chatId)?.memory_saved)}>🧠</button>
                <button className="soft-btn icon-btn" title="Закрепить" onClick={() => pinChat(chatId, chats.find(c => c.id === chatId)?.pinned)}>📌</button>
                <button className="soft-btn icon-btn" title="Переименовать" onClick={() => { setRenaming(true); setRenameVal(chats.find(c => c.id === chatId)?.title || ""); }}>✎</button>
                <button className="soft-btn icon-btn" title="Удалить" onClick={() => deleteChat(chatId)}>🗑</button>
              </div>
            )}
          </div>

          {renaming && sideTab === "chats" && (
            <div className="rename-bar">
              <input value={renameVal} onChange={e => setRenameVal(e.target.value)} className="rename-input wide" placeholder="Название" />
              <button className="mini-btn" onClick={renameActive}>OK</button>
            </div>
          )}

          {/* ── SETTINGS TAB ──────────────────────────────── */}
          {sideTab === "settings" ? (
            <div className="settings-main-card">
              <div className="settings-tile-grid">
                <div className="settings-tile">
                  <div className="settings-title">Модель</div>
                  <select value={model} onChange={e => setModel(e.target.value)} className="topbar-select full dark-select">
                    {(modelOpts?.length ? modelOpts : [{ name: model }]).map(i => (
                      <option key={i.name || i} value={i.name || i}>{i.name || i}</option>
                    ))}
                  </select>
                </div>
                <div className="settings-tile">
                  <div className="settings-title">Профиль</div>
                  <select value={profile} onChange={e => setProfile(e.target.value)} className="topbar-select full dark-select">
                    {Object.keys(PROFILE_DESCRIPTIONS).map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                  <div className="settings-desc">{PROFILE_DESCRIPTIONS[profile]}</div>
                </div>
              </div>

              {/* Skills */}
              <div style={{marginTop: 18}}>
                <div className="settings-title" style={{marginBottom: 8}}>Skills</div>
                <div className="settings-desc" style={{marginBottom: 10}}>Включи или выключи возможности Jarvis</div>
                <div className="skills-grid">
                  {SKILLS.map(s => (
                    <button key={s.id} className={`skill-chip ${enabledSkills.includes(s.id) ? "active" : ""}`} onClick={() => toggleSkill(s.id)} title={s.desc}>
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="settings-description-list">
                <div className="content-card-title" style={{marginTop:18}}>Профили</div>
                <ul className="settings-list">
                  {Object.entries(PROFILE_DESCRIPTIONS).map(([n,t]) => <li key={n}><strong>{n}:</strong> {t}</li>)}
                </ul>
              </div>
            </div>

          /* ── LIBRARY TAB ─────────────────────────────────── */
          ) : sideTab === "library" ? (
            <div className="library-table-view">
              <div className={`upload-dropzone ${dragActive ? "active" : ""}`} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop} onClick={() => fileInputRef.current?.click()}>
                Перетащи файлы сюда (PDF, TXT, код, и др.)
              </div>
              <div className="library-search-row">
                <span className="library-search-icon">⌕</span>
                <input value={libSearch} onChange={e => setLibSearch(e.target.value)} placeholder="Поиск" className="library-search-input" />
              </div>
              <input ref={fileInputRef} type="file" multiple hidden accept=".txt,.md,.json,.js,.jsx,.ts,.tsx,.py,.css,.html,.yml,.yaml,.xml,.csv,.log,.pdf,.toml,.ini,.rs,.go,.java,.c,.cpp,.h,.rb,.sh,.bat" onChange={e => handleFiles(e.target.files)} />
              <div className="library-table">
                <div className="library-table-row header"><div>Имя</div><div>Тип</div><div>Размер</div><div>Контекст</div><div></div></div>
                {filteredLib.length ? filteredLib.map(i => (
                  <div key={i.id} className={`library-table-row ${selLibId === i.id ? "active" : ""}`} onClick={() => setSelLibId(i.id)}>
                    <div className="table-name">{i.name}</div>
                    <div>{i.type.split("/").pop()}</div>
                    <div>{Math.round(i.size / 1024) || 0}K</div>
                    <div><input type="checkbox" checked={!!i.use_in_context} onChange={e => { e.stopPropagation(); toggleLibCtx(i.id, e.target.checked); }} /></div>
                    <div><button className="mini-icon-btn" onClick={e => { e.stopPropagation(); removeLib(i.id); }}>✕</button></div>
                  </div>
                )) : <div className="sidebar-empty" style={{padding:10}}>Нет файлов</div>}
              </div>
              {selLibItem && (
                <div className="content-card">
                  <div className="content-card-title">{selLibItem.name}</div>
                  <div className="content-card-text">Тип: {selLibItem.type} · {Math.round(selLibItem.size/1024)||0} KB</div>
                  {selLibItem.preview ? <pre className="library-preview">{selLibItem.preview}</pre> : <div className="content-card-text" style={{marginTop:6}}>Превью недоступно</div>}
                </div>
              )}
            </div>

          /* ── MEMORY TAB ──────────────────────────────────── */
          ) : sideTab === "memory" ? (
            <div style={{padding:16,overflow:"auto",flex:1}}>
              {memoryChats.length ? memoryChats.map(c => (
                <button key={c.id} className="content-card content-card-button" style={{marginBottom:8,display:"block"}} onClick={() => openChat(c.id)}>
                  <div className="content-card-title">{c.title}</div>
                  <div className="content-card-text">Открыть</div>
                </button>
              )) : <div className="sidebar-empty">Нет сохранённых чатов</div>}
            </div>

          /* ── CHAT TAB ────────────────────────────────────── */
          ) : (
            <>
              {ctxFiles.length > 0 && (
                <div className="context-bar">
                  <div className="context-bar-title">В контексте</div>
                  <div className="context-tags">{ctxFiles.map(f => <span key={f.id} className="context-tag">{f.name}</span>)}</div>
                </div>
              )}

              {messages.length === 0 && !streaming && (
                <div style={{flex:1,display:"flex",alignItems:"center",justifyContent:"center"}}>
                  <div style={{textAlign:"center",color:"var(--text-muted)"}}>
                    <div style={{fontSize:28,marginBottom:8,opacity:0.2}}>✺</div>
                    <div style={{fontSize:14}}>Чем могу помочь?</div>
                  </div>
                </div>
              )}

              <div className="message-stream compact-stream" ref={msgStreamRef}>
                {messages.map(msg => (
                  <div key={msg.id} className={`message-row ${msg.role}`}>
                    <div className="message-bubble smaller-text">
                      {msg.role === "assistant" ? <MarkdownRenderer content={msg.content} /> : msg.content}
                    </div>
                  </div>
                ))}
                {streaming && streamText && (
                  <div className="message-row assistant">
                    <div className="message-bubble smaller-text streaming-cursor"><MarkdownRenderer content={streamText} /></div>
                  </div>
                )}
                {streaming && !streamText && (
                  <div className="message-row assistant">
                    <div className="message-bubble smaller-text" style={{opacity:0.4}}>Jarvis думает...</div>
                  </div>
                )}
              </div>

              {error && <div className="error-banner smaller-text">{error}</div>}

              {/* ── CENTERED COMPOSER ──────────────────────── */}
              <div className="composer-wrap" onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
                <div className={`chat-input-shell ${dragActive ? "drag-active" : ""}`}>
                  <button className="input-plus-btn" onClick={() => fileInputRef.current?.click()}>+</button>
                  <textarea ref={textareaRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Напиши сообщение..." className="chat-textarea" />
                  <button className="send-btn" onClick={handleSend} disabled={working}>{working ? "⏳" : "➤"}</button>
                  <input ref={fileInputRef} type="file" multiple hidden accept=".txt,.md,.json,.js,.jsx,.ts,.tsx,.py,.css,.html,.yml,.yaml,.xml,.csv,.log,.pdf,.toml,.ini,.rs,.go,.java,.c,.cpp,.h,.rb,.sh,.bat" onChange={e => handleFiles(e.target.files)} />
                </div>
                <div className="composer-selectors">
                  <select value={model} onChange={e => setModel(e.target.value)} className="composer-select">
                    {(modelOpts?.length ? modelOpts : [{ name: model }]).map(i => <option key={i.name || i} value={i.name || i}>{i.name || i}</option>)}
                  </select>
                  <select value={profile} onChange={e => setProfile(e.target.value)} className="composer-select">
                    {Object.keys(PROFILE_DESCRIPTIONS).map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
