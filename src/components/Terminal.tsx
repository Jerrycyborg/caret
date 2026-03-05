import { useState, useEffect, useRef, useCallback } from "react";
import { Command } from "@tauri-apps/plugin-shell";
import { invoke } from "@tauri-apps/api/core";

interface HistoryEntry { cmd: string; output: string; error?: string }

export default function Terminal() {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [homeDir, setHomeDir] = useState("~");
  const [cwd, setCwd] = useState("~");
  const [running, setRunning] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const cmdHistory = useRef<string[]>([]);
  const histIdx = useRef(-1);

  useEffect(() => {
    invoke<string>("get_home_dir").then((h) => {
      setHomeDir(h);
      setCwd(h);
    }).catch(() => {});
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    outputRef.current?.scrollTo(0, outputRef.current.scrollHeight);
  }, [history]);

  const runCmd = useCallback(async (rawCmd: string) => {
    const cmd = rawCmd.trim();
    if (!cmd) return;
    cmdHistory.current = [cmd, ...cmdHistory.current.slice(0, 99)];
    histIdx.current = -1;
    setRunning(true);

    // Handle 'cd' locally
    if (cmd.startsWith("cd ") || cmd === "cd") {
      const target = cmd.slice(3).trim() || homeDir;
      const resolved = target.startsWith("~")
        ? homeDir + target.slice(1)
        : target.startsWith("/")
          ? target
          : cwd + "/" + target;
      setCwd(resolved);
      setHistory((prev) => [...prev, { cmd, output: "" }]);
      setRunning(false);
      return;
    }
    if (cmd === "clear") {
      setHistory([]);
      setRunning(false);
      return;
    }

    try {
      const isWin = navigator.userAgent.includes("Windows");
      const shell = isWin ? "cmd" : "sh";
      const args = isWin ? ["/C", `cd /d "${cwd}" && ${cmd}`] : ["-c", `cd "${cwd}" && ${cmd}`];
      const result = await Command.create(shell, args).execute();
      setHistory((prev) => [
        ...prev,
        { cmd, output: result.stdout || "", error: result.stderr || undefined },
      ]);
    } catch (e) {
      setHistory((prev) => [...prev, { cmd, output: "", error: String(e) }]);
    } finally {
      setRunning(false);
    }
  }, [cwd, homeDir]);

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      runCmd(input);
      setInput("");
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const next = histIdx.current + 1;
      if (next < cmdHistory.current.length) {
        histIdx.current = next;
        setInput(cmdHistory.current[next]);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = histIdx.current - 1;
      if (next < 0) { histIdx.current = -1; setInput(""); }
      else { histIdx.current = next; setInput(cmdHistory.current[next]); }
    }
  };

  const displayCwd = cwd.startsWith(homeDir) ? "~" + cwd.slice(homeDir.length) : cwd;

  return (
    <div className="terminal-panel" onClick={() => inputRef.current?.focus()}>
      <div className="term-title">Terminal</div>
      <div className="term-output" ref={outputRef}>
        {history.map((h, i) => (
          <div key={i} className="term-block">
            <div className="term-prompt-line">
              <span className="term-cwd">{displayCwd}</span>
              <span className="term-prompt-sym"> $ </span>
              <span className="term-cmd-echo">{h.cmd}</span>
            </div>
            {h.output && <pre className="term-stdout">{h.output}</pre>}
            {h.error && <pre className="term-stderr">{h.error}</pre>}
          </div>
        ))}
        {running && (
          <div className="term-running">▋</div>
        )}
      </div>
      <div className="term-input-row">
        <span className="term-cwd">{displayCwd}</span>
        <span className="term-prompt-sym"> $ </span>
        <input
          ref={inputRef}
          className="term-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          autoComplete="off"
          spellCheck={false}
          disabled={running}
          placeholder={running ? "running…" : ""}
        />
      </div>
    </div>
  );
}
