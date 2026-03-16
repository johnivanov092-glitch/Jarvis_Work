import DesktopStatusBar from "./DesktopStatusBar";
import SupervisorView from "./SupervisorView";
import RunHistoryView from "./RunHistoryView";
import BackendControlPanel from "./BackendControlPanel";

export default function WorkspaceShell() {
  return (
    <div className="workspace-shell">
      <DesktopStatusBar />
      <div className="workspace-grid">
        <SupervisorView />
        <RunHistoryView />
        <BackendControlPanel />
      </div>
    </div>
  );
}
