import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Chat from "./components/Chat";
import Settings from "./components/Settings";
import Resources from "./components/Resources";
import Support from "./components/Support";
import SecurityPanel from "./components/SecurityPanel";
import "./App.css";

export type View = "chat" | "support" | "resources" | "security" | "settings";

function App() {
  const [view, setView] = useState<View>("chat");
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);

  const handleConvCreated = useCallback((id: string) => {
    setActiveConvId(id);
    setSidebarKey((k) => k + 1);
  }, []);

  const handleConvUpdated = useCallback(() => {
    setSidebarKey((k) => k + 1);
  }, []);

  const handleOpenTask = useCallback(() => {
    setView("support");
  }, []);

  return (
    <div className="app">
      <Sidebar
        activeView={view}
        onNavigate={(v) => setView(v)}
        activeConvId={activeConvId}
        onSelectConv={(id) => {
          setActiveConvId(id);
          setView("chat");
        }}
        onNewConv={() => {
          setActiveConvId(null);
          setView("chat");
        }}
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
        {view === "support" && <Support />}
        {view === "settings" && <Settings />}
        {view === "resources" && <Resources />}
        {view === "security" && <SecurityPanel />}
      </main>
    </div>
  );
}

export default App;
