import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

export default function SecurityPanel() {
  const [firewall, setFirewall] = useState<string>("");
  const [services, setServices] = useState<string>("");
  const [users, setUsers] = useState<string>("");
  const [auditLog, setAuditLog] = useState<string>("");
  const [connections, setConnections] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [refreshing, setRefreshing] = useState(false);
  const [firewallEnabled, setFirewallEnabled] = useState<boolean | null>(null);
  const [serviceAction, setServiceAction] = useState<{ name: string; action: string }>({ name: "", action: "start" });
  const [userLock, setUserLock] = useState<{ name: string; lock: boolean }>({ name: "", lock: false });
  const [terminatePid, setTerminatePid] = useState<string>("");

  const refreshAll = () => {
    setRefreshing(true);
    Promise.all([
      invoke<string>("get_firewall_status").then((fw) => {
        setFirewall(fw);
        setFirewallEnabled(/enabled|on|active/i.test(fw));
      }),
      invoke<string>("get_services").then(setServices),
      invoke<string>("get_users").then(setUsers),
      invoke<string>("get_audit_log").then(setAuditLog),
      invoke<string>("get_network_connections").then(setConnections),
    ]).catch(e => setError(String(e))).finally(() => setRefreshing(false));
  };

  useEffect(() => { refreshAll(); }, []);

  return (
    <div className="security-panel">
      <h2>Security & Privacy</h2>
      <button className="btn-refresh" onClick={refreshAll} disabled={refreshing}>
        {refreshing ? "Refreshing…" : "↻ Refresh"}
      </button>
      {error && <div className="security-error">{error ? "Could not refresh. Please try again." : null}</div>}
      <div className="security-grid">
        <section>
          <h3>Firewall</h3>
          <div style={{display:'flex',alignItems:'center',gap:8}}>
            <span style={{fontSize:24}}>{firewallEnabled ? "🟢" : "🔴"}</span>
            <span>{firewallEnabled ? "Firewall is ON" : "Firewall is OFF"}</span>
          </div>
          <button onClick={() => invoke<string>("set_firewall_enabled", { enabled: !(firewallEnabled ?? false) }).then(refreshAll)}>
            {firewallEnabled ? "Turn Off" : "Turn On"}
          </button>
          <div style={{fontSize:12,color:'#888',marginTop:8}}>Helps protect your computer from unauthorized access.</div>
        </section>
        <section>
          <h3>Services</h3>
          <div style={{fontSize:14,marginBottom:8}}>Start or stop important background apps.</div>
          <div className="input-row">
            <input
              type="text"
              placeholder="Service name (e.g. bluetooth)"
              value={serviceAction.name}
              onChange={e => setServiceAction({ ...serviceAction, name: e.target.value })}
            />
            <select
              value={serviceAction.action}
              onChange={e => setServiceAction({ ...serviceAction, action: e.target.value })}
            >
              <option value="start">Start</option>
              <option value="stop">Stop</option>
              <option value="restart">Restart</option>
            </select>
            <button onClick={() => invoke<string>("control_service", serviceAction).then(refreshAll)} disabled={!serviceAction.name}>Apply</button>
          </div>
        </section>
        <section>
          <h3>User Accounts</h3>
          <div style={{fontSize:14,marginBottom:8}}>Lock or unlock user accounts for safety.</div>
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
            <button onClick={() => invoke<string>("lock_user", userLock).then(refreshAll)} disabled={!userLock.name}>Apply</button>
          </div>
        </section>
        <section>
          <h3>Audit Log</h3>
          <div style={{fontSize:14,marginBottom:8}}>Recent security events (for advanced users).</div>
          <pre style={{maxHeight:120,overflow:'auto',background:'#181824',padding:8,borderRadius:8,fontSize:12}}>{auditLog || "No recent events."}</pre>
        </section>
        <section>
          <h3>Network Connections</h3>
          <div style={{fontSize:14,marginBottom:8}}>See and end active connections.</div>
          <pre style={{maxHeight:120,overflow:'auto',background:'#181824',padding:8,borderRadius:8,fontSize:12}}>{connections || "No active connections."}</pre>
          <div className="input-row">
            <input
              type="text"
              placeholder="PID to end (advanced)"
              value={terminatePid}
              onChange={e => setTerminatePid(e.target.value)}
            />
            <button onClick={() => invoke<string>("terminate_connection", { pid: Number(terminatePid) }).then(refreshAll)} disabled={!terminatePid}>End Connection</button>
          </div>
        </section>
      </div>
    </div>
  );
}
