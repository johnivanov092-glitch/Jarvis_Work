import { useEffect, useState } from "react";
import { api } from "../api/ide";
import { FileCode2, RefreshCw } from "lucide-react";

export default function FileExplorerPanel({ onOpen }) {
  const [files, setFiles] = useState([]);

  async function load() {
    try {
      const s = await api.projectSnapshot();
      setFiles(s.files || []);
    } catch {
      setFiles([]);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="panel">
      <div className="panel-head">
        <b>Files</b>
        <button onClick={load}><RefreshCw size={14} /></button>
      </div>

      <div className="file-list">
        {files.map((f) => (
          <button key={f.path} onClick={() => onOpen?.(f)} className="file-item">
            <FileCode2 size={14} /> {f.path}
          </button>
        ))}
      </div>
    </div>
  );
}
