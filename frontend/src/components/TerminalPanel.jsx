import { useEffect, useState } from "react";

export default function TerminalPanel() {
  const [lines, setLines] = useState([
    "[jarvis] runtime ready",
    "[supervisor] idle",
  ]);

  useEffect(() => {
    const t = setInterval(() => {
      setLines((l) => [...l.slice(-10), "[heartbeat] " + new Date().toLocaleTimeString()]);
    }, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="panel">
      <div className="panel-head"><b>Terminal</b></div>
      <pre className="terminal">{lines.join("\n")}</pre>
    </div>
  );
}
