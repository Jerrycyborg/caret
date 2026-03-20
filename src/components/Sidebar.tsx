import React, { useEffect, useState } from "react";
import type { View } from "../App";
import { BACKEND_URL } from "../config";

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
  isAdmin: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

const NavIcons: Record<string, () => React.ReactElement> = {
  home: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
  help: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  incidents: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  ),
  security: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  settings: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
};

const navItems: { id: View; label: string }[] = [
  { id: "home",      label: "Home"      },
  { id: "help",      label: "Help"      },
  { id: "incidents", label: "Incidents" },
  { id: "security",  label: "Security"  },
  { id: "settings",  label: "Settings"  },
];

export default function Sidebar({
  activeView,
  onNavigate,
  activeConvId,
  onSelectConv,
  onNewConv,
  refreshKey,
  isAdmin,
  theme,
  onToggleTheme,
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
        <svg className="logo-mark" width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7l10 5 10-5-10-5z" fill="url(#lg)" />
          <path d="M2 17l10 5 10-5" stroke="url(#lg)" strokeWidth="2" strokeLinecap="round" fill="none" />
          <path d="M2 12l10 5 10-5" stroke="url(#lg)" strokeWidth="2" strokeLinecap="round" fill="none" />
          <defs>
            <linearGradient id="lg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
              <stop stopColor="#7c6aff" /><stop offset="1" stopColor="#a78bfa" />
            </linearGradient>
          </defs>
        </svg>
        <span className="logo-text">CARET</span>
      </div>
      <nav className="sidebar-nav">
        {navItems.filter((item) => item.id !== "settings" || isAdmin).map((item) => {
          const Icon = NavIcons[item.id];
          return (
            <button
              key={item.id}
              className={`nav-item${activeView === item.id ? " active" : ""}`}
              onClick={() => onNavigate(item.id)}
            >
              <span className="nav-icon"><Icon /></span>
              <span className="nav-label">{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <button className="theme-toggle-btn" onClick={onToggleTheme} title="Toggle theme">
          {theme === "dark" ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          )}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
      </div>

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
