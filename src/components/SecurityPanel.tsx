import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface ComplianceStatus {
  firewall_on: boolean;
  bitlocker_on: boolean;
  active_connections: number;
  recent_errors: number;
  defender_enabled: boolean;
  pending_reboot: boolean;
  spooler_running: boolean;
}

interface AdminStatus {
  is_admin: boolean;
}

type PrivilegedActionRequest =
  | { kind: "firewall"; enabled: boolean }
  | { kind: "service"; name: string; action: "start" | "stop" | "restart" }
  | { kind: "terminate_process"; pid: number };

interface PrivilegedActionPreview {
  action_label: string;
  reason: string;
  execution_path: string;
}

interface PrivilegedActionResult {
  status: string;
  message: string;
  details?: string;
}

interface SystemEvent {
  time: string;
  id: number;
  level: string;
  source: string;
  message: string;
}

type ActionState = "idle" | "previewing" | "executing" | "done";

const ADMIN_ACTIONS: { label: string; request: PrivilegedActionRequest }[] = [
  { label: "Enable firewall",  request: { kind: "firewall", enabled: true } },
  { label: "Disable firewall", request: { kind: "firewall", enabled: false } },
];

export default function SecurityPanel() {
  const [compliance, setCompliance] = useState<ComplianceStatus | null>(null);
  const [adminStatus, setAdminStatus] = useState<AdminStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<PrivilegedActionPreview | null>(null);
  const [pendingRequest, setPendingRequest] = useState<PrivilegedActionRequest | null>(null);
  const [actionState, setActionState] = useState<ActionState>("idle");
  const [actionResult, setActionResult] = useState<PrivilegedActionResult | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [showEvents, setShowEvents] = useState(false);
  const [eventsLoading, setEventsLoading] = useState(false);

  useEffect(() => {
    fetch("http://localhost:8000/v1/settings/config")
      .then((r) => r.json())
      .then((data) => {
        const adminGroup: string = data.config?.management?.admin_group ?? "";
        return Promise.all([
          invoke<ComplianceStatus>("get_compliance_status"),
          invoke<AdminStatus>("get_admin_status", { adminGroup: adminGroup || undefined }),
        ]);
      })
      .catch(() =>
        Promise.all([
          invoke<ComplianceStatus>("get_compliance_status"),
          invoke<AdminStatus>("get_admin_status", {}),
        ])
      )
      .then(([c, a]) => { setCompliance(c); setAdminStatus(a); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const startAction = async (request: PrivilegedActionRequest) => {
    setActionState("previewing");
    setActionResult(null);
    setPendingRequest(request);
    const p = await invoke<PrivilegedActionPreview>("preview_privileged_action", { request });
    setPreview(p);
  };

  const confirmAction = async () => {
    if (!pendingRequest) return;
    setActionState("executing");
    const result = await invoke<PrivilegedActionResult>("execute_privileged_action", {
      request: pendingRequest,
      approved: true,
    });
    setActionResult(result);
    setActionState("done");
    setPreview(null);
    invoke<ComplianceStatus>("get_compliance_status").then(setCompliance).catch(() => {});
  };

  const toggleEvents = async () => {
    if (!showEvents && events.length === 0) {
      setEventsLoading(true);
      const evts = await invoke<SystemEvent[]>("get_recent_events").catch(() => []);
      setEvents(evts);
      setEventsLoading(false);
    }
    setShowEvents((s) => !s);
  };

  const cancelAction = () => {
    setActionState("idle");
    setPreview(null);
    setPendingRequest(null);
    setActionResult(null);
  };


  return (
    <div className="security-panel">
      <div className="settings-header">
        <div>
          <div className="settings-title">Security</div>
          <div className="settings-subtitle">
            {adminStatus?.is_admin
              ? "Admin — compliance status and device controls."
              : "View only — contact IT to make changes."}
          </div>
        </div>
        {adminStatus?.is_admin && <span className="provider-status ok">Admin</span>}
      </div>

      {loading ? (
        <div className="sec-loading">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          Checking device security…
        </div>
      ) : (
        <>
          {/* Summary bar */}
          {(() => {
            const issues = [
              !compliance?.firewall_on,
              !compliance?.bitlocker_on,
              !compliance?.defender_enabled,
              compliance?.pending_reboot,
              !compliance?.spooler_running,
              (compliance?.recent_errors ?? 0) >= 10,
            ].filter(Boolean).length;
            return (
              <div className={`sec-summary ${issues === 0 ? "sec-summary-ok" : issues >= 3 ? "sec-summary-critical" : "sec-summary-warn"}`}>
                {issues === 0
                  ? "All security checks passed"
                  : `${issues} issue${issues > 1 ? "s" : ""} detected — review below`}
              </div>
            );
          })()}

          <div className="sec-grid">
            <div className={`sec-card ${compliance?.firewall_on ? "sec-ok" : "sec-critical"}`}>
              <div className="sec-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              </div>
              <div className="sec-card-body">
                <div className="sec-card-title">Firewall</div>
                <div className="sec-card-detail">{compliance?.firewall_on ? "All network profiles protected" : "Firewall is off — contact IT immediately"}</div>
              </div>
              <span className={`sec-badge ${compliance?.firewall_on ? "badge-ok" : "badge-critical"}`}>{compliance?.firewall_on ? "On" : "Off"}</span>
            </div>

            <div className={`sec-card ${compliance?.bitlocker_on ? "sec-ok" : "sec-critical"}`}>
              <div className="sec-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </div>
              <div className="sec-card-body">
                <div className="sec-card-title">Disk Encryption</div>
                <div className="sec-card-detail">{compliance?.bitlocker_on ? "BitLocker active on C:" : "Drive not encrypted — contact IT"}</div>
              </div>
              <span className={`sec-badge ${compliance?.bitlocker_on ? "badge-ok" : "badge-critical"}`}>{compliance?.bitlocker_on ? "Active" : "Off"}</span>
            </div>

            <div className={`sec-card ${compliance?.defender_enabled ? "sec-ok" : "sec-critical"}`}>
              <div className="sec-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>
              </div>
              <div className="sec-card-body">
                <div className="sec-card-title">Antivirus</div>
                <div className="sec-card-detail">{compliance?.defender_enabled ? "Windows Defender real-time protection on" : "Real-time protection disabled — security incident"}</div>
              </div>
              <span className={`sec-badge ${compliance?.defender_enabled ? "badge-ok" : "badge-critical"}`}>{compliance?.defender_enabled ? "Protected" : "Disabled"}</span>
            </div>

            <div className={`sec-card ${!compliance?.pending_reboot ? "sec-ok" : "sec-warn"}`}>
              <div className="sec-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              </div>
              <div className="sec-card-body">
                <div className="sec-card-title">Windows Update</div>
                <div className="sec-card-detail">{compliance?.pending_reboot ? "Reboot required to finish installing updates" : "No reboot pending"}</div>
              </div>
              <span className={`sec-badge ${!compliance?.pending_reboot ? "badge-ok" : "badge-warn"}`}>{compliance?.pending_reboot ? "Reboot needed" : "Up to date"}</span>
            </div>

            <div className={`sec-card ${compliance?.spooler_running ? "sec-ok" : "sec-warn"}`}>
              <div className="sec-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
              </div>
              <div className="sec-card-body">
                <div className="sec-card-title">Print Spooler</div>
                <div className="sec-card-detail">{compliance?.spooler_running ? "Spooler service running normally" : "Spooler stopped — printing unavailable, contact IT"}</div>
              </div>
              <span className={`sec-badge ${compliance?.spooler_running ? "badge-ok" : "badge-warn"}`}>{compliance?.spooler_running ? "Running" : "Stopped"}</span>
            </div>

            <div
              className={`sec-card ${(compliance?.recent_errors ?? 0) < 10 ? "sec-ok" : "sec-warn"} sec-card-clickable`}
              onClick={toggleEvents}
              style={{ cursor: "pointer", flexWrap: "wrap" }}
            >
              <div className="sec-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              </div>
              <div className="sec-card-body">
                <div className="sec-card-title">System Events {showEvents ? "▲" : "▼"}</div>
                <div className="sec-card-detail">{compliance?.recent_errors ?? 0} errors/warnings in last 50 System log events — click to expand</div>
              </div>
              <span className={`sec-badge ${(compliance?.recent_errors ?? 0) < 10 ? "badge-ok" : "badge-warn"}`}>{compliance?.recent_errors ?? 0} events</span>
              {showEvents && (
                <div className="sec-events-list" onClick={(e) => e.stopPropagation()}>
                  {eventsLoading ? (
                    <div className="sec-events-loading">Loading events…</div>
                  ) : events.length === 0 ? (
                    <div className="sec-events-empty">No errors or warnings found.</div>
                  ) : (
                    events.map((ev, i) => (
                      <div key={i} className={`sec-event-row ${ev.level === "Error" ? "sec-event-error" : "sec-event-warn"}`}>
                        <span className="sec-event-time">{ev.time}</span>
                        <span className="sec-event-level">{ev.level}</span>
                        <span className="sec-event-source">{ev.source}</span>
                        <span className="sec-event-msg">{ev.message}</span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            <div className="sec-card sec-info">
              <div className="sec-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"><circle cx="12" cy="12" r="10"/><path d="M4.93 4.93l14.14 14.14"/><path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z"/></svg>
              </div>
              <div className="sec-card-body">
                <div className="sec-card-title">Network</div>
                <div className="sec-card-detail">{compliance?.active_connections ?? 0} active TCP connections</div>
              </div>
              <span className="sec-badge badge-info">{compliance?.active_connections ?? 0}</span>
            </div>
          </div>
        </>
      )}

      {!loading && adminStatus?.is_admin && (
        <div className="admin-section">
          <div className="settings-section-title">Admin actions</div>
          <div className="settings-line">All actions require UAC confirmation and are logged.</div>

          {actionState === "idle" && (
            <div className="admin-actions">
              {ADMIN_ACTIONS.map((a) => (
                <button key={a.label} className="btn-save" onClick={() => startAction(a.request)}>
                  {a.label}
                </button>
              ))}
            </div>
          )}

          {actionState === "previewing" && preview && (
            <div className="action-preview">
              <div className="preview-label">{preview.action_label}</div>
              <div className="preview-reason">{preview.reason}</div>
              <div className="preview-path">Via: {preview.execution_path}</div>
              <div className="preview-buttons">
                <button className="btn-save" onClick={confirmAction}>Confirm — run with UAC</button>
                <button className="btn-clear" onClick={cancelAction}>Cancel</button>
              </div>
            </div>
          )}

          {actionState === "executing" && (
            <div className="compliance-loading">Running with elevated privileges…</div>
          )}

          {actionState === "done" && actionResult && (
            <div className={`action-result result-${actionResult.status}`}>
              <div>{actionResult.message}</div>
              {actionResult.details && <div className="result-detail">{actionResult.details}</div>}
              <button className="btn-clear" onClick={cancelAction}>Done</button>
            </div>
          )}
        </div>
      )}

      {!loading && !adminStatus?.is_admin && (
        <div className="admin-section">
          <div className="settings-line">
            Need to change a security setting? Use <strong>Help</strong> to chat with IT,
            or go to <strong>Incidents</strong> to raise a ticket.
          </div>
        </div>
      )}
    </div>
  );
}
