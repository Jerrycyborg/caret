import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

interface PluginInfo {
  name: string;
  description: string;
  enabled: boolean;
}

export default function PluginPanel() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [error, setError] = useState("");

  const refreshPlugins = () => {
    invoke<PluginInfo[]>("list_plugins").then(setPlugins).catch(e => setError(String(e)));
  };

  useEffect(() => {
    refreshPlugins();
  }, []);

  const runSelected = () => {
    if (!selected) return;
    invoke<string | null>("run_plugin", { name: selected, input })
      .then(res => setOutput(res ?? "No output"))
      .catch(e => setError(String(e)));
  };

  const togglePlugin = async (name: string, enabled: boolean) => {
    try {
      await invoke("toggle_plugin_enabled", { name, enabled });
      refreshPlugins();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="plugin-panel">
      <h2>Plugin Manager</h2>
      <div style={{fontSize:14,marginBottom:8}}>Easily add new features to Oxy. Enable or disable plugins as needed.</div>
      {error && <div className="plugin-error">Error: {error}</div>}
      <ul className="plugin-list">
        {plugins.map(p => (
          <li key={p.name} style={{marginBottom:12}}>
            <label style={{display:'flex',alignItems:'center',gap:8}}>
              <input
                type="radio"
                name="plugin"
                value={p.name}
                checked={selected === p.name}
                onChange={() => setSelected(p.name)}
              />
              <b>{p.name}</b>
              <span style={{color:p.enabled?"green":"red"}}>
                {p.enabled ? "Enabled" : "Disabled"}
              </span>
              <button
                style={{marginLeft:8}}
                onClick={() => togglePlugin(p.name, !p.enabled)}
              >{p.enabled ? "Disable" : "Enable"}</button>
            </label>
            <div style={{fontSize:12,color:'#888',marginLeft:32}}>{p.description}</div>
          </li>
        ))}
      </ul>
      <div className="plugin-runner">
        <input
          type="text"
          placeholder="Input for plugin (optional)"
          value={input}
          onChange={e => setInput(e.target.value)}
        />
        <button onClick={runSelected} disabled={!selected}>Run Plugin</button>
      </div>
      {output && <pre className="plugin-output">{output}</pre>}
    </div>
  );
}
