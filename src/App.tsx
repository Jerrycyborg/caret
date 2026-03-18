import { useState, useCallback, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import Sidebar from "./components/Sidebar";
import Home from "./components/Home";
import Chat from "./components/Chat";
import Support from "./components/Support";
import Settings from "./components/Settings";
import SecurityPanel from "./components/SecurityPanel";
import "./App.css";

export type View = "home" | "help" | "incidents" | "security" | "settings";

const BACKEND_URL = "http://localhost:8000";

function App() {
  const [view, setView] = useState<View>("home");
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    fetch(`${BACKEND_URL}/v1/settings/config`)
      .then((r) => r.json())
      .then(async (data) => {
        const adminGroup: string = data.config?.management?.admin_group ?? "";
        const status = await invoke<{ is_admin: boolean }>("get_admin_status", { adminGroup: adminGroup || undefined });
        setIsAdmin(status.is_admin);
      })
      .catch(() => {});
  }, []);

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
        isAdmin={isAdmin}
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
