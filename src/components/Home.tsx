import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { BACKEND_URL } from "../config";

interface HealthTile {
  label: string;
  value: string;
  pct: number;
  status: "ok" | "warn" | "critical";
  icon: "cpu" | "mem" | "disk";
}

interface ActiveIncident {
  id: string;
  title: string;
  support_severity: string;
  support_category: string;
  external_ticket_key: string;
}

interface HomeProps {
  onNavigate: (view: "help" | "incidents" | "security" | "settings") => void;
}

function healthStatus(pct: number): "ok" | "warn" | "critical" {
  if (pct >= 85) return "critical";
  if (pct >= 65) return "warn";
  return "ok";
}

function CpuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" />
      <line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  );
}

function MemIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <line x1="6" y1="10" x2="6" y2="14" /><line x1="10" y1="10" x2="10" y2="14" />
      <line x1="14" y1="10" x2="14" y2="14" /><line x1="18" y1="10" x2="18" y2="14" />
    </svg>
  );
}

function DiskIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
      <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
    </svg>
  );
}

export default function Home({ onNavigate }: HomeProps) {
  const [tiles, setTiles] = useState<HealthTile[]>([]);
  const [incidents, setIncidents] = useState<ActiveIncident[]>([]);
  const [backendStatus, setBackendStatus] = useState<"ready" | "starting" | "unavailable">("starting");
  const [loading, setLoading] = useState(true);
  const [cpuBrand, setCpuBrand] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  useEffect(() => {
    const checkBackend = () => {
      invoke<{ status: string }>("get_backend_status").then((s) => {
        const st = s.status as "ready" | "starting" | "unavailable";
        setBackendStatus(st);
        if (st === "ready" && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          loadSupportData();
        }
      }).catch(() => setBackendStatus("unavailable"));
    };
    checkBackend();
    pollRef.current = setInterval(checkBackend, 10000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const loadSupportData = () => {
    fetch(`${BACKEND_URL}/v1/support/status`)
      .then((r) => r.json())
      .then((data) => {
        const active: ActiveIncident[] = [
          ...(data.fix_queue ?? []),
          ...(data.escalations ?? []),
        ].slice(0, 4);
        setIncidents(active);
      })
      .catch(() => {});
  };

  useEffect(() => {
    invoke<{
      cpu: { usage: number; core_count: number; brand: string };
      mem: { used_gb: number; total_gb: number; used_pct: number };
      disks: { name: string; mount: string; used_pct: number }[];
    }>("get_system_info")
      .then((info) => {
        setCpuBrand(info.cpu.brand);
        const diskMax = info.disks.reduce((m, d) => Math.max(m, d.used_pct), 0);
        setTiles([
          { label: "CPU", value: `${info.cpu.usage.toFixed(0)}%`, pct: info.cpu.usage, status: healthStatus(info.cpu.usage), icon: "cpu" },
          { label: "Memory", value: `${info.mem.used_gb.toFixed(1)} / ${info.mem.total_gb.toFixed(0)} GB`, pct: info.mem.used_pct, status: healthStatus(info.mem.used_pct), icon: "mem" },
          { label: "Disk", value: `${diskMax.toFixed(0)}% used`, pct: diskMax, status: healthStatus(diskMax), icon: "disk" },
        ]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const overallStatus = tiles.some((t) => t.status === "critical")
    ? "critical"
    : tiles.some((t) => t.status === "warn")
    ? "warn"
    : "ok";

  const overallLabel =
    overallStatus === "critical" ? "Needs Attention"
    : overallStatus === "warn" ? "Normal"
    : "Healthy";

  const tileIcon = (icon: HealthTile["icon"]) => {
    if (icon === "cpu") return <CpuIcon />;
    if (icon === "mem") return <MemIcon />;
    return <DiskIcon />;
  };

  return (
    <div className="home">
      {/* Hero */}
      <div className="home-hero">
        <div className="home-hero-text">
          <div className="home-greeting">{greeting}</div>
          <div className="home-hero-status">
            Device is&nbsp;<span className={`hero-status-word status-word-${overallStatus}`}>{overallLabel}</span>
          </div>
          {cpuBrand && <div className="home-device-label">{cpuBrand}</div>}
          <div className="home-backend-note">
            {backendStatus === "ready" ? "Caret is monitoring your device."
              : backendStatus === "starting" ? "Support service is starting…"
              : "Support service could not start. Check Settings."}
          </div>
        </div>
        <div className={`home-health-badge badge-${overallStatus}`}>
          <span className={`badge-pulse pulse-${overallStatus}`} />
          {overallLabel}
        </div>
      </div>

      {/* Metric tiles */}
      <div className="home-tiles">
        {loading
          ? ["CPU", "Memory", "Disk"].map((l) => (
              <div key={l} className="health-tile tile-loading">
                <div className="tile-shimmer-label">{l}</div>
                <div className="tile-shimmer-bar" />
              </div>
            ))
          : tiles.map((t) => (
              <div key={t.label} className={`health-tile tile-${t.status}`}>
                <div className="tile-top">
                  <div className={`tile-icon-wrap icon-${t.status}`}>
                    {tileIcon(t.icon)}
                  </div>
                  <div className="tile-info">
                    <div className="tile-label">{t.label}</div>
                    <div className="tile-value">{t.value}</div>
                  </div>
                  <div className={`tile-pct pct-${t.status}`}>{t.pct.toFixed(0)}%</div>
                </div>
                <div className="tile-bar">
                  <div
                    className={`tile-bar-fill fill-${t.status}`}
                    style={{ width: `${Math.min(t.pct, 100)}%` }}
                  />
                </div>
              </div>
            ))}
      </div>

      {/* Quick actions */}
      <div className="home-actions-grid">
        <button className="home-action-card primary-action" onClick={() => onNavigate("help")}>
          <span className="action-card-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </span>
          <div className="action-card-body">
            <div className="action-card-title">Get IT Help</div>
            <div className="action-card-desc">Ask the AI assistant</div>
          </div>
          <svg className="action-card-arrow" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>

        <button className="home-action-card" onClick={() => onNavigate("incidents")}>
          <span className="action-card-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </span>
          <div className="action-card-body">
            <div className="action-card-title">Incidents</div>
            <div className="action-card-desc">Monitoring signals</div>
          </div>
          <svg className="action-card-arrow" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>

        <button className="home-action-card" onClick={() => onNavigate("security")}>
          <span className="action-card-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </span>
          <div className="action-card-body">
            <div className="action-card-title">Security</div>
            <div className="action-card-desc">Compliance & firewall</div>
          </div>
          <svg className="action-card-arrow" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      {/* Active issues */}
      <div className="home-issues">
        <div className="home-section-title">Active Issues</div>
        {incidents.length > 0
          ? incidents.map((inc) => (
              <div
                key={inc.id}
                className={`home-incident-row`}
                onClick={() => onNavigate("incidents")}
              >
                <span className={`incident-sev-dot sev-${inc.support_severity}`} />
                <span className="incident-title">{inc.title}</span>
                {inc.external_ticket_key && (
                  <span className="incident-ticket">{inc.external_ticket_key}</span>
                )}
                <svg className="incident-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
            ))
          : !loading && (
              <div className="home-no-issues">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                <span>No active issues detected</span>
              </div>
            )}
      </div>
    </div>
  );
}
