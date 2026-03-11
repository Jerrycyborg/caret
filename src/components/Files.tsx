import { useState, useEffect, useCallback } from "react";
import { readDir, type DirEntry } from "@tauri-apps/plugin-fs";
import { invoke } from "@tauri-apps/api/core";

interface Entry { name: string; isDir: boolean }

const EXT_ICONS: Record<string, string> = {
  ts: "TS", tsx: "TSX", js: "JS", jsx: "JSX", rs: "RS",
  py: "PY", json: "{}",  md: "MD", txt: "TXT", html: "HTML",
  css: "CSS", toml: "TOML", yaml: "YAML", yml: "YML",
  png: "IMG", jpg: "IMG", jpeg: "IMG", gif: "IMG", svg: "SVG",
  mp4: "VID", mov: "VID", pdf: "PDF", zip: "ZIP", tar: "ZIP",
  sh: "SH", bat: "BAT", exe: "EXE",
};

function fileIcon(name: string, isDir: boolean): string {
  if (isDir) return "📁";
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  return EXT_ICONS[ext] ?? "FILE";
}

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export default function Files() {
  const [homeDir, setHomeDir] = useState("");
  const [cwd, setCwd] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [stack, setStack] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadDir = useCallback(async (path: string) => {
    setLoading(true);
    setError("");
    try {
      const items = await readDir(path);
      const parsed: Entry[] = items
        .filter((i: DirEntry) => i.name)
        .map((i: DirEntry) => ({ name: i.name!, isDir: !!i.isDirectory }))
        .sort((a: Entry, b: Entry) => {
          if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
          return a.name.localeCompare(b.name);
        });
      setEntries(parsed);
      setCwd(path);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isTauriRuntime()) {
      setError("Files panel requires the Tauri desktop runtime.");
      return;
    }
    invoke<string>("get_home_dir").then((h) => {
      setHomeDir(h);
      loadDir(h);
    }).catch((e) => setError(String(e)));
  }, [loadDir]);

  const enterDir = (name: string) => {
    setStack((prev) => [...prev, cwd]);
    loadDir(cwd.endsWith("/") ? cwd + name : cwd + "/" + name);
  };

  const goUp = () => {
    if (stack.length === 0) return;
    const prev = stack[stack.length - 1];
    setStack((s) => s.slice(0, -1));
    loadDir(prev);
  };

  const displayCwd = homeDir && cwd.startsWith(homeDir)
    ? "~" + cwd.slice(homeDir.length)
    : cwd;

  return (
    <div className="files-panel">
      <div className="files-title">Files</div>

      {!isTauriRuntime() && (
        <div className="files-notice">
          Open this panel inside the desktop app. The web/dev preview cannot access local filesystem APIs.
        </div>
      )}

      <div className="files-bar">
        <button className="files-up-btn" onClick={goUp} disabled={stack.length === 0}>
          ↑ Up
        </button>
        <span className="files-cwd">{displayCwd}</span>
      </div>

      {error && <div className="files-error">⚠ {error}</div>}
      {loading && <div className="files-loading">Loading…</div>}

      {!loading && (
        <div className="files-list">
          {entries.length === 0 && !error && (
            <div className="files-empty">Empty directory</div>
          )}
          {entries.map((e) => (
            <div
              key={e.name}
              className={`files-entry${e.isDir ? " is-dir" : ""}`}
              onClick={e.isDir ? () => enterDir(e.name) : undefined}
              title={e.name}
            >
              <span className="files-icon">{fileIcon(e.name, e.isDir)}</span>
              <span className="files-name">{e.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
