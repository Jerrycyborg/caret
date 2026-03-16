import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface HealthTile {
  label: string;
  value: string;
  pct: number;
  status: "ok" | "warn" | "critical";
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

const BACKEND_URL = "http://localhost:8000";

function healthStatus(pct: number): "ok" | "warn" | "critical" {
  if (pct >= 85) return "critical";
  if (pct >= 65) return "warn";
  return "ok";
}

export default function Home({ onNavigate }: HomeProps) {
  const [tiles, setTiles] = useState<HealthTile[]>([]);
  const [incidents, setIncidents] = useState<ActiveIncident[]>([]);
  const [backendStatus, setBackendStatus] = useState<"ready" | "starting" | "unavailable">("starting");
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    pollRef.current = setInterval(checkBackend, 3000);
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
    // Device health from Tauri (independent of backend)
    invoke<{
      cpu: { usage: number; core_count: number; brand: string };
      mem: { used_gb: number; total_gb: number; used_pct: number };
      disks: { name: string; mount: string; used_pct: number }[];
    }>("get_system_info")
      .then((info) => {
        const diskMax = info.disks.reduce((m, d) => Math.max(m, d.used_pct), 0);
        setTiles([
          {
            label: "CPU",
            value: `${info.cpu.usage.toFixed(0)}%`,
            pct: info.cpu.usage,
            status: healthStatus(info.cpu.usage),
          },
          {
            label: "Memory",
            value: `${info.mem.used_gb.toFixed(1)} / ${info.mem.total_gb.toFixed(0)} GB`,
            pct: info.mem.used_pct,
            status: healthStatus(info.mem.used_pct),
          },
          {
            label: "Disk",
            value: `${diskMax.toFixed(0)}% used`,
            pct: diskMax,
            status: healthStatus(diskMax),
          },
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
    overallStatus === "critical"
      ? "Needs attention"
      : overallStatus === "warn"
      ? "Monitor"
      : "Healthy";

  return (
    <div className="home">
      <div className="home-header">
        <div>
          <div className="home-title">Device Overview</div>
          <div className="home-subtitle">
            {backendStatus === "ready"
              ? "Caret is monitoring your device."
              : backendStatus === "starting"
              ? "Support service is starting…"
              : "Support service could not start. Check Settings."}
          </div>
        </div>
        <span className={`home-status-badge status-${overallStatus}`}>
          {overallLabel}
        </span>
      </div>

      <div className="home-tiles">
        {loading
          ? ["CPU", "Memory", "Disk"].map((l) => (
              <div key={l} className="health-tile loading">
                <div className="tile-label">{l}</div>
                <div className="tile-value">—</div>
              </div>
            ))
          : tiles.map((t) => (
              <div key={t.label} className={`health-tile tile-${t.status}`}>
                <div className="tile-label">{t.label}</div>
                <div className="tile-value">{t.value}</div>
                <div className="tile-bar">
                  <div
                    className={`tile-bar-fill fill-${t.status}`}
                    style={{ width: `${Math.min(t.pct, 100)}%` }}
                  />
                </div>
              </div>
            ))}
      </div>

      <div className="home-actions">
        <button className="home-action-btn primary" onClick={() => onNavigate("help")}>
          Get IT Help
        </button>
        <button className="home-action-btn" onClick={() => onNavigate("incidents")}>
          View Incidents
        </button>
      </div>

      {incidents.length > 0 && (
        <div className="home-incidents">
          <div className="home-section-title">Active Issues</div>
          {incidents.map((inc) => (
            <div
              key={inc.id}
              className={`home-incident-row severity-${inc.support_severity}`}
              onClick={() => onNavigate("incidents")}
            >
              <span className={`incident-dot sev-${inc.support_severity}`} />
              <span className="incident-title">{inc.title}</span>
              {inc.external_ticket_key && (
                <span className="incident-ticket">{inc.external_ticket_key}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {incidents.length === 0 && !loading && (
        <div className="home-incidents">
          <div className="home-section-title">Active Issues</div>
          <div className="home-no-issues">No active issues detected.</div>
        </div>
      )}
    </div>
  );
}
