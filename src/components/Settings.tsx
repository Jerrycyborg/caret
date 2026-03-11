import { useEffect, useState } from "react";

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

const PROVIDERS: ProviderDef[] = [
  { id: "ollama", name: "Ollama", icon: "🦙", desc: "Local model endpoint.", placeholder: "http://localhost:11434" },
  { id: "openai", name: "OpenAI", icon: "⚡", desc: "Hosted general-purpose models.", placeholder: "sk-..." },
  { id: "anthropic", name: "Anthropic", icon: "🧠", desc: "Claude family models.", placeholder: "sk-ant-..." },
  { id: "gemini", name: "Google Gemini", icon: "✨", desc: "Gemini API access.", placeholder: "AIza..." },
  { id: "azure", name: "Azure OpenAI", icon: "☁️", desc: "Enterprise OpenAI via Azure.", placeholder: "Azure API key" },
];

const BACKEND_URL = "http://localhost:8000";

export default function Settings() {
  const [keyStatuses, setKeyStatuses] = useState<Record<string, KeyStatus>>({});
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState<Record<string, string>>({});

  useEffect(() => {
    fetch(`${BACKEND_URL}/v1/settings/keys`)
      .then((r) => r.json())
      .then((data) => {
        const map: Record<string, KeyStatus> = {};
        for (const key of data.keys ?? []) map[key.provider] = key;
        setKeyStatuses(map);
      })
      .catch(() => {});
  }, []);

  const showFeedback = (provider: string, msg: string) => {
    setFeedback((prev) => ({ ...prev, [provider]: msg }));
    setTimeout(() => setFeedback((prev) => ({ ...prev, [provider]: "" })), 2000);
  };

  const save = async (provider: string) => {
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
      setKeyStatuses((prev) => ({
        ...prev,
        [provider]: { provider, masked, updated_at: new Date().toISOString() },
      }));
      setInputs((prev) => ({ ...prev, [provider]: "" }));
      showFeedback(provider, "Saved");
    } catch {
      showFeedback(provider, "Error");
    } finally {
      setSaving((prev) => ({ ...prev, [provider]: false }));
    }
  };

  const clear = async (provider: string) => {
    await fetch(`${BACKEND_URL}/v1/settings/keys/${provider}`, { method: "DELETE" });
    setKeyStatuses((prev) => {
      const next = { ...prev };
      delete next[provider];
      return next;
    });
    showFeedback(provider, "Cleared");
  };

  return (
    <div className="settings">
      <div className="settings-header">
        <div>
          <div className="settings-title">Settings</div>
          <div className="settings-subtitle">Connections, policy defaults, runtime behavior, and operator preferences.</div>
        </div>
      </div>

      <div className="settings-layout">
        <section className="settings-panel">
          <div className="settings-section-title">AI Providers</div>
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
                    <span className={`provider-status ${isConfigured ? "ok" : "missing"}`}>
                      {isConfigured ? "Configured" : "Not set"}
                    </span>
                  </div>
                  {isConfigured && <div className="provider-current">Current: {status.masked}</div>}
                  <div className="provider-input-row">
                    <input
                      type="password"
                      className="provider-input"
                      placeholder={provider.placeholder}
                      value={inputs[provider.id] ?? ""}
                      onChange={(e) => setInputs((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                      onKeyDown={(e) => e.key === "Enter" && save(provider.id)}
                      autoComplete="off"
                    />
                    <button className="btn-save" onClick={() => save(provider.id)} disabled={!inputs[provider.id]?.trim() || saving[provider.id]}>
                      {feedback[provider.id] || (saving[provider.id] ? "…" : "Save")}
                    </button>
                    {isConfigured && <button className="btn-clear" onClick={() => clear(provider.id)}>Clear</button>}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="settings-panel">
          <div className="settings-section-title">Integrations</div>
          <div className="settings-scroll">
            <div className="settings-card">
              <strong>Telegram</strong>
              <div className="settings-line">Webhook-ready in backend. Deployment, bot token, and secret wiring still required.</div>
            </div>
            <div className="settings-card">
              <strong>WhatsApp</strong>
              <div className="settings-line">Session contract exists. Provider integration is still deferred.</div>
            </div>
            <div className="settings-card">
              <strong>OpenClaw</strong>
              <div className="settings-line">Executor contract exists. Live subsystem wiring is still open.</div>
            </div>
            <div className="settings-card">
              <strong>Wraith</strong>
              <div className="settings-line">Executor contract exists. Live security workflow wiring is still open.</div>
            </div>
          </div>
        </section>

        <section className="settings-panel">
          <div className="settings-section-title">Approval Policy</div>
          <div className="settings-scroll">
            <div className="settings-card">
              <strong>Plan approval</strong>
              <div className="settings-line">Mutating tasks stop at task-level approval before execution.</div>
            </div>
            <div className="settings-card">
              <strong>Privileged boundary</strong>
              <div className="settings-line">Local OS-sensitive actions still require separate Rust-managed approval.</div>
            </div>
            <div className="settings-card">
              <strong>Reporting rule</strong>
              <div className="settings-line">All delegated work reports back into Oxy sessions and task history first.</div>
            </div>
          </div>
        </section>

        <section className="settings-panel">
          <div className="settings-section-title">App Preferences</div>
          <div className="settings-scroll">
            <div className="settings-card">
              <strong>Desktop-first control surface</strong>
              <div className="settings-line">Best experience for terminal, security, and local runtime features.</div>
            </div>
            <div className="settings-card">
              <strong>Verification baseline</strong>
              <div className="settings-line">Frontend build passes. Backend contract tests are active and tracked in handoff.</div>
            </div>
            <div className="settings-card">
              <strong>Storage</strong>
              <div className="settings-line">Keys and local state stay on the machine. Current dev testing uses a workspace-local DB override.</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
