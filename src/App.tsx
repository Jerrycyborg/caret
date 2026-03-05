import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Chat from "./components/Chat";
import "./App.css";

export type View = "chat" | "files" | "terminal" | "resources" | "security" | "settings";

function App() {
  const [view, setView] = useState<View>("chat");

  return (
    <div className="app">
      <Sidebar activeView={view} onNavigate={setView} />
      <main className="main-content">
        {view === "chat" && <Chat />}
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
