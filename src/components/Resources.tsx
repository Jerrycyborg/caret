import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";

interface CpuInfo { usage: number; core_count: number; brand: string }
interface MemInfo { used_gb: number; total_gb: number; used_pct: number }
interface DiskInfo { name: string; mount: string; used_gb: number; total_gb: number; used_pct: number }
interface ProcessInfo { pid: number; name: string; cpu_pct: number; mem_mb: number }
interface ExecutionTargetInfo { id: string; label: string; available: boolean; reason: string }
interface ToolAdapterInfo {
  id: string;
  name: string;
  adapter_type: string;
  health: string;
  capabilities: string[];
  input_contract: string;
  output_contract: string;
  error_contract: string;
  orchestration_role: string;
}
interface SystemInfo {
  cpu: CpuInfo;
  mem: MemInfo;
  disks: DiskInfo[];
  top_processes: ProcessInfo[];
  execution_targets: ExecutionTargetInfo[];
}

function GaugeBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="gauge-track">
      <div className="gauge-fill" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
    </div>
  );
}

export default function Resources() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [adapters, setAdapters] = useState<ToolAdapterInfo[]>([]);
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = async () => {
    try {
      const [systemInfo, toolAdapters] = await Promise.all([
        invoke<SystemInfo>("get_system_info"),
        invoke<ToolAdapterInfo[]>("list_tool_adapters"),
      ]);
      setInfo(systemInfo);
      setAdapters(toolAdapters);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    refresh();
    intervalRef.current = setInterval(refresh, 2000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  if (error) return (
    <div className="resources"><div className="res-error">⚠ {error}</div></div>
  );
  if (!info) return <div className="resources"><div className="res-loading">Loading…</div></div>;

  const cpuColor = info.cpu.usage > 80 ? "var(--danger)" : info.cpu.usage > 50 ? "#f59e0b" : "var(--success)";
  const memColor = info.mem.used_pct > 80 ? "var(--danger)" : info.mem.used_pct > 60 ? "#f59e0b" : "var(--accent)";

  return (
    <div className="resources">
      <div className="res-title">Resources</div>

      <div className="res-grid">
        {/* CPU */}
        <div className="res-card">
          <div className="res-card-label">CPU — {info.cpu.brand || `${info.cpu.core_count} cores`}</div>
          <div className="res-card-value" style={{ color: cpuColor }}>{info.cpu.usage.toFixed(1)}%</div>
          <GaugeBar pct={info.cpu.usage} color={cpuColor} />
          <div className="res-card-sub">{info.cpu.core_count} logical cores</div>
        </div>

        {/* RAM */}
        <div className="res-card">
          <div className="res-card-label">Memory</div>
          <div className="res-card-value" style={{ color: memColor }}>{info.mem.used_pct.toFixed(1)}%</div>
          <GaugeBar pct={info.mem.used_pct} color={memColor} />
          <div className="res-card-sub">
            {info.mem.used_gb.toFixed(1)} / {info.mem.total_gb.toFixed(1)} GB
          </div>
        </div>

        {/* Disks */}
        {info.disks.slice(0, 2).map((d) => {
          const dc = d.used_pct > 85 ? "var(--danger)" : d.used_pct > 65 ? "#f59e0b" : "var(--accent)";
          return (
            <div key={d.mount} className="res-card">
              <div className="res-card-label">Disk — {d.mount}</div>
              <div className="res-card-value" style={{ color: dc }}>{d.used_pct.toFixed(1)}%</div>
              <GaugeBar pct={d.used_pct} color={dc} />
              <div className="res-card-sub">{d.used_gb.toFixed(1)} / {d.total_gb.toFixed(1)} GB</div>
            </div>
          );
        })}
      </div>

      <div className="res-section-title">Execution Targets</div>
      <div className="res-grid">
        {info.execution_targets.map((target) => (
          <div key={target.id} className="res-card">
            <div className="res-card-label">{target.label}</div>
            <div
              className="res-card-value"
              style={{ color: target.available ? "var(--success)" : "var(--text-muted)" }}
            >
              {target.available ? "Available" : "Unavailable"}
            </div>
            <div className="res-card-sub">{target.reason}</div>
          </div>
        ))}
      </div>

      <div className="res-section-title">Tool Adapters</div>
      <div className="res-grid">
        {adapters.map((adapter) => (
          <div key={adapter.id} className="res-card">
            <div className="res-card-label">{adapter.name}</div>
            <div
              className="res-card-value"
              style={{ color: adapter.health === "healthy" ? "var(--success)" : "#f59e0b", fontSize: 18 }}
            >
              {adapter.health}
            </div>
            <div className="res-card-sub">{adapter.orchestration_role}</div>
            <div className="res-card-sub">Type: {adapter.adapter_type}</div>
            <div className="res-card-sub">Capabilities: {adapter.capabilities.join(", ")}</div>
          </div>
        ))}
      </div>

      {/* Process table */}
      <div className="res-section-title">Top Processes</div>
      <div className="proc-table">
        <div className="proc-header">
          <span>Name</span><span>PID</span><span>CPU %</span><span>RAM (MB)</span>
        </div>
        {info.top_processes.map((p) => (
          <div key={p.pid} className="proc-row">
            <span className="proc-name">{p.name}</span>
            <span className="proc-pid">{p.pid}</span>
            <span className={`proc-cpu${p.cpu_pct > 20 ? " high" : ""}`}>{p.cpu_pct.toFixed(1)}</span>
            <span className="proc-mem">{p.mem_mb.toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
