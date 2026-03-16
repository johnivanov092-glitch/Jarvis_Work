import DesktopStatusBar from "./DesktopStatusBar";
import SupervisorView from "./SupervisorView";
import RunHistoryView from "./RunHistoryView";
import BackendControlPanel from "./BackendControlPanel";
import AutonomousDevPanel from "./AutonomousDevPanel";
import ProjectBrainPanel from "./ProjectBrainPanel";

export default function WorkspaceShell() {
  return (
    <div className="workspace-shell">
      <DesktopStatusBar />
      <div className="workspace-grid">
        <SupervisorView />
        <RunHistoryView />
        <BackendControlPanel />
        <AutonomousDevPanel />
        <ProjectBrainPanel />
      </div>
    </div>
  );
}
