import { useEffect, useMemo, useState } from "react";

const BACKEND_URL = "http://localhost:8000";

type SupportSignal = {
  issue_key: string;
  category: string;
  title: string;
  severity: string;
  summary: string;
  recommended_fixes: string[];
  last_task_id?: string | null;
  trigger_count: number;
};

type SupportIncident = {
  id: string;
  title: string;
  summary: string;
  status: string;
  support_category: string | null;
  support_severity: string;
  trigger_source: string;
  auto_fix_eligible: boolean;
  auto_fix_attempted: boolean;
  auto_fix_result: string;
  assigned_executor: string;
  updated_at: string;
  next_suggested_action: string;
};

type SupportStatus = {
  running: boolean;
  interval_seconds: number;
  last_run_at: string | null;
  next_run_at: string | null;
  last_error: string;
  last_snapshot: {
    disk_used_pct: number;
    cpu_load_pct: number;
    mem_used_pct: number;
    teams_cpu_pct: number;
    active_connections: number;
    background_heavy_count: number;
  } | null;
  summary: {
    watcher_status: string;
    monitoring_count: number;
    queued_fix_count: number;
    escalation_count: number;
    active_incident_count: number;
    last_successful_auto_fix: SupportIncident | null;
  };
  monitoring: SupportSignal[];
  fix_queue: SupportIncident[];
  escalations: SupportIncident[];
  history: SupportIncident[];
};

export default function Support({ onOpenWorkflows }: { onOpenWorkflows: () => void }) {
  const [status, setStatus] = useState<SupportStatus | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    const res = await fetch(`${BACKEND_URL}/v1/support/status`);
    const data = await res.json();
    setStatus(data);
  };

  useEffect(() => {
    load().catch((e) => setError(String(e)));
    const interval = setInterval(() => {
      load().catch(() => {});
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const summaryCards = useMemo(() => {
    const snapshot = status?.last_snapshot;
    return [
      { label: "Disk", value: snapshot ? `${snapshot.disk_used_pct.toFixed(0)}% used` : "pending" },
      { label: "CPU", value: snapshot ? `${snapshot.cpu_load_pct.toFixed(0)}% load` : "pending" },
      { label: "Memory", value: snapshot ? `${snapshot.mem_used_pct.toFixed(0)}% used` : "pending" },
      { label: "Meetings", value: snapshot ? `${snapshot.teams_cpu_pct.toFixed(0)}% app load` : "pending" },
      { label: "Connections", value: snapshot ? `${snapshot.active_connections}` : "pending" },
      { label: "Background", value: snapshot ? `${snapshot.background_heavy_count} heavy` : "pending" },
    ];
  }, [status]);

  const watcherLabel = status?.summary.watcher_status?.replace("_", " ") ?? "checking";

  const severityLabel = (value: string) => value.replace("_", " ");

  const renderIncident = (incident: SupportIncident) => (
    <div key={incident.id} className="support-card">
      <div className="support-card-top">
        <strong>{incident.title}</strong>
        <span className={`support-state support-state-${incident.support_severity}`}>{severityLabel(incident.support_severity)}</span>
      </div>
      <div className="support-line">{incident.summary}</div>
      <div className="support-note">
        {incident.support_category} · {incident.assigned_executor} · {new Date(incident.updated_at).toLocaleString()}
      </div>
      {incident.auto_fix_result && <div className="support-note">Auto-fix: {incident.auto_fix_result}</div>}
      <div className="support-line">Next: {incident.next_suggested_action}</div>
    </div>
  );

  return (
    <div className="support-panel">
      <div className="support-header">
        <div>
          <h2>Support</h2>
          <p className="support-subtitle">Local-first incident monitoring, safe remediation, and escalation for device health.</p>
        </div>
        <button className="support-open-tasks" onClick={onOpenWorkflows}>Open workflows</button>
      </div>

      {error && <div className="support-error">{error}</div>}

      <div className="support-banner">
        <strong>Watcher:</strong> {watcherLabel}
        {status?.last_run_at ? ` · last run ${new Date(status.last_run_at).toLocaleString()}` : ""}
        {status?.next_run_at ? ` · next run ${new Date(status.next_run_at).toLocaleTimeString()}` : ""}
        {status?.last_error ? ` · error: ${status.last_error}` : ""}
      </div>

      <div className="support-summary-grid">
        <div className="support-card compact">
          <strong>Monitoring</strong>
          <div className="support-line">{status?.summary.monitoring_count ?? 0} active signals</div>
        </div>
        <div className="support-card compact">
          <strong>Fix queue</strong>
          <div className="support-line">{status?.summary.queued_fix_count ?? 0} queued remediations</div>
        </div>
        <div className="support-card compact">
          <strong>Escalations</strong>
          <div className="support-line">{status?.summary.escalation_count ?? 0} need approval</div>
        </div>
        <div className="support-card compact">
          <strong>Last auto-fix</strong>
          <div className="support-line">
            {status?.summary.last_successful_auto_fix?.title ?? "No completed auto-fix yet"}
          </div>
        </div>
      </div>

      <div className="support-layout">
        <section className="support-section">
          <div className="support-section-title">Now</div>
          <div className="support-scroll">
            {summaryCards.map((item) => (
              <div key={item.label} className="support-card compact">
                <strong>{item.label}</strong>
                <div className="support-line">{item.value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="support-section">
          <div className="support-section-title">Monitoring</div>
          <div className="support-scroll">
            {status?.monitoring?.length ? (
              status.monitoring.map((signal) => (
                <div key={signal.issue_key} className="support-card">
                  <div className="support-card-top">
                    <strong>{signal.title}</strong>
                    <span className="support-state support-state-monitoring">monitoring</span>
                  </div>
                  <div className="support-line">{signal.summary}</div>
                  <div className="support-note">{signal.category} · triggered {signal.trigger_count} times</div>
                  {signal.recommended_fixes.length > 0 && (
                    <div className="support-note">Suggested: {signal.recommended_fixes.join(" · ")}</div>
                  )}
                </div>
              ))
            ) : (
              <div className="tasks-empty">No monitoring issues right now.</div>
            )}
          </div>
        </section>

        <section className="support-section">
          <div className="support-section-title">Fix Queue</div>
          <div className="support-scroll">
            {status?.fix_queue?.length ? status.fix_queue.map(renderIncident) : <div className="tasks-empty">No queued safe fixes.</div>}
          </div>
        </section>

        <section className="support-section">
          <div className="support-section-title">Escalations</div>
          <div className="support-scroll">
            {status?.escalations?.length ? status.escalations.map(renderIncident) : <div className="tasks-empty">No escalations right now.</div>}
          </div>
        </section>

        <section className="support-section support-section-wide">
          <div className="support-section-title">History</div>
          <div className="support-scroll">
            {status?.history?.length ? status.history.map(renderIncident) : <div className="tasks-empty">No support incident history yet.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
