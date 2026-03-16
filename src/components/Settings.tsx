import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface KeyStatus {
  provider: string;
  masked: string;
  updated_at: string;
}

interface ProviderDef {
  id: string;
  name: string;
  icon: string;
  desc: string;
  placeholder: string;
}

type ConfigState = {
  org: { org_name: string; environment_label: string };
  ticketing: {
    adapter_type: string;
    jira_base_url: string;
    jira_project_key: string;
    jira_issue_type: string;
    jira_user_email: string;
    jira_api_token: string;
    jira_default_labels: string[];
    jira_default_components: string[];
  };
  support_policy: {
    auto_fix_enabled: boolean;
    default_escalation_policy: string;
    allowed_remediation_classes: string[];
  };
  management: {
    server_url: string;
    admin_group: string;
  };
};

const PROVIDERS: ProviderDef[] = [
  { id: "ollama", name: "Local model", icon: "🦙", desc: "Optional local runtime. Keep Caret usable even if no model is configured.", placeholder: "http://localhost:11434" },
  { id: "openai", name: "OpenAI", icon: "⚡", desc: "Hosted assistant model access.", placeholder: "sk-..." },
  { id: "anthropic", name: "Anthropic", icon: "🧠", desc: "Claude family models.", placeholder: "sk-ant-..." },
  { id: "gemini", name: "Google Gemini", icon: "✨", desc: "Gemini API access.", placeholder: "AIza..." },
  { id: "azure", name: "Azure OpenAI", icon: "☁️", desc: "Enterprise OpenAI via Azure.", placeholder: "Azure API key" },
];

const BACKEND_URL = "http://localhost:8000";

const EMPTY_CONFIG: ConfigState = {
  org: { org_name: "", environment_label: "" },
  ticketing: {
    adapter_type: "jira",
    jira_base_url: "",
    jira_project_key: "",
    jira_issue_type: "Task",
    jira_user_email: "",
    jira_api_token: "",
    jira_default_labels: [],
    jira_default_components: [],
  },
  support_policy: {
    auto_fix_enabled: true,
    default_escalation_policy: "manual_review",
    allowed_remediation_classes: ["cleanup_candidates", "diagnostics", "readiness_refresh"],
  },
  management: {
    server_url: "",
    admin_group: "",
  },
};

type MgmtStatus = "not_configured" | "ok" | "unreachable" | "error";

export default function Settings() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [keyStatuses, setKeyStatuses] = useState<Record<string, KeyStatus>>({});
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [config, setConfig] = useState<ConfigState>(EMPTY_CONFIG);
  const [mgmtStatus, setMgmtStatus] = useState<MgmtStatus>("not_configured");
  const [jiraOauth, setJiraOauth] = useState<{ app_configured: boolean; connected: boolean; cloud_id?: string; updated_at?: string } | null>(null);

  useEffect(() => {
    // Resolve admin status first using configured admin_group if available
    fetch(`${BACKEND_URL}/v1/settings/config`)
      .then((r) => r.json())
      .then(async (data) => {
        const adminGroup: string = data.config?.management?.admin_group ?? "";
        const status = await invoke<{ is_admin: boolean }>("get_admin_status", { adminGroup: adminGroup || undefined });
        setIsAdmin(status.is_admin);
        if (status.is_admin) {
          setConfig({ ...EMPTY_CONFIG, ...(data.config ?? {}) });
        }
      })
      .catch(() => setIsAdmin(false));

    fetch(`${BACKEND_URL}/v1/settings/keys`)
      .then((r) => r.json())
      .then((data) => {
        const map: Record<string, KeyStatus> = {};
        for (const key of data.keys ?? []) map[key.provider] = key;
        setKeyStatuses(map);
      })
      .catch(() => {});

    fetch(`${BACKEND_URL}/v1/management/status`)
      .then((r) => r.json())
      .then((data) => setMgmtStatus(data.last_status ?? "not_configured"))
      .catch(() => {});

    fetch(`${BACKEND_URL}/v1/settings/jira/oauth/status`)
      .then((r) => r.json())
      .then((data) => setJiraOauth(data))
      .catch(() => {});
  }, []);

  const showFeedback = (key: string, msg: string, ms = 2000) => {
    setFeedback((prev) => ({ ...prev, [key]: msg }));
    setTimeout(() => setFeedback((prev) => ({ ...prev, [key]: "" })), ms);
  };

  const saveKey = async (provider: string) => {
    const value = inputs[provider]?.trim();
    if (!value) return;
    setSaving((prev) => ({ ...prev, [provider]: true }));
    try {
      const res = await fetch(`${BACKEND_URL}/v1/settings/keys/${provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) throw new Error();
      const masked = value.length <= 8 ? "*".repeat(value.length) : value.slice(0, 4) + "****" + value.slice(-4);
      setKeyStatuses((prev) => ({ ...prev, [provider]: { provider, masked, updated_at: new Date().toISOString() } }));
      setInputs((prev) => ({ ...prev, [provider]: "" }));
      showFeedback(provider, "Saved");
    } catch {
      showFeedback(provider, "Error");
    } finally {
      setSaving((prev) => ({ ...prev, [provider]: false }));
    }
  };

  const clearKey = async (provider: string) => {
    await fetch(`${BACKEND_URL}/v1/settings/keys/${provider}`, { method: "DELETE" });
    setKeyStatuses((prev) => {
      const next = { ...prev };
      delete next[provider];
      return next;
    });
    showFeedback(provider, "Cleared");
  };

  const saveSection = async (section: keyof ConfigState) => {
    setSaving((prev) => ({ ...prev, [section]: true }));
    try {
      const res = await fetch(`${BACKEND_URL}/v1/settings/config/${section}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: config[section] }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Save failed");
      setConfig((prev) => ({ ...prev, [section]: data.config }));
      showFeedback(section, "Saved");
    } catch {
      showFeedback(section, "Error");
    } finally {
      setSaving((prev) => ({ ...prev, [section]: false }));
    }
  };

  if (isAdmin === null) {
    return <div className="settings"><div className="settings-header"><div className="settings-title">Settings</div></div><div className="compliance-loading">Checking access…</div></div>;
  }

  if (!isAdmin) {
    return (
      <div className="settings">
        <div className="settings-header">
          <div>
            <div className="settings-title">Settings</div>
            <div className="settings-subtitle">Managed by your IT department.</div>
          </div>
        </div>
        <div className="admin-section">
          <div className="settings-line">Configuration is managed centrally by IT. Contact your IT helpdesk if you need a change.</div>
          <div className="settings-line" style={{ marginTop: "0.5rem" }}>
            Management server: <strong>{mgmtStatus === "ok" ? "Connected" : mgmtStatus === "unreachable" ? "Unreachable" : "Not configured"}</strong>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="settings">
      <div className="settings-header">
        <div>
          <div className="settings-title">Settings</div>
          <div className="settings-subtitle">Model keys, Jira ticketing, support policy, and deployment identity.</div>
        </div>
      </div>

      <div className="settings-layout">
        <section className="settings-panel">
          <div className="settings-section-title">Models</div>
          <div className="settings-scroll">
            {PROVIDERS.map((provider) => {
              const status = keyStatuses[provider.id];
              const isConfigured = !!status;
              return (
                <div key={provider.id} className={`provider-card${isConfigured ? " configured" : ""}`}>
                  <div className="provider-card-header">
                    <div className="provider-icon">{provider.icon}</div>
                    <div>
                      <div className="provider-name">{provider.name}</div>
                      <div className="provider-desc">{provider.desc}</div>
                    </div>
                    <span className={`provider-status ${isConfigured ? "ok" : "missing"}`}>{isConfigured ? "Configured" : "Not set"}</span>
                  </div>
                  {isConfigured && <div className="provider-current">Current: {status.masked}</div>}
                  <div className="provider-input-row">
                    <input
                      type="password"
                      className="provider-input"
                      placeholder={provider.placeholder}
                      value={inputs[provider.id] ?? ""}
                      onChange={(e) => setInputs((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                      onKeyDown={(e) => e.key === "Enter" && saveKey(provider.id)}
                      autoComplete="off"
                    />
                    <button className="btn-save" onClick={() => saveKey(provider.id)} disabled={!inputs[provider.id]?.trim() || saving[provider.id]}>
                      {feedback[provider.id] || (saving[provider.id] ? "…" : "Save")}
                    </button>
                    {isConfigured && <button className="btn-clear" onClick={() => clearKey(provider.id)}>Clear</button>}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="settings-panel">
          <div className="settings-section-title">Org and Ticketing</div>
          <div className="settings-scroll">
            <div className="settings-card">
              <strong>Deployment</strong>
              <div className="provider-input-row settings-form-row">
                <input className="provider-input" placeholder="Org name" value={config.org.org_name} onChange={(e) => setConfig((prev) => ({ ...prev, org: { ...prev.org, org_name: e.target.value } }))} />
                <input className="provider-input" placeholder="Environment label" value={config.org.environment_label} onChange={(e) => setConfig((prev) => ({ ...prev, org: { ...prev.org, environment_label: e.target.value } }))} />
              </div>
              <button className="btn-save" onClick={() => saveSection("org")} disabled={saving.org}>{feedback.org || (saving.org ? "…" : "Save org")}</button>
            </div>

            <div className="settings-card">
              <strong>Jira ticketing</strong>

              <div className="provider-card-header" style={{ marginBottom: "0.5rem" }}>
                <div>
                  {jiraOauth?.connected ? (
                    <span className="provider-status ok">Connected · {jiraOauth.cloud_id}</span>
                  ) : jiraOauth?.app_configured === false ? (
                    <span className="provider-status missing">OAuth not configured — contact IT</span>
                  ) : (
                    <span className="provider-status missing">Not signed in</span>
                  )}
                </div>
                {jiraOauth?.connected ? (
                  <button className="btn-clear" onClick={async () => {
                    await fetch(`${BACKEND_URL}/v1/settings/jira/oauth`, { method: "DELETE" });
                    setJiraOauth({ connected: false, app_configured: jiraOauth.app_configured });
                  }}>Sign out</button>
                ) : jiraOauth?.app_configured ? (
                  <button className="btn-save" onClick={async () => {
                    showFeedback("jira_oauth", "Opening browser…");
                    try {
                      const res = await fetch(`${BACKEND_URL}/v1/settings/jira/oauth/start`, { method: "POST" });
                      const data = await res.json();
                      if (!res.ok) throw new Error(data.detail ?? "Failed");
                      await invoke("plugin:opener|open_url", { url: data.auth_url });
                      showFeedback("jira_oauth", "Complete login in browser…", 8000);
                      setTimeout(async () => {
                        const r = await fetch(`${BACKEND_URL}/v1/settings/jira/oauth/status`);
                        setJiraOauth(await r.json());
                      }, 6000);
                    } catch (e) {
                      showFeedback("jira_oauth", String(e).replace("Error: ", ""), 5000);
                    }
                  }}>{feedback.jira_oauth || "Sign in with Jira"}</button>
                ) : null}
              </div>

              <div className="settings-line"><strong>API token (fallback if OAuth not set up)</strong></div>
              <div className="provider-input-row settings-form-row">
                <input className="provider-input" placeholder="Jira base URL" value={config.ticketing.jira_base_url} onChange={(e) => setConfig((prev) => ({ ...prev, ticketing: { ...prev.ticketing, jira_base_url: e.target.value } }))} />
                <input className="provider-input" placeholder="Project key" value={config.ticketing.jira_project_key} onChange={(e) => setConfig((prev) => ({ ...prev, ticketing: { ...prev.ticketing, jira_project_key: e.target.value } }))} />
              </div>
              <div className="provider-input-row settings-form-row">
                <input className="provider-input" placeholder="Issue type" value={config.ticketing.jira_issue_type} onChange={(e) => setConfig((prev) => ({ ...prev, ticketing: { ...prev.ticketing, jira_issue_type: e.target.value } }))} />
                <input className="provider-input" placeholder="Jira user email" value={config.ticketing.jira_user_email} onChange={(e) => setConfig((prev) => ({ ...prev, ticketing: { ...prev.ticketing, jira_user_email: e.target.value } }))} />
              </div>
              <div className="provider-input-row settings-form-row">
                <input className="provider-input" placeholder="Jira API token" value={config.ticketing.jira_api_token} onChange={(e) => setConfig((prev) => ({ ...prev, ticketing: { ...prev.ticketing, jira_api_token: e.target.value } }))} />
                <input className="provider-input" placeholder="Labels (comma separated)" value={config.ticketing.jira_default_labels.join(",")} onChange={(e) => setConfig((prev) => ({ ...prev, ticketing: { ...prev.ticketing, jira_default_labels: e.target.value.split(",").map((item) => item.trim()).filter(Boolean) } }))} />
              </div>
              <div className="provider-input-row settings-form-row">
                <input className="provider-input" placeholder="Components (comma separated)" value={config.ticketing.jira_default_components.join(",")} onChange={(e) => setConfig((prev) => ({ ...prev, ticketing: { ...prev.ticketing, jira_default_components: e.target.value.split(",").map((item) => item.trim()).filter(Boolean) } }))} />
              </div>
              <div className="provider-input-row">
                <button className="btn-save" onClick={() => saveSection("ticketing")} disabled={saving.ticketing}>{feedback.ticketing || (saving.ticketing ? "…" : "Save ticketing")}</button>
                <button className="btn-clear" onClick={async () => {
                  showFeedback("ticketing_test", "Testing…");
                  try {
                    const res = await fetch(`${BACKEND_URL}/v1/settings/jira/test`, { method: "POST" });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail ?? "Failed");
                    showFeedback("ticketing_test", `Connected as ${data.authenticated_as}`, 5000);
                  } catch (e) {
                    showFeedback("ticketing_test", String(e).replace("Error: ", ""), 5000);
                  }
                }}>{feedback.ticketing_test || "Test connection"}</button>
              </div>
            </div>

            <div className="settings-card">
              <strong>Management server</strong>
              <div className="settings-line">Central control plane URL. Leave empty to run standalone. Set by your IT admin at deployment.</div>
              <div className="provider-input-row settings-form-row">
                <input
                  className="provider-input"
                  placeholder="https://caret.your-org.com"
                  value={config.management.server_url}
                  onChange={(e) => setConfig((prev) => ({ ...prev, management: { ...prev.management, server_url: e.target.value } }))}
                />
                <span className={`provider-status ${mgmtStatus === "ok" ? "ok" : "missing"}`}>
                  {mgmtStatus === "ok" ? "Connected" : mgmtStatus === "unreachable" ? "Unreachable" : mgmtStatus === "error" ? "Error" : "Not configured"}
                </span>
              </div>
              <div className="provider-input-row settings-form-row">
                <input
                  className="provider-input"
                  placeholder="AD group SAM name (e.g. ROL-ADM-Admins) — leave empty to use local admin"
                  value={config.management.admin_group}
                  onChange={(e) => setConfig((prev) => ({ ...prev, management: { ...prev.management, admin_group: e.target.value } }))}
                />
              </div>
              <button className="btn-save" onClick={() => saveSection("management")} disabled={saving.management}>{feedback.management || (saving.management ? "…" : "Save")}</button>
            </div>
          </div>
        </section>

        <section className="settings-panel">
          <div className="settings-section-title">Support Policy</div>
          <div className="settings-scroll">
            <div className="settings-card">
              <strong>Auto-fix policy</strong>
              <div className="settings-line">Caret stays lightweight by keeping support deterministic and policy-driven.</div>
              <label className="settings-toggle">
                <input type="checkbox" checked={config.support_policy.auto_fix_enabled} onChange={(e) => setConfig((prev) => ({ ...prev, support_policy: { ...prev.support_policy, auto_fix_enabled: e.target.checked } }))} />
                <span>Enable safe auto-fix queue runner</span>
              </label>
              <div className="provider-input-row settings-form-row">
                <input className="provider-input" placeholder="Escalation policy" value={config.support_policy.default_escalation_policy} onChange={(e) => setConfig((prev) => ({ ...prev, support_policy: { ...prev.support_policy, default_escalation_policy: e.target.value } }))} />
                <input className="provider-input" placeholder="Allowed remediation classes" value={config.support_policy.allowed_remediation_classes.join(",")} onChange={(e) => setConfig((prev) => ({ ...prev, support_policy: { ...prev.support_policy, allowed_remediation_classes: e.target.value.split(",").map((item) => item.trim()).filter(Boolean) } }))} />
              </div>
              <button className="btn-save" onClick={() => saveSection("support_policy")} disabled={saving.support_policy}>{feedback.support_policy || (saving.support_policy ? "…" : "Save support policy")}</button>
            </div>

          </div>
        </section>
      </div>
    </div>
  );
}
