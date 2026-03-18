import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

const BACKEND_URL = "http://localhost:8000";

type SupportSignal = {
  issue_key: string;
  category: string;
  title: string;
  severity: string;
  decision_kind: string;
  decision_reason: string;
  summary: string;
  recommended_fixes: string[];
  last_task_id?: string | null;
  trigger_count: number;
  source_signal: string;
  detected_at: string;
  last_decision_at: string;
};

type SupportIncident = {
  id: string;
  title: string;
  summary: string;
  status: string;
  support_category: string | null;
  support_severity: string;
  decision_kind: string;
  decision_reason: string;
  recommended_fixes: string[];
  source_signal: string;
  detected_at: string;
  last_decision_at: string;
  trigger_source: string;
  auto_fix_eligible: boolean;
  auto_fix_attempted: boolean;
  auto_fix_result: string;
  external_ticket_system: string;
  external_ticket_key: string;
  external_ticket_url: string;
  external_ticket_status: string;
  external_ticket_created_at: string | null;
  assigned_executor: string;
  updated_at: string;
  next_suggested_action: string;
};

type SupportIncidentDetail = {
  task: SupportIncident & { prompt: string; risk_level: string };
  timeline: { kind: string; timestamp: string; title: string; detail: string }[];
  policy_events: { event_type: string; message: string; metadata_json: Record<string, unknown>; created_at: string }[];
  incident: {
    decision_kind: string;
    decision_reason: string;
    recommended_fixes: string[];
    detected_at: string;
    last_decision_at: string;
    source_signal: string;
  };
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
    platform: string;
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

export default function Support() {
  const [status, setStatus] = useState<SupportStatus | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<SupportIncidentDetail | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [jiraOauth, setJiraOauth] = useState<{ app_configured: boolean; connected: boolean; cloud_id?: string } | null>(null);
  const [jiraSignInBusy, setJiraSignInBusy] = useState(false);

  const load = async () => {
    const res = await fetch(`${BACKEND_URL}/v1/support/status`);
    const data = await res.json();
    setStatus(data);
    const lastAutoFixId = data.summary?.last_successful_auto_fix?.id;
    const firstIncidentId =
      data.fix_queue?.[0]?.id ??
      data.escalations?.[0]?.id ??
      lastAutoFixId ??
      data.history?.[0]?.id ??
      null;
    setSelectedIncidentId((current) => current ?? firstIncidentId);
  };

  const loadDetail = async (taskId: string) => {
    const res = await fetch(`${BACKEND_URL}/v1/support/incidents/${taskId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail ?? "Could not load support incident.");
    setSelectedIncident(data);
  };

  useEffect(() => {
    load().catch((e) => setError(String(e)));
    const interval = setInterval(() => {
      load().catch(() => {});
    }, 4000);
    fetch(`${BACKEND_URL}/v1/settings/jira/oauth/status`)
      .then((r) => r.json())
      .then(setJiraOauth)
      .catch(() => {});
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!selectedIncidentId) {
      setSelectedIncident(null);
      return;
    }
    loadDetail(selectedIncidentId).catch((e) => setError(String(e)));
  }, [selectedIncidentId]);

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

  const actOnIncident = async (taskId: string, action: "run-fix" | "escalate") => {
    setBusyId(taskId);
    setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/v1/support/incidents/${taskId}/${action}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Support action failed.");
      setStatus(data);
      setSelectedIncidentId(taskId);
      await loadDetail(taskId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyId(null);
    }
  };

  const createTicket = async (taskId: string) => {
    setBusyId(taskId);
    setError("");
    try {
      const res = await fetch(`${BACKEND_URL}/v1/support/incidents/${taskId}/create-ticket`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Ticket creation failed.");
      setStatus(data.status);
      setSelectedIncident(data.detail);
      setSelectedIncidentId(taskId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyId(null);
    }
  };

  const incidentSections: { title: string; items: SupportIncident[] }[] = [
    { title: "Fix Queue", items: status?.fix_queue ?? [] },
    { title: "Escalations", items: status?.escalations ?? [] },
    { title: "History", items: status?.history ?? [] },
  ];

  const renderIncidentList = (items: SupportIncident[], empty: string) => (
    <div className="support-scroll">
      {items.length ? (
        items.map((incident) => (
          <button
            key={incident.id}
            className={`support-incident-item${selectedIncidentId === incident.id ? " active" : ""}`}
            onClick={() => setSelectedIncidentId(incident.id)}
          >
            <div className="support-card-top">
              <strong>{incident.title}</strong>
              <span className={`support-state support-state-${incident.support_severity}`}>{severityLabel(incident.support_severity)}</span>
            </div>
            <div className="support-line">{incident.summary}</div>
            <div className="support-note">{incident.support_category} · {new Date(incident.last_decision_at).toLocaleString()}</div>
          </button>
        ))
      ) : (
        <div className="tasks-empty">{empty}</div>
      )}
    </div>
  );

  return (
    <div className="support-panel">
      <div className="support-header">
        <div>
          <h2>Support</h2>
          <p className="support-subtitle">Local-first incident monitoring, safe remediation, and escalation for device health.</p>
        </div>
      </div>

      {error && <div className="support-error">{error}</div>}

      {jiraOauth?.app_configured && !jiraOauth.connected && (
        <div className="support-banner" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>Connect your Jira account to create IT tickets directly from incidents.</span>
          <button className="btn-save" disabled={jiraSignInBusy} onClick={async () => {
            setJiraSignInBusy(true);
            try {
              const res = await fetch(`${BACKEND_URL}/v1/settings/jira/oauth/start`, { method: "POST" });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail);
              await invoke("plugin:opener|open_url", { url: data.auth_url });
              setTimeout(async () => {
                const r = await fetch(`${BACKEND_URL}/v1/settings/jira/oauth/status`);
                setJiraOauth(await r.json());
                setJiraSignInBusy(false);
              }, 6000);
            } catch {
              setJiraSignInBusy(false);
            }
          }}>{jiraSignInBusy ? "Opening browser…" : "Sign in with Jira"}</button>
        </div>
      )}

      <div className="support-banner">
        <strong>Watcher:</strong> {watcherLabel}
        {status?.summary.platform ? ` · ${status.summary.platform}` : ""}
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
        <button
          className={`support-card compact support-summary-button${status?.summary.last_successful_auto_fix ? "" : " disabled"}`}
          disabled={!status?.summary.last_successful_auto_fix}
          onClick={() => setSelectedIncidentId(status?.summary.last_successful_auto_fix?.id ?? null)}
        >
          <strong>Last auto-fix</strong>
          <div className="support-line">
            {status?.summary.last_successful_auto_fix?.title ?? "No completed auto-fix yet"}
          </div>
        </button>
      </div>

      <div className="support-layout support-layout-split">
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

          <div className="support-section-title support-section-gap">Monitoring</div>
          <div className="support-scroll support-scroll-medium">
            {status?.monitoring?.length ? (
              status.monitoring.map((signal) => (
                <div key={signal.issue_key} className="support-card compact">
                  <div className="support-card-top">
                    <strong>{signal.title}</strong>
                    <span className="support-state support-state-monitoring">monitoring</span>
                  </div>
                  <div className="support-line">{signal.summary}</div>
                  <div className="support-note">{signal.category} · signal {signal.source_signal}</div>
                  <div className="support-note">{signal.decision_reason}</div>
                </div>
              ))
            ) : (
              <div className="tasks-empty">No monitoring issues right now.</div>
            )}
          </div>

          {incidentSections.map((section) => (
            <div key={section.title}>
              <div className="support-section-title support-section-gap">{section.title}</div>
              {renderIncidentList(
                section.items,
                section.title === "Fix Queue"
                  ? "No queued safe fixes."
                  : section.title === "Escalations"
                    ? "No escalations right now."
                    : "No support incident history yet.",
              )}
            </div>
          ))}
        </section>

        <section className="support-section support-detail-pane">
          <div className="support-section-title">Incident Detail</div>
          {selectedIncident ? (
            <div className="support-scroll">
              <div className="support-card">
                <div className="support-card-top">
                  <strong>{selectedIncident.task.title}</strong>
                  <span className={`support-state support-state-${selectedIncident.incident.decision_kind}`}>
                    {severityLabel(selectedIncident.incident.decision_kind)}
                  </span>
                </div>
                <div className="support-line">{selectedIncident.task.summary}</div>
                <div className="support-note">{selectedIncident.task.support_category || "device"}</div>
                <div className="support-line"><strong>Why:</strong> {selectedIncident.incident.decision_reason}</div>
                <div className="support-line"><strong>Signal:</strong> {selectedIncident.incident.source_signal || "manual"}</div>
                <div className="support-line"><strong>Detected:</strong> {new Date(selectedIncident.incident.detected_at).toLocaleString()}</div>
                <div className="support-line"><strong>Last decision:</strong> {new Date(selectedIncident.incident.last_decision_at).toLocaleString()}</div>
                {selectedIncident.task.auto_fix_result && <div className="support-line"><strong>Result:</strong> {selectedIncident.task.auto_fix_result}</div>}
                {selectedIncident.task.external_ticket_key && (
                  <div className="support-line">
                    <strong>IT ticket:</strong>{" "}
                    {selectedIncident.task.external_ticket_url ? (
                      <a className="support-link" href={selectedIncident.task.external_ticket_url} target="_blank" rel="noreferrer">
                        {selectedIncident.task.external_ticket_key}
                      </a>
                    ) : (
                      selectedIncident.task.external_ticket_key
                    )}
                    {selectedIncident.task.external_ticket_status ? ` · ${selectedIncident.task.external_ticket_status}` : ""}
                  </div>
                )}
                <div className="support-line"><strong>Next:</strong> {selectedIncident.task.next_suggested_action}</div>
                <div className="support-actions">
                  {selectedIncident.task.support_severity === "fix_queued" && (
                    <button
                      className="support-action-button"
                      disabled={busyId === selectedIncident.task.id}
                      onClick={() => actOnIncident(selectedIncident.task.id, "run-fix")}
                    >
                      {busyId === selectedIncident.task.id ? "Running…" : "Run safe fix"}
                    </button>
                  )}
                  {["action_required", "blocked", "escalated"].includes(selectedIncident.task.support_severity) && (
                    <button
                      className="support-action-button secondary"
                      disabled={busyId === selectedIncident.task.id}
                      onClick={() => actOnIncident(selectedIncident.task.id, "escalate")}
                    >
                      {busyId === selectedIncident.task.id ? "Working…" : "Escalate"}
                    </button>
                  )}
                  {!selectedIncident.task.external_ticket_key && (
                    jiraOauth?.app_configured && !jiraOauth.connected ? (
                      <button
                        className="support-action-button secondary"
                        disabled={jiraSignInBusy}
                        onClick={async () => {
                          setJiraSignInBusy(true);
                          try {
                            const res = await fetch(`${BACKEND_URL}/v1/settings/jira/oauth/start`, { method: "POST" });
                            const data = await res.json();
                            if (!res.ok) throw new Error(data.detail ?? "Failed");
                            await invoke("plugin:opener|open_url", { url: data.auth_url });
                            setTimeout(async () => {
                              const r = await fetch(`${BACKEND_URL}/v1/settings/jira/oauth/status`);
                              setJiraOauth(await r.json());
                            }, 6000);
                          } finally {
                            setJiraSignInBusy(false);
                          }
                        }}
                      >
                        {jiraSignInBusy ? "Opening browser…" : "Sign in with Jira to create ticket"}
                      </button>
                    ) : (
                      <button
                        className="support-action-button secondary"
                        disabled={busyId === selectedIncident.task.id}
                        onClick={() => createTicket(selectedIncident.task.id)}
                      >
                        {busyId === selectedIncident.task.id ? "Creating…" : "Create IT ticket"}
                      </button>
                    )
                  )}
                </div>
              </div>

              <div className="support-card">
                <strong>Recommended fixes</strong>
                {selectedIncident.incident.recommended_fixes.length ? (
                  selectedIncident.incident.recommended_fixes.map((fix) => (
                    <div key={fix} className="support-line">- {fix}</div>
                  ))
                ) : (
                  <div className="tasks-empty">No additional recommendations.</div>
                )}
              </div>

              <div className="support-card">
                <strong>Audit trail</strong>
                {selectedIncident.policy_events.length ? (
                  selectedIncident.policy_events.map((event) => (
                    <div key={`${event.event_type}-${event.created_at}`} className="support-audit-row">
                      <div className="support-line"><strong>{event.event_type}</strong></div>
                      <div className="support-note">{event.message}</div>
                      <div className="support-note">{new Date(event.created_at).toLocaleString()}</div>
                    </div>
                  ))
                ) : (
                  <div className="tasks-empty">No audit events yet.</div>
                )}
              </div>

              <div className="support-card">
                <strong>Timeline</strong>
                {selectedIncident.timeline.length ? (
                  selectedIncident.timeline.map((event, index) => (
                    <div key={`${event.kind}-${event.timestamp}-${index}`} className="support-audit-row">
                      <div className="support-line"><strong>{event.title}</strong> <span className="timeline-kind">{event.kind}</span></div>
                      <div className="support-note">{event.detail}</div>
                      <div className="support-note">{new Date(event.timestamp).toLocaleString()}</div>
                    </div>
                  ))
                ) : (
                  <div className="tasks-empty">No timeline events yet.</div>
                )}
              </div>
            </div>
          ) : (
            <div className="tasks-empty">Select a support incident to inspect its decision, audit trail, and actions.</div>
          )}
        </section>
      </div>
    </div>
  );
}
