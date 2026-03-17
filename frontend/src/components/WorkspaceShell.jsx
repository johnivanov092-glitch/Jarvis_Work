import { useMemo, useState } from "react";
        import {
          Bot,
          FolderKanban,
          History,
          Search,
          Settings,
          Code2,
          Eye,
          GitBranch,
          Globe,
          Play,
          Square,
          PanelLeft,
        } from "lucide-react";

        const chats = [
          { id: "c1", title: "Patch pipeline redesign", time: "2m ago" },
          { id: "c2", title: "Browser runtime", time: "18m ago" },
          { id: "c3", title: "Tauri desktop fixes", time: "1h ago" },
        ];

        const timeline = [
          { type: "planner", title: "Goal parsed", meta: "Patch pipeline + safer rollback" },
          { type: "research", title: "Project Brain analyzed impacted files", meta: "main.py · patch service · routes" },
          { type: "code", title: "Generated patch preview", meta: "4 files · diff ready" },
          { type: "verify", title: "Verification pending", meta: "pytest / syntax / rollback smoke" },
        ];

        const tabs = [
          { id: "preview", label: "Preview", icon: Eye },
          { id: "code", label: "Code", icon: Code2 },
          { id: "diff", label: "Diff", icon: GitBranch },
          { id: "browser", label: "Browser", icon: Globe },
        ];

        function SidebarItem({ icon: Icon, label, active = false, collapsed = false }) {
          return (
            <button className={`jw-sidebar-item ${active ? "active" : ""} ${collapsed ? "collapsed" : ""}`}>
              <Icon size={18} />
              {!collapsed && <span>{label}</span>}
            </button>
          );
        }

        function TimelineBadge({ type }) {
          const map = {
            planner: "Planner",
            research: "Research",
            code: "Coder",
            verify: "Verify",
          };
          return <span className={`jw-badge jw-badge-${type}`}>{map[type] || type}</span>;
        }

        export default function WorkspaceShell() {
          const [activeTab, setActiveTab] = useState("preview");
          const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
          const [prompt, setPrompt] = useState("Сделай safe patch pipeline с rollback и verification.");
          const activeChat = useMemo(() => chats[0], []);

          return (
            <div className="jw-app">
              <aside className={`jw-sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
                <div className="jw-sidebar-top">
                  <button
                    className="jw-icon-button"
                    onClick={() => setSidebarCollapsed((v) => !v)}
                    title="Toggle sidebar"
                  >
                    <PanelLeft size={18} />
                  </button>
                  {!sidebarCollapsed && (
                    <div className="jw-brand">
                      <div className="jw-brand-mark">J</div>
                      <div>
                        <div className="jw-brand-title">Jarvis Work</div>
                        <div className="jw-brand-subtitle">AI IDE Desktop</div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="jw-sidebar-group">
                  <SidebarItem icon={Bot} label="Chat" active collapsed={sidebarCollapsed} />
                  <SidebarItem icon={FolderKanban} label="Projects" collapsed={sidebarCollapsed} />
                  <SidebarItem icon={History} label="Runs" collapsed={sidebarCollapsed} />
                  <SidebarItem icon={Search} label="Research" collapsed={sidebarCollapsed} />
                  <SidebarItem icon={Settings} label="Settings" collapsed={sidebarCollapsed} />
                </div>

                {!sidebarCollapsed && (
                  <>
                    <div className="jw-sidebar-section-title">Recent Chats</div>
                    <div className="jw-chat-list">
                      {chats.map((chat) => (
                        <button key={chat.id} className={`jw-chat-item ${chat.id === activeChat.id ? "active" : ""}`}>
                          <div className="jw-chat-item-title">{chat.title}</div>
                          <div className="jw-chat-item-time">{chat.time}</div>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </aside>

              <main className="jw-main">
                <header className="jw-topbar">
                  <div className="jw-topbar-left">
                    <div className="jw-context-title">{activeChat.title}</div>
                    <div className="jw-context-subtitle">Workspace · Agent loop · Desktop runtime</div>
                  </div>
                  <div className="jw-topbar-actions">
                    <button className="jw-secondary-button"><Square size={15} /> Stop</button>
                    <button className="jw-primary-button"><Play size={15} /> Run</button>
                  </div>
                </header>

                <section className="jw-commandbar">
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    className="jw-command-input"
                  />
                  <div className="jw-command-actions">
                    <button className="jw-secondary-button">Project Brain</button>
                    <button className="jw-secondary-button">Multi-Agent</button>
                    <button className="jw-primary-button">Execute</button>
                  </div>
                </section>

                <section className="jw-workspace">
                  <div className="jw-left-panel">
                    <div className="jw-panel-header">
                      <div>
                        <h2>Agent Conversation</h2>
                        <p>Пошаговое выполнение задачи и действия агентов</p>
                      </div>
                    </div>

                    <div className="jw-messages">
                      <div className="jw-message user">
                        <div className="jw-message-role">You</div>
                        <div className="jw-message-text">
                          Сделай desktop-first safe patch workflow и покажи diff preview.
                        </div>
                      </div>

                      <div className="jw-message assistant">
                        <div className="jw-message-role">Jarvis</div>
                        <div className="jw-message-text">
                          Анализирую проект, строю план и готовлю безопасный pipeline изменений.
                        </div>
                      </div>
                    </div>

                    <div className="jw-timeline">
                      {timeline.map((item, idx) => (
                        <div className="jw-timeline-item" key={idx}>
                          <div className="jw-timeline-line" />
                          <div className="jw-timeline-content">
                            <div className="jw-timeline-head">
                              <TimelineBadge type={item.type} />
                              <span className="jw-timeline-title">{item.title}</span>
                            </div>
                            <div className="jw-timeline-meta">{item.meta}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="jw-right-panel">
                    <div className="jw-tabs">
                      {tabs.map((tab) => {
                        const Icon = tab.icon;
                        return (
                          <button
                            key={tab.id}
                            className={`jw-tab ${activeTab === tab.id ? "active" : ""}`}
                            onClick={() => setActiveTab(tab.id)}
                          >
                            <Icon size={15} />
                            <span>{tab.label}</span>
                          </button>
                        );
                      })}
                    </div>

                    <div className="jw-editor-shell">
                      {activeTab === "preview" && (
                        <div className="jw-preview">
                          <div className="jw-preview-window">
                            <div className="jw-preview-toolbar">
                              <span />
                              <span />
                              <span />
                            </div>
                            <div className="jw-preview-body">
                              <div className="jw-preview-card">
                                <div className="jw-preview-title">Safe Patch Pipeline</div>
                                <div className="jw-preview-subtitle">Preview · Verify · Apply · Rollback</div>
                              </div>
                              <div className="jw-preview-grid">
                                <div className="jw-stat-card">
                                  <span>Impacted files</span>
                                  <strong>4</strong>
                                </div>
                                <div className="jw-stat-card">
                                  <span>Backup points</span>
                                  <strong>3</strong>
                                </div>
                                <div className="jw-stat-card">
                                  <span>Checks</span>
                                  <strong>5</strong>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {activeTab === "code" && (
                        <pre className="jw-code-block">{`def apply_patch_transaction(payload):
    backup_id = create_backup(payload["file_path"])
    preview = preview_patch(payload)
    checks = verify_patch(payload["file_path"])
    if checks["status"] != "ok":
        rollback_patch(backup_id)
        return {"status": "rolled_back"}
    return {"status": "applied", "backup_id": backup_id}`}</pre>
                      )}

                      {activeTab === "diff" && (
                        <pre className="jw-code-block">{`--- a/backend/app/services/project_patch_service.py
+++ b/backend/app/services/project_patch_service.py
@@
- def apply_patch(...):
+ def apply_patch_transaction(...):
+     backup_id = create_backup(...)
+     verify_result = verify_patch(...)
+     if verify_result["status"] != "ok":
+         rollback_patch(backup_id)`}</pre>
                      )}

                      {activeTab === "browser" && (
                        <div className="jw-browser-placeholder">
                          <div className="jw-browser-bar">https://docs.example.dev/safe-patch</div>
                          <div className="jw-browser-content">
                            Browser runtime placeholder for Playwright / docs / research.
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </section>

                <footer className="jw-bottom-bar">
                  <div className="jw-bottom-pill">Backend · connected</div>
                  <div className="jw-bottom-pill">Execution · running</div>
                  <div className="jw-bottom-pill">Mode · desktop</div>
                </footer>
              </main>
            </div>
          );
        }
