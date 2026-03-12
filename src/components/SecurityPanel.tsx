import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

type ServiceAction = "start" | "stop" | "restart";

type PrivilegedActionRequest =
  | { kind: "firewall"; enabled: boolean }
  | { kind: "service"; name: string; action: ServiceAction }
  | { kind: "user_lock"; name: string; lock: boolean }
  | { kind: "terminate_process"; pid: number };

type PrivilegedActionPreview = {
  action_type: string;
  action_label: string;
  target: string;
  reason: string;
  approval_required: boolean;
  mutating: boolean;
  platform: string;
  execution_path: string;
};

type PrivilegedActionResult = {
  status: string;
  action_type: string;
  action_label: string;
  target: string;
  message: string;
  details?: string | null;
  approval_required: boolean;
  mutating: boolean;
};

export default function SecurityPanel() {
  const [auditLog, setAuditLog] = useState<string>("");
  const [connections, setConnections] = useState<string>("");
  const [services, setServices] = useState<string>("");
  const [users, setUsers] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [firewallEnabled, setFirewallEnabled] = useState<boolean | null>(null);
  const [serviceAction, setServiceAction] = useState<{ name: string; action: ServiceAction }>({ name: "", action: "start" });
  const [userLock, setUserLock] = useState<{ name: string; lock: boolean }>({ name: "", lock: false });
  const [terminatePid, setTerminatePid] = useState<string>("");
  const [pendingAction, setPendingAction] = useState<{ request: PrivilegedActionRequest; preview: PrivilegedActionPreview } | null>(null);
  const [actionResult, setActionResult] = useState<PrivilegedActionResult | null>(null);

  const refreshAll = () => {
    setRefreshing(true);
    setError("");
    Promise.all([
      invoke<string>("get_firewall_status").then((fw) => {
        setFirewallEnabled(/enabled|on|active/i.test(fw));
      }),
      invoke<string>("get_services").then(setServices),
      invoke<string>("get_users").then(setUsers),
      invoke<string>("get_audit_log").then(setAuditLog),
      invoke<string>("get_network_connections").then(setConnections),
    ]).catch(e => setError(String(e))).finally(() => setRefreshing(false));
  };

  useEffect(() => { refreshAll(); }, []);

  const queuePrivilegedAction = async (request: PrivilegedActionRequest) => {
    setActionResult(null);
    setError("");
    try {
      const preview = await invoke<PrivilegedActionPreview>("preview_privileged_action", { request });
      setPendingAction({ request, preview });
    } catch (e) {
      setError(String(e));
    }
  };

  const approveAction = async () => {
    if (!pendingAction) return;
    setSubmitting(true);
    try {
      const result = await invoke<PrivilegedActionResult>("execute_privileged_action", {
        request: pendingAction.request,
        approved: true,
      });
      setActionResult(result);
      setPendingAction(null);
      refreshAll();
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const cancelAction = () => {
    if (!pendingAction) return;
    setActionResult({
      status: "denied",
      action_type: pendingAction.preview.action_type,
      action_label: pendingAction.preview.action_label,
      target: pendingAction.preview.target,
      message: "Action canceled before execution.",
      details: null,
      approval_required: true,
      mutating: true,
    });
    setPendingAction(null);
  };

  return (
    <div className="security-panel">
      <h2>Security & Privacy</h2>
      <div style={{ fontSize: 13, color: "#888", marginBottom: 12 }}>
        Tier 1 operations below are read-only. Tier 2 actions require explicit approval before Caret will execute them.
      </div>
      <button className="btn-refresh" onClick={refreshAll} disabled={refreshing}>
        {refreshing ? "Refreshing…" : "↻ Refresh"}
      </button>
      {error && <div className="security-error">{error}</div>}
      {actionResult && (
        <div style={{ marginTop: 12, padding: 12, borderRadius: 10, background: "#181824", border: "1px solid #2a2a40" }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>
            {actionResult.status === "executed" ? "Action completed" : "Action result"}
          </div>
          <div style={{ fontSize: 13 }}>
            {actionResult.action_label} on {actionResult.target}: {actionResult.message}
          </div>
          {actionResult.details && (
            <pre style={{ marginTop: 8, maxHeight: 120, overflow: "auto", fontSize: 12, color: "#aaa" }}>
              {actionResult.details}
            </pre>
          )}
        </div>
      )}
      {pendingAction && (
        <div style={{ marginTop: 12, padding: 14, borderRadius: 12, background: "#141420", border: "1px solid #7c6aff" }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Approval required</div>
          <div style={{ fontSize: 13, marginBottom: 6 }}>
            <b>Action:</b> {pendingAction.preview.action_label}
          </div>
          <div style={{ fontSize: 13, marginBottom: 6 }}>
            <b>Target:</b> {pendingAction.preview.target}
          </div>
          <div style={{ fontSize: 13, marginBottom: 6 }}>
            <b>Reason:</b> {pendingAction.preview.reason}
          </div>
          <div style={{ fontSize: 13, marginBottom: 10 }}>
            <b>Mutating:</b> {pendingAction.preview.mutating ? "Yes" : "No"} | <b>Platform:</b> {pendingAction.preview.platform}
          </div>
          <div style={{ fontSize: 13, marginBottom: 10 }}>
            <b>Execution path:</b> {pendingAction.preview.execution_path}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={approveAction} disabled={submitting}>
              {submitting ? "Executing…" : "Approve and execute"}
            </button>
            <button onClick={cancelAction} disabled={submitting}>Cancel</button>
          </div>
        </div>
      )}
      <div className="security-grid">
        <section>
          <h3>Firewall Status</h3>
          <div style={{display:'flex',alignItems:'center',gap:8}}>
            <span style={{fontSize:24}}>{firewallEnabled ? "🟢" : "🔴"}</span>
            <span>{firewallEnabled ? "Firewall is ON" : "Firewall is OFF"}</span>
          </div>
          <div style={{fontSize:12,color:'#888',marginTop:8}}>Helps protect your computer from unauthorized access.</div>
        </section>
        <section>
          <h3>Running Services</h3>
          <div style={{fontSize:14,marginBottom:8}}>Read-only list of currently running services.</div>
          <pre style={{maxHeight:120,overflow:'auto',background:'#181824',padding:8,borderRadius:8,fontSize:12}}>{services || "No services found."}</pre>
        </section>
        <section>
          <h3>User Accounts</h3>
          <div style={{fontSize:14,marginBottom:8}}>Read-only list of local users.</div>
          <pre style={{maxHeight:120,overflow:'auto',background:'#181824',padding:8,borderRadius:8,fontSize:12}}>{users || "No users found."}</pre>
        </section>
        <section>
          <h3>Audit Log</h3>
          <div style={{fontSize:14,marginBottom:8}}>Recent security events (for advanced users).</div>
          <pre style={{maxHeight:120,overflow:'auto',background:'#181824',padding:8,borderRadius:8,fontSize:12}}>{auditLog || "No recent events."}</pre>
        </section>
        <section>
          <h3>Network Connections</h3>
          <div style={{fontSize:14,marginBottom:8}}>Read-only view of active connections.</div>
          <pre style={{maxHeight:120,overflow:'auto',background:'#181824',padding:8,borderRadius:8,fontSize:12}}>{connections || "No active connections."}</pre>
        </section>
        <section>
          <h3>Privileged Actions</h3>
          <div style={{fontSize:14,marginBottom:8}}>Every action below requires an explicit approval step.</div>
          <div className="input-row" style={{ marginBottom: 10 }}>
            <button onClick={() => queuePrivilegedAction({ kind: "firewall", enabled: !(firewallEnabled ?? false) })}>
              {firewallEnabled ? "Request firewall disable" : "Request firewall enable"}
            </button>
          </div>
          <div className="input-row">
            <input
              type="text"
              placeholder="Service name (e.g. bluetooth)"
              value={serviceAction.name}
              onChange={e => setServiceAction({ ...serviceAction, name: e.target.value })}
            />
            <select
              value={serviceAction.action}
              onChange={e => setServiceAction({ ...serviceAction, action: e.target.value as ServiceAction })}
            >
              <option value="start">Start</option>
              <option value="stop">Stop</option>
              <option value="restart">Restart</option>
            </select>
            <button
              onClick={() => queuePrivilegedAction({ kind: "service", name: serviceAction.name, action: serviceAction.action })}
              disabled={!serviceAction.name}
            >
              Request service action
            </button>
          </div>
          <div className="input-row">
            <input
              type="text"
              placeholder="User name"
              value={userLock.name}
              onChange={e => setUserLock({ ...userLock, name: e.target.value })}
            />
            <select
              value={userLock.lock ? "lock" : "unlock"}
              onChange={e => setUserLock({ ...userLock, lock: e.target.value === "lock" })}
            >
              <option value="lock">Lock</option>
              <option value="unlock">Unlock</option>
            </select>
            <button
              onClick={() => queuePrivilegedAction({ kind: "user_lock", name: userLock.name, lock: userLock.lock })}
              disabled={!userLock.name}
            >
              Request user action
            </button>
          </div>
          <div className="input-row">
            <input
              type="text"
              placeholder="PID to end (advanced)"
              value={terminatePid}
              onChange={e => setTerminatePid(e.target.value)}
            />
            <button
              onClick={() => queuePrivilegedAction({ kind: "terminate_process", pid: Number(terminatePid) })}
              disabled={!terminatePid}
            >
              Request process termination
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
