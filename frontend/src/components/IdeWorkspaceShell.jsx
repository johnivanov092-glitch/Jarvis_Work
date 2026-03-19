/**
 * IdeWorkspaceShell.jsx — v2
 *
 * Drag-and-drop файловая панель вместо проектного браузера.
 * Синхронизируется с библиотекой (libraryFiles prop).
 * Поддержка PDF: показывает превью извлечённого текста.
 */

import { useMemo, useRef, useState } from "react";

const LIBRARY_KEY = "jarvis_library_files_v7";
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function makeId(p = "id") {
  return `${p}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadJson(key, fb) { try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fb)); } catch { return fb; } }
function saveJson(key, v) { localStorage.setItem(key, JSON.stringify(v)); }

async function fileToRecord(file) {
  let textPreview = "";
  const isText = file.type.startsWith("text/") || file.name.match(/\.(txt|md|json|js|jsx|ts|tsx|py|css|html|yml|yaml|xml|csv|log|ini|toml|rs|go|java|c|cpp|h|rb|sh|bat)$/i);
  const isPdf = file.name.match(/\.pdf$/i);

  if (isText) {
    try { textPreview = (await file.text()).slice(0, 12000); } catch {}
  } else if (isPdf) {
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await fetch(`${API_BASE}/api/files/extract-text`, { method: "POST", body: fd });
      if (r.ok) { const d = await r.json(); textPreview = (d.text || "").slice(0, 12000); }
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
    source: "code-upload",
  };
}


export default function IdeWorkspaceShell({ libraryFiles: propFiles, setLibraryFiles: propSetFiles, onBackToChat }) {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedId, setSelectedId] = useState("");

  // Sync with parent or local
  const libraryFiles = propFiles || loadJson(LIBRARY_KEY, []);
  function setLibraryFiles(next) {
    if (propSetFiles) propSetFiles(next);
    saveJson(LIBRARY_KEY, next);
  }

  const selectedFile = useMemo(() => libraryFiles.find(f => f.id === selectedId) || null, [libraryFiles, selectedId]);

  async function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const records = [];
    for (const f of files) records.push(await fileToRecord(f));
    const next = [...records, ...libraryFiles];
    setLibraryFiles(next);
    setSelectedId(records[0]?.id || "");
  }

  function removeFile(id) {
    const next = libraryFiles.filter(f => f.id !== id);
    setLibraryFiles(next);
    if (selectedId === id) setSelectedId(next[0]?.id || "");
  }

  function onDrop(e) { e.preventDefault(); e.stopPropagation(); setDragActive(false); handleFiles(e.dataTransfer.files); }
  function onDragOver(e) { e.preventDefault(); e.stopPropagation(); setDragActive(true); }
  function onDragLeave(e) { e.preventDefault(); e.stopPropagation(); setDragActive(false); }

  return (
    <div className="ide-shell">
      {/* Toolbar */}
      <div className="ide-toolbar">
        <button onClick={onBackToChat} className="soft-btn" style={{border:"1px solid var(--border)"}}>← Chat</button>
        <div style={{fontSize:14,fontWeight:600}}>Code · Файлы</div>
        <div style={{marginLeft:"auto",fontSize:11,color:"var(--text-muted)"}}>{libraryFiles.length} файлов в библиотеке</div>
      </div>

      {/* Grid: drop zone + file list | preview */}
      <div className="ide-grid">
        <div style={{display:"flex",flexDirection:"column",gap:12,minHeight:0}}>
          {/* Drop zone */}
          <div
            className={`drop-panel ${dragActive ? "active" : ""}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{minHeight: libraryFiles.length ? 100 : 200}}
          >
            <div className="drop-panel-icon">📂</div>
            <div className="drop-panel-text">
              Перетащи файлы сюда<br/>
              <span style={{fontSize:10,opacity:0.6}}>PDF, код, текст, конфиги</span>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            accept=".txt,.md,.json,.js,.jsx,.ts,.tsx,.py,.css,.html,.yml,.yaml,.xml,.csv,.log,.pdf,.toml,.ini,.rs,.go,.java,.c,.cpp,.h,.rb,.sh,.bat"
            onChange={e => handleFiles(e.target.files)}
          />

          {/* File list */}
          <div className="file-list-panel" style={{flex:1}}>
            <div className="file-list-header">Файлы ({libraryFiles.length})</div>
            <div className="file-list-body">
              {libraryFiles.length ? libraryFiles.map(f => (
                <div
                  key={f.id}
                  className="file-list-item"
                  style={{background: selectedId === f.id ? "var(--bg-surface-active)" : undefined, cursor:"pointer"}}
                  onClick={() => setSelectedId(f.id)}
                >
                  <span style={{marginRight:6,fontSize:13}}>
                    {f.name.match(/\.pdf$/i) ? "📑" : f.name.match(/\.(js|jsx|ts|tsx|py|rs|go|java|c|cpp|h|rb)$/i) ? "📄" : "📝"}
                  </span>
                  <span className="file-list-name">{f.name}</span>
                  <span className="file-list-size">{Math.round(f.size/1024)||0}K</span>
                  <button className="file-list-remove" onClick={e => { e.stopPropagation(); removeFile(f.id); }} title="Удалить">✕</button>
                </div>
              )) : (
                <div style={{padding:12,fontSize:11,color:"var(--text-muted)",textAlign:"center"}}>
                  Загрузи файлы через drag-and-drop
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Preview */}
        <div className="file-preview-panel">
          <div className="file-preview-header">
            {selectedFile ? (
              <>
                <span>{selectedFile.name}</span>
                <span style={{marginLeft:8,fontSize:10,opacity:0.5}}>{selectedFile.type} · {Math.round(selectedFile.size/1024)||0} KB</span>
              </>
            ) : "Выбери файл слева"}
          </div>
          <div className="file-preview-body">
            {selectedFile?.preview ? selectedFile.preview : (
              selectedFile ? "Превью недоступно для этого типа файла" : "←  Нажми на файл для просмотра"
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
