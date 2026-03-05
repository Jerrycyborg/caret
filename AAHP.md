### Phase 4 — In Progress (Security Control Panel)
- [x] SecurityPanel.tsx: React UI for firewall, services, users, audit log, network connections
- [x] Rust/Tauri backend: get_firewall_status, get_services, get_users, get_audit_log, get_network_connections (cross-platform shell)
- [x] Live status display wired to backend
- [x] Control actions: enable/disable firewall, start/stop/restart services, lock/unlock users, terminate connections
- [x] UI: refresh button, error handling, input controls
- [ ] Further UI/UX polish and validation
### Phase 5 — In Progress (Plugin Architecture)
- [x] Designed Rust plugin API: OxyPlugin trait, registry, example Echo plugin
- [x] Created src-tauri/plugins/oxy_plugin.rs with plugin trait, registry, Echo plugin, Tauri commands
- [x] Integrated plugin API into src-tauri/src/lib.rs, exposed list_plugins and run_plugin commands
- [x] Scaffolded React PluginPanel.tsx for plugin management UI
- [ ] Wire frontend PluginPanel to backend plugin commands
- [ ] Add enable/disable plugin controls and status display
- [ ] Update AAHP.md and README.md for plugin architecture progress

# AAHP — Oxy Development Checkpoint
> Adaptive AI-Handoff Protocol. Paste this file at the start of every new AI chat session to restore full context in ~500 tokens.

---

## PROJECT
**Name:** Oxy
**Goal:** AI assistant deeply integrated into the operating system, leveraging all available machine resources (CPU, GPU, memory, etc.) for advanced tasks. Oxy is designed to go beyond basic OS help, performing complex operations similar to OpenClaw or other powerful AI assistants, with full access to system capabilities and hardware. Core features include:

- **Plugin architecture** for extensibility and custom skills
- **Hardware acceleration** (GPU, NPU, etc.) for high-performance AI workloads
- **Multi-agent orchestration** for parallel, collaborative, or specialized AI tasks
**Repo:** `Internal projects/Oxy`
**Stack:** Tauri 2 (Rust + React 19/TS) · FastAPI + LiteLLM (Python sidecar) · SQLite · LanceDB

---

## PHASES

| Phase | Name                    | Status         |
|-------|-------------------------|----------------|
| 0     | Scaffold & AAHP Setup   | ✅ Done        |
| 1     | Core Chat Loop          | ✅ Done        |
| 2     | Multi-Model Layer       | ✅ Done        |
| 3     | OS Integration          | ✅ Done        |
| 4     | Security Control Panel  | ⏳ Not Started |
| 5     | Plugin Architecture     | ⏳ Not Started |
| 6     | Hardware Acceleration   | ⏳ Not Started |
| 7     | Multi-Agent Orchestration| ⏳ Not Started |
| 8     | RAG & Documents         | ⏳ Not Started |
| 9     | Distribution & Polish   | ⏳ Not Started |
---

## TECHNICAL ROADMAP

**Plugin Architecture**
- Design and implement a plugin system for extensibility
- Support custom skills, tools, and integrations
- Secure sandboxing and permission management

**Hardware Acceleration**
- Detect and utilize available GPU/NPU resources
- Integrate with frameworks (CUDA, Metal, OpenCL, etc.)
- Optimize AI workloads for performance

**Multi-Agent Orchestration**
- Enable parallel and collaborative agent workflows
- Support specialized agents for different tasks
- Design agent communication and coordination protocols

---

## CURRENT STATE

### Phase 1 — Completed
- [x] `database.py`: aiosqlite + SQLite at `~/.oxy/oxy.db`, auto-init on startup
- [x] `routers/conversations.py`: CRUD (list, create, get-with-messages, delete)
- [x] `routers/chat.py`: saves each message to DB, bumps `updated_at`
- [x] `main.py`: FastAPI lifespan init, dotenv loaded, conversations router included
- [x] `backend/.env.example`: template for all provider API keys
- [x] `Sidebar.tsx`: conversation list with `+` new chat button, auto-refreshes
- [x] `Chat.tsx`: loads history when switching conversations; auto-creates conversation on first message (title = first 48 chars)
- [x] `App.tsx`: `activeConvId` state, `sidebarKey` refresh signal, callbacks wired
- [x] CSS: conversation list styles added, old boilerplate stripped

### Phase 2 — Completed
- [x] `database.py`: `api_keys` table added
- [x] `routers/settings.py`: GET/PUT/DELETE `/v1/settings/keys/{provider}` (Ollama, OpenAI, Anthropic, Gemini, Azure)
- [x] `main.py`: keys loaded from DB into `os.environ` on startup so LiteLLM picks them up; also applied immediately on save
- [x] `Settings.tsx`: provider cards with masked display, password input, Save/Clear, instant ✓ feedback
- [x] `ModelSelector.tsx`: ↻ refresh button to re-fetch Ollama + cloud model list
- [x] `App.tsx`: Settings view wired (no longer "coming soon")

### Phase 3 — Completed (OS Integration)
- [x] `src-tauri/Cargo.toml`: added `sysinfo = "0.33"`, `dirs = "5"`, `tauri-plugin-shell = "2"`, `tauri-plugin-fs = "2"`
- [x] `src-tauri/src/lib.rs`: `get_system_info` command (structs CpuInfo/MemInfo/DiskInfo/ProcessInfo/SystemInfo via sysinfo crate); `get_home_dir` command via dirs crate; both plugins registered
- [x] `capabilities/default.json`: shell + fs permissions added
- [x] `Resources.tsx`: live CPU/RAM/disk gauges (auto-colour by threshold) + top-20 process table; polls `invoke("get_system_info")` every 2 s
- [x] `Terminal.tsx`: shell command runner via `Command.create()` (plugin-shell); `cd`/`clear` builtins; ↑/↓ command history; cwd tracking; cross-platform (sh on Unix, cmd on Windows)
- [x] `Files.tsx`: file browser via `readDir` (plugin-fs); starts at home dir; click to navigate into dirs; Up button; extension-badge icons
- [x] `App.tsx`: Resources/Terminal/Files panels wired; Security stays "coming-soon" for Phase 4
- [x] `App.css`: Resources gauges/process table, Terminal dark theme, Files list styles, coming-soon styles
- [x] Fixed sysinfo 0.33 API: `RefreshKind::nothing()` replaces removed `RefreshKind::new()`
- [x] Installed `@tauri-apps/plugin-shell` + `@tauri-apps/plugin-fs` npm packages
- **Commit:** `60d8c80`

### Phase 4 — Next (Security Control Panel)
- [ ] Firewall rules viewer/toggle (via shell commands — `pfctl` / `netsh`)
- [ ] Running services list with enable/disable
- [ ] User account management (list users, lock/unlock)
- [ ] Audit log viewer (tail system log)
- [ ] Network connections monitor (active sockets)

---

## FILE STRUCTURE

```
Oxy/
├── AAHP.md                          ← you are here
├── .gitignore
├── package.json                     ← Tauri + Vite + React 19
├── vite.config.ts
├── tsconfig.json / tsconfig.node.json
├── index.html
├── src/                             ← React/TypeScript frontend
│   ├── main.tsx
│   ├── App.tsx                      ← layout shell, view router
│   ├── App.css                      ← full dark theme
│   └── components/
│       ├── Sidebar.tsx
│       ├── Chat.tsx                 ← SSE streaming chat
│       ├── ModelSelector.tsx       ← Ollama + cloud models
│       ├── Settings.tsx            ← API key vault UI
│       ├── Resources.tsx           ← CPU/RAM/disk/process dashboard
│       ├── Terminal.tsx            ← shell command runner
│       └── Files.tsx               ← file browser
├── src-tauri/                       ← Rust/Tauri shell
│   ├── Cargo.toml                   ← package: oxy, lib: oxy_lib
│   ├── build.rs
│   ├── tauri.conf.json
│   ├── capabilities/default.json
│   ├── icons/                       ← all icon sizes present ✅
│   └── src/
│       ├── main.rs
│       └── lib.rs
└── backend/                         ← Python FastAPI sidecar
    ├── main.py                      ← FastAPI app, CORS
    ├── requirements.txt
    └── routers/
        ├── chat.py                  ← LiteLLM SSE streaming
        └── models.py               ← Ollama + cloud model list
```

---

## HOW TO RUN (DEV)

```bash
# Terminal 1 — Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Desktop app
npm install
npm run tauri dev

# Or both at once (requires concurrently)
npm run dev:all
```

Ollama must be running with at least one model pulled:
```bash
ollama pull llama3.2
ollama serve
```

---

## KEY DECISIONS

| Decision | Choice | Reason |
|----------|--------|--------|
| Desktop runtime | Tauri 2 | Native OS access, lighter than Electron, better sandbox |
| Model proxy | LiteLLM | Abstracts all provider differences, single import |
| Backend | FastAPI sidecar | Python AI ecosystem, clean separation |
| Streaming | SSE (Server-Sent Events) | Simple, works with `fetch()` in Tauri WebView |
| CSS | Plain CSS variables | Zero dependency, fast, fully customizable |
| Model discovery | Ollama API dynamic + cloud static | Fast startup, no cloud calls needed |
| Identifier | `com.tws.oxy` | Matches TWS Partners AG domain |

---

## KNOWN GAPS / NOTES

- SQLite not yet wired (Phase 1 remaining)
- No `.env` wiring yet — API keys for cloud providers must be set as env vars for now
- Sidecar auto-launch (production): add Python frozen binary to `src-tauri/binaries/` in Phase 6
- Icons already present in `src-tauri/icons/` from scaffold ✅

---

## AAHP RULES (token-saving protocol)
1. **Paste this file** at the top of every new AI chat session
2. **One phase per session** — never mix concerns
3. **Last act** of session: update this file (Done / In-Progress / Next / Decisions)
4. **Trust the file** — do not re-explain prior decisions
