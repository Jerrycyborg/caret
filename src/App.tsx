import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Home from "./components/Home";
import Chat from "./components/Chat";
import Support from "./components/Support";
import Settings from "./components/Settings";
import SecurityPanel from "./components/SecurityPanel";
import "./App.css";

export type View = "home" | "help" | "incidents" | "security" | "settings";

function App() {
  const [view, setView] = useState<View>("home");
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);

  const handleConvCreated = useCallback((id: string) => {
    setActiveConvId(id);
    setSidebarKey((k) => k + 1);
  }, []);

  const handleConvUpdated = useCallback(() => {
    setSidebarKey((k) => k + 1);
  }, []);

  return (
    <div className="app">
      <Sidebar
        activeView={view}
        onNavigate={(v) => setView(v)}
        activeConvId={activeConvId}
        onSelectConv={(id) => {
          setActiveConvId(id);
          setView("help");
        }}
        onNewConv={() => {
          setActiveConvId(null);
          setView("help");
        }}
        refreshKey={sidebarKey}
      />
      <main className="main-content">
        {view === "home" && (
          <Home onNavigate={(v) => setView(v)} />
        )}
        {view === "help" && (
          <Chat
            conversationId={activeConvId}
            onConversationCreated={handleConvCreated}
            onConversationUpdated={handleConvUpdated}
            onOpenTask={() => setView("incidents")}
          />
        )}
        {view === "incidents" && <Support />}
        {view === "security" && <SecurityPanel />}
        {view === "settings" && <Settings />}
      </main>
    </div>
  );
}

export default App;
