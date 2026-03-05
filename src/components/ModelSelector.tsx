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

  useEffect(() => {
    fetch(`${BACKEND_URL}/v1/models`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data.models) && data.models.length > 0) {
          setModels(data.models);
          const current = data.models.find((m: ModelOption) => m.id === value);
          if (!current) onChange(data.models[0].id);
        }
      })
      .catch(() => {
        // backend not running yet — keep showing current value
      });
  }, []);

  return (
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
  );
}
