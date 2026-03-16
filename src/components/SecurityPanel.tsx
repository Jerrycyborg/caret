import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface ComplianceStatus {
  firewall_on: boolean;
  bitlocker_on: boolean;
  active_connections: number;
  recent_errors: number;
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

  const cancelAction = () => {
    setActionState("idle");
    setPreview(null);
    setPendingRequest(null);
    setActionResult(null);
  };

  const dot = (ok: boolean, info = false) => (
    <span className={`compliance-dot ${info ? "dot-info" : ok ? "dot-ok" : "dot-warn"}`} />
  );

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

      <div className="compliance-grid">
        {loading ? (
          <div className="compliance-loading">Checking device…</div>
        ) : (
          <>
            <div className="compliance-row">
              {dot(!!compliance?.firewall_on)}
              <span className="compliance-label">Firewall</span>
              <span className="compliance-value">
                {compliance?.firewall_on ? "On" : "Off — contact IT"}
              </span>
            </div>
            <div className="compliance-row">
              {dot(!!compliance?.bitlocker_on)}
              <span className="compliance-label">Disk encryption</span>
              <span className="compliance-value">
                {compliance?.bitlocker_on ? "BitLocker active" : "Not encrypted — contact IT"}
              </span>
            </div>
            <div className="compliance-row">
              {dot((compliance?.recent_errors ?? 0) < 10)}
              <span className="compliance-label">System events</span>
              <span className="compliance-value">
                {compliance?.recent_errors ?? 0} errors/warnings in last 50 events
              </span>
            </div>
            <div className="compliance-row">
              {dot(true, true)}
              <span className="compliance-label">Network</span>
              <span className="compliance-value">
                {compliance?.active_connections ?? 0} active connections
              </span>
            </div>
          </>
        )}
      </div>

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
