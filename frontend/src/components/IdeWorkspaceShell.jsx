import { useState } from "react";
import FileExplorerPanel from "./FileExplorerPanel";
import TerminalPanel from "./TerminalPanel";
import { api } from "../api/ide";

export default function IdeWorkspaceShell() {
  const [prompt, setPrompt] = useState("Build safe patch pipeline");
  const [file, setFile] = useState(null);
  const [code, setCode] = useState("");

  async function run() {
    try {
      await api.runGoal(prompt);
      alert("Goal sent");
    } catch (e) {
      alert("Backend not responding");
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h3>Jarvis IDE</h3>
        <FileExplorerPanel onOpen={(f) => {
          setFile(f);
          setCode("// opened file: " + f.path);
        }} />
      </aside>

      <main className="main">
        <div className="topbar">
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          <button onClick={run}>Run</button>
        </div>

        <div className="workspace">
          <div className="editor">
            <div className="editor-head">{file?.path || "No file selected"}</div>
            <textarea value={code} onChange={(e) => setCode(e.target.value)} />
          </div>

          <div className="right">
            <TerminalPanel />
          </div>
        </div>
      </main>
    </div>
  );
}
