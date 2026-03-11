import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Chat from "./components/Chat";
import Settings from "./components/Settings";
import Resources from "./components/Resources";
import Support from "./components/Support";
import SecurityPanel from "./components/SecurityPanel";
import PluginMarketplace from "./components/PluginMarketplace";
import TasksPanel from "./components/TasksPanel";
import "./App.css";

export type View = "chat" | "tasks" | "support" | "resources" | "security" | "settings" | "marketplace";

function App() {
  const [view, setView] = useState<View>("chat");
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

  const handleConvCreated = useCallback((id: string) => {
    setActiveConvId(id);
    setSidebarKey((k) => k + 1);
  }, []);

  const handleConvUpdated = useCallback(() => {
    setSidebarKey((k) => k + 1);
  }, []);

  const handleOpenTask = useCallback((taskId: string, taskKind: string = "workflow_task") => {
    setActiveTaskId(taskId);
    setView(taskKind === "support_incident" ? "support" : "tasks");
  }, []);

  return (
    <div className="app">
      <Sidebar
        activeView={view}
        onNavigate={(v) => setView(v)}
        activeConvId={activeConvId}
        onSelectConv={(id) => { setActiveConvId(id); setView("chat"); }}
        onNewConv={() => { setActiveConvId(null); setView("chat"); }}
        refreshKey={sidebarKey}
      />
      <main className="main-content">
        {view === "chat" && (
          <Chat
            conversationId={activeConvId}
            onConversationCreated={handleConvCreated}
            onConversationUpdated={handleConvUpdated}
            onOpenTask={handleOpenTask}
          />
        )}
        {view === "tasks" && <TasksPanel initialTaskId={activeTaskId} />}
        {view === "support" && <Support onOpenWorkflows={() => setView("tasks")} />}
        {view === "settings" && <Settings />}
        {view === "resources" && <Resources />}
        {view === "security" && <SecurityPanel />}
        {view === "marketplace" && <PluginMarketplace />}
      </main>
    </div>
  );
}

export default App;
