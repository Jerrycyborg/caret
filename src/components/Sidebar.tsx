import type { View } from "../App";

interface SidebarProps {
  activeView: View;
  onNavigate: (view: View) => void;
}

const navItems: { id: View; label: string; icon: string }[] = [
  { id: "chat", label: "Chat", icon: "💬" },
  { id: "files", label: "Files", icon: "📁" },
  { id: "terminal", label: "Terminal", icon: "⌨️" },
  { id: "resources", label: "Resources", icon: "📊" },
  { id: "security", label: "Security", icon: "🔒" },
  { id: "settings", label: "Settings", icon: "⚙️" },
];

export default function Sidebar({ activeView, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-text">OXY</span>
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
    </aside>
  );
}
