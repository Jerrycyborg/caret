import { useEffect, useState } from "react";
import type { View } from "../App";

interface Conversation {
  id: string;
  title: string;
  model: string;
  channel_type: string;
  session_status: string;
}

interface SidebarProps {
  activeView: View;
  onNavigate: (view: View) => void;
  activeConvId: string | null;
  onSelectConv: (id: string) => void;
  onNewConv: () => void;
  refreshKey: number;
}

const BACKEND_URL = "http://localhost:8000";

const navItems: { id: View; label: string; icon: string }[] = [
  { id: "home",      label: "Home",      icon: "🖥️" },
  { id: "help",      label: "Help",      icon: "💬" },
  { id: "incidents", label: "Incidents", icon: "🩺" },
  { id: "security",  label: "Security",  icon: "🔒" },
  { id: "settings",  label: "Settings",  icon: "⚙️" },
];

export default function Sidebar({
  activeView,
  onNavigate,
  activeConvId,
  onSelectConv,
  onNewConv,
  refreshKey,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    fetch(`${BACKEND_URL}/v1/conversations`)
      .then((r) => r.json())
      .then((data) => setConversations(data.conversations ?? []))
      .catch(() => {});
  }, [refreshKey]);

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-text">CARET</span>
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item${activeView === item.id ? " active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
      {activeView === "help" && (
        <div className="conv-section">
          <div className="conv-section-header">
            <span className="conv-section-title">Chats</span>
            <button className="new-conv-btn" onClick={onNewConv} title="New chat">+</button>
          </div>
          <div className="conv-list">
            {conversations.map((c) => (
              <button
                key={c.id}
                className={`conv-item${activeConvId === c.id ? " active" : ""}`}
                onClick={() => onSelectConv(c.id)}
              >
                <span className="conv-title">{c.title}</span>
                <span className={`conv-status status-${c.session_status}`}>{c.session_status}</span>
              </button>
            ))}
            {conversations.length === 0 && <span className="conv-empty">No chats yet</span>}
          </div>
        </div>
      )}
    </aside>
  );
}
