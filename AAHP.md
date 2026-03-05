# AAHP — Oxy Development Checkpoint
> Adaptive AI-Handoff Protocol. Paste this file at the start of every new AI chat session to restore full context in ~500 tokens.

---

## PROJECT
**Name:** Oxy
**Goal:** Cross-platform AI-powered personal OS assistant (Tauri 2 desktop app + FastAPI/Python sidecar)
**Repo:** `Internal projects/Oxy`
**Stack:** Tauri 2 (Rust + React 19/TS) · FastAPI + LiteLLM (Python sidecar) · SQLite · LanceDB

---

## PHASES

| Phase | Name                    | Status         |
|-------|-------------------------|----------------|
| 0     | Scaffold & AAHP Setup   | ✅ Done        |
| 1     | Core Chat Loop          | 🔄 In Progress |
| 2     | Multi-Model Layer       | ⏳ Not Started |
| 3     | OS Integration          | ⏳ Not Started |
| 4     | Security Control Panel  | ⏳ Not Started |
| 5     | RAG & Documents         | ⏳ Not Started |
| 6     | Distribution & Polish   | ⏳ Not Started |

---

## CURRENT STATE

### Completed This Session (Phase 0)
- [x] Tauri 2 + React 19/TS project scaffolded (`npm create tauri-app`)
- [x] Renamed from `tauri-app` → `oxy` (package.json, Cargo.toml, tauri.conf.json)
- [x] Window: 1200×800, identifier: `com.tws.oxy`
- [x] FastAPI backend created: `backend/main.py` with CORS for Tauri origins
- [x] Chat router: `backend/routers/chat.py` — SSE streaming via LiteLLM
- [x] Models router: `backend/routers/models.py` — Ollama dynamic + cloud static list
- [x] React UI: Sidebar navigation, Chat view, ModelSelector component
- [x] Dark theme CSS (var-based, fully custom)
- [x] Backend health indicator in chat header
- [x] `concurrently` added — `npm run dev:all` starts both

### Phase 1 Remaining
- [ ] SQLite persistence: save/load conversation history
- [ ] Conversation list panel in sidebar
- [ ] Backend health polling (retry on reconnect)
- [ ] `.env` support for API keys (python-dotenv wired in)
- [ ] Test full flow: Ollama → stream → UI renders

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
│       └── ModelSelector.tsx       ← Ollama + cloud models
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
