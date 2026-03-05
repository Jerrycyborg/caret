import { useState, useEffect } from "react";

interface ModelOption {
  id: string;
  provider: string;
  name: string;
}

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
}

const BACKEND_URL = "http://localhost:8000";

export default function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchModels = () => {
    setRefreshing(true);
    fetch(`${BACKEND_URL}/v1/models`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data.models) && data.models.length > 0) {
          setModels(data.models);
          const current = data.models.find((m: ModelOption) => m.id === value);
          if (!current) onChange(data.models[0].id);
        }
      })
      .catch(() => {})
      .finally(() => setRefreshing(false));
  };

  useEffect(() => {
    fetchModels();
  }, []);

  return (
    <div className="model-selector-wrap">
      <select
        className="model-selector"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {models.length === 0 ? (
          <option value={value}>{value}</option>
        ) : (
          models.map((m) => (
            <option key={m.id} value={m.id}>
              [{m.provider.toUpperCase()}] {m.name}
            </option>
          ))
        )}
      </select>
      <button
        className="model-refresh-btn"
        onClick={fetchModels}
        disabled={refreshing}
        title="Refresh model list"
      >
        {refreshing ? "…" : "↻"}
      </button>
    </div>
  );
}
