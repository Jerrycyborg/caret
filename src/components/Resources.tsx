import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface CpuInfo { usage: number; core_count: number; brand: string }
interface MemInfo { used_gb: number; total_gb: number; used_pct: number }
interface DiskInfo { name: string; mount: string; used_gb: number; total_gb: number; used_pct: number }
interface ProcessInfo { pid: number; name: string; cpu_pct: number; mem_mb: number }
interface SystemInfo {
  cpu: CpuInfo;
  mem: MemInfo;
  disks: DiskInfo[];
  top_processes: ProcessInfo[];
}

function GaugeBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="gauge-track">
      <div className="gauge-fill" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
    </div>
  );
}

function healthTone(pct: number, warn = 60, danger = 80) {
  if (pct >= danger) return "var(--danger)";
  if (pct >= warn) return "#f59e0b";
  return "var(--success)";
}

export default function Resources() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = async () => {
    try {
      const systemInfo = await invoke<SystemInfo>("get_system_info");
      setInfo(systemInfo);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    refresh();
    intervalRef.current = setInterval(refresh, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  if (error) return <div className="resources"><div className="res-error">⚠ {error}</div></div>;
  if (!info) return <div className="resources"><div className="res-loading">Loading…</div></div>;

  const cpuColor = healthTone(info.cpu.usage, 50, 80);
  const memColor = healthTone(info.mem.used_pct, 60, 80);

  return (
    <div className="resources">
      <div className="res-header">
        <div>
          <div className="res-title">System</div>
          <div className="res-subtitle">Live machine status for support, cleanup, and device health decisions.</div>
        </div>
      </div>

      <div className="res-overview-grid">
        <div className="res-card res-card-hero">
          <div className="res-card-label">Machine load</div>
          <div className="res-hero-row">
            <div>
              <div className="res-card-value" style={{ color: cpuColor }}>{info.cpu.usage.toFixed(0)}%</div>
              <div className="res-card-sub">CPU usage</div>
            </div>
            <div>
              <div className="res-card-value" style={{ color: memColor }}>{info.mem.used_pct.toFixed(0)}%</div>
              <div className="res-card-sub">Memory usage</div>
            </div>
          </div>
          <div className="res-stack">
            <div>
              <div className="res-inline-label">CPU</div>
              <GaugeBar pct={info.cpu.usage} color={cpuColor} />
            </div>
            <div>
              <div className="res-inline-label">Memory</div>
              <GaugeBar pct={info.mem.used_pct} color={memColor} />
            </div>
          </div>
        </div>

        <div className="res-card">
          <div className="res-card-label">Hardware</div>
          <div className="res-card-value">{info.cpu.core_count}</div>
          <div className="res-card-sub">CPU cores · {info.cpu.brand}</div>
        </div>

        <div className="res-card">
          <div className="res-card-label">Memory</div>
          <div className="res-card-value">{info.mem.used_gb.toFixed(1)} GB</div>
          <div className="res-card-sub">used of {info.mem.total_gb.toFixed(1)} GB</div>
        </div>
      </div>

      <div className="res-layout">
        <section className="res-panel">
          <div className="res-section-title">Storage</div>
          <div className="res-scroll-list">
            {info.disks.map((disk) => {
              const tone = healthTone(disk.used_pct, 65, 85);
              return (
                <div key={disk.mount} className="res-list-item">
                  <div className="res-list-top">
                    <strong>{disk.mount}</strong>
                    <span style={{ color: tone }}>{disk.used_pct.toFixed(0)}%</span>
                  </div>
                  <GaugeBar pct={disk.used_pct} color={tone} />
                  <div className="res-card-sub">{disk.used_gb.toFixed(1)} / {disk.total_gb.toFixed(1)} GB</div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="res-panel">
          <div className="res-section-title">Top Processes</div>
          <div className="res-scroll-list">
            {info.top_processes.map((process) => (
              <div key={process.pid} className="res-list-item">
                <div className="res-list-top">
                  <strong>{process.name}</strong>
                  <span className={process.cpu_pct > 20 ? "res-state warn" : "res-state muted"}>
                    {process.cpu_pct.toFixed(1)}% CPU
                  </span>
                </div>
                <div className="res-card-sub">PID {process.pid} · {process.mem_mb.toFixed(0)} MB RAM</div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
