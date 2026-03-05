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
  {
    id: "ollama",
    name: "Ollama",
    icon: "🦙",
    desc: "Local models — no key needed. Enter custom base URL only if not using default.",
    placeholder: "http://localhost:11434 (leave blank for default)",
  },
  {
    id: "openai",
    name: "OpenAI",
    icon: "⚡",
    desc: "GPT-4o, GPT-4o-mini and more.",
    placeholder: "sk-...",
  },
  {
    id: "anthropic",
    name: "Anthropic",
    icon: "🧠",
    desc: "Claude 3.5 Sonnet, Claude 3 Haiku.",
    placeholder: "sk-ant-...",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    icon: "✨",
    desc: "Gemini 1.5 Pro, Gemini 1.5 Flash.",
    placeholder: "AIza...",
  },
  {
    id: "azure",
    name: "Azure OpenAI",
    icon: "☁️",
    desc: "Enterprise OpenAI via Azure. Also set AZURE_API_BASE and AZURE_API_VERSION in .env.",
    placeholder: "Your Azure API key",
  },
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
        for (const k of data.keys ?? []) map[k.provider] = k;
        setKeyStatuses(map);
      })
      .catch(() => {});
  }, []);

  const showFeedback = (provider: string, msg: string) => {
    setFeedback((f) => ({ ...f, [provider]: msg }));
    setTimeout(() => setFeedback((f) => ({ ...f, [provider]: "" })), 2000);
  };

  const save = async (provider: string) => {
    const value = inputs[provider]?.trim();
    if (!value) return;
    setSaving((s) => ({ ...s, [provider]: true }));
    try {
      const res = await fetch(`${BACKEND_URL}/v1/settings/keys/${provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) throw new Error();
      const masked =
        value.length <= 8 ? "*".repeat(value.length) : value.slice(0, 4) + "****" + value.slice(-4);
      setKeyStatuses((s) => ({
        ...s,
        [provider]: { provider, masked, updated_at: new Date().toISOString() },
      }));
      setInputs((i) => ({ ...i, [provider]: "" }));
      showFeedback(provider, "✓ Saved");
    } catch {
      showFeedback(provider, "✗ Error");
    } finally {
      setSaving((s) => ({ ...s, [provider]: false }));
    }
  };

  const clear = async (provider: string) => {
    await fetch(`${BACKEND_URL}/v1/settings/keys/${provider}`, { method: "DELETE" });
    setKeyStatuses((s) => {
      const next = { ...s };
      delete next[provider];
      return next;
    });
    showFeedback(provider, "Cleared");
  };

  return (
    <div className="settings">
      <div className="settings-title">Settings</div>
      <div className="settings-subtitle">
        API keys are stored locally in <code>~/.oxy/oxy.db</code> and never leave your machine.
      </div>

      <div className="provider-grid">
        {PROVIDERS.map((p) => {
          const status = keyStatuses[p.id];
          const isConfigured = !!status;
          return (
            <div key={p.id} className={`provider-card${isConfigured ? " configured" : ""}`}>
              <div className="provider-card-header">
                <div className="provider-icon">{p.icon}</div>
                <div>
                  <div className="provider-name">{p.name}</div>
                  <div className="provider-desc">{p.desc}</div>
                </div>
                <span className={`provider-status ${isConfigured ? "ok" : "missing"}`}>
                  {isConfigured ? "● Configured" : "○ Not set"}
                </span>
              </div>

              {isConfigured && (
                <div className="provider-current">Current: {status.masked}</div>
              )}

              <div className="provider-input-row">
                <input
                  type="password"
                  className="provider-input"
                  placeholder={p.placeholder}
                  value={inputs[p.id] ?? ""}
                  onChange={(e) =>
                    setInputs((i) => ({ ...i, [p.id]: e.target.value }))
                  }
                  onKeyDown={(e) => e.key === "Enter" && save(p.id)}
                  autoComplete="off"
                />
                <button
                  className="btn-save"
                  onClick={() => save(p.id)}
                  disabled={!inputs[p.id]?.trim() || saving[p.id]}
                >
                  {feedback[p.id] || (saving[p.id] ? "…" : "Save")}
                </button>
                {isConfigured && (
                  <button className="btn-clear" onClick={() => clear(p.id)}>
                    Clear
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
