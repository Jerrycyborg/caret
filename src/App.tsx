import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Chat from "./components/Chat";
import "./App.css";

export type View = "chat" | "files" | "terminal" | "resources" | "security" | "settings";

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
          />
        )}
        {view !== "chat" && (
          <div className="coming-soon">
            <div className="coming-soon-icon">
              {view === "files" && "📁"}
              {view === "terminal" && "⌨️"}
              {view === "resources" && "📊"}
              {view === "security" && "🔒"}
              {view === "settings" && "⚙️"}
            </div>
            <h2>{view.charAt(0).toUpperCase() + view.slice(1)}</h2>
            <p>Coming in a future phase.</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;


export default App;
