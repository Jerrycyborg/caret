import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { FaPuzzlePiece, FaCloudSun, FaShieldAlt } from "react-icons/fa";

type MarketplacePlugin = {
  name: string;
  description: string;
  installed: boolean;
  author: string;
  version: string;
  category?: string;
};

export default function PluginMarketplace() {
  const [plugins, setPlugins] = useState<MarketplacePlugin[]>([]);
  const [error, setError] = useState("");
  const [installing, setInstalling] = useState<string>("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("All");

  useEffect(() => {
    // Replace with backend call for real plugin discovery
    invoke<MarketplacePlugin[]>("discover_plugins")
      .then(setPlugins)
      .catch(e => setError(String(e)));
  }, []);

  const installPlugin = async (name: string) => {
    setInstalling(name);
    try {
      await invoke("install_plugin", { name });
      setPlugins(await invoke("discover_plugins"));
    } catch (e) {
      setError(String(e));
    } finally {
      setInstalling("");
    }
  };

  // Icon mapping by category
  const getIcon = (cat?: string) => {
    switch (cat) {
      case "Utility": return <FaPuzzlePiece style={{color:'#6cf',fontSize:22}} />;
      case "Weather": return <FaCloudSun style={{color:'#fc6',fontSize:22}} />;
      case "Security": return <FaShieldAlt style={{color:'#c66',fontSize:22}} />;
      default: return <FaPuzzlePiece style={{color:'#888',fontSize:22}} />;
    }
  };

  // Get unique categories
  const categories = ["All", ...Array.from(new Set(plugins.map(p => p.category).filter(Boolean)))];

  // Filter plugins by search and category
  const filtered = plugins.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) || p.description.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = category === "All" || p.category === category;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="plugin-marketplace">
      <h2>Plugin Marketplace</h2>
      <div style={{fontSize:14,marginBottom:8}}>Browse and install new features for Oxy. All plugins are reviewed for safety.</div>
      {error && <div className="plugin-error">Error: {error}</div>}
      <div style={{display:'flex',gap:16,marginBottom:16}}>
        <input
          type="text"
          placeholder="Search plugins..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{padding:6,borderRadius:6,border:'1px solid #333',background:'#222',color:'#eee',width:180}}
        />
        <select value={category} onChange={e => setCategory(e.target.value)} style={{padding:6,borderRadius:6,border:'1px solid #333',background:'#222',color:'#eee'}}>
          {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
        </select>
      </div>
      <ul className="marketplace-list">
        {filtered.map(p => (
          <li key={p.name} style={{marginBottom:16,padding:12,borderRadius:8,background:'#181824',display:'flex',alignItems:'center',gap:16}}>
            {getIcon(p.category)}
            <div style={{flex:1}}>
              <div style={{display:'flex',alignItems:'center',gap:12}}>
                <b style={{fontSize:16}}>{p.name}</b>
                <span style={{fontSize:12,color:'#888'}}>by {p.author}</span>
                <span style={{fontSize:12,color:'#888'}}>v{p.version}</span>
                {p.installed ? (
                  <span style={{color:'green',marginLeft:8}}>Installed</span>
                ) : (
                  <button onClick={() => installPlugin(p.name)} disabled={!!installing}>
                    {installing === p.name ? "Installing…" : "Install"}
                  </button>
                )}
              </div>
              <div style={{fontSize:13,color:'#aaa',marginTop:6}}>{p.description}</div>
            </div>
          </li>
        ))}
        {filtered.length === 0 && <div style={{color:'#888',marginTop:24}}>No plugins found.</div>}
      </ul>
    </div>
  );
}
