# Caret

Caret is a local-first IT support assistant for Windows devices. It gives every user an always-on tool to troubleshoot device issues, monitor device health, and escalate to IT — without requiring any user configuration.

## What Caret Does

- **Help** — AI-powered support chat. Describe a device problem; Caret guides resolution. Works with a local Ollama model or a cloud API key configured by IT.
- **Home** — Dashboard showing live CPU/RAM/disk health and active incidents at a glance.
- **Incidents** — Automated monitoring daemon detects disk/CPU/memory issues, queues safe auto-fixes, and surfaces incidents for review or escalation.
- **Security** — Compliance visibility: firewall state, BitLocker, system event errors, active connections. Admin-gated remediation actions with UAC elevation.
- **Settings** — Admin-only. Non-admins see a managed view. Admins configure Jira, support policy, and management server.

## Design Principles

- **Local-first** — core functions work without cloud connectivity
- **Zero-config for users** — IT deploys credentials once via env vars; users open the app and everything works
- **Policy-bounded auto-fix** — remediation stays within an explicit allowlist; no open-ended execution
- **Safe around privileged actions** — UAC elevation required, all actions auditable
- **Windows only** — no macOS or Linux build paths

## Building

Prerequisites: [Rust](https://rustup.rs), [Node.js](https://nodejs.org), [WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (pre-installed on Windows 11).

```
npm install
npm run tauri build
```

Installer output: `src-tauri\target\release\bundle\nsis\caret_<version>_x64-setup.exe`

## IT Deployment — Environment Variables

| Variable | Purpose |
|---|---|
| `CARET_JIRA_BASE_URL` | Jira instance URL |
| `CARET_JIRA_PROJECT_KEY` | Default project for ticket creation |
| `CARET_JIRA_USER_EMAIL` | Service account email (Basic auth) |
| `CARET_JIRA_API_TOKEN` | API token (Basic auth) — never stored in DB |
| `CARET_JIRA_OAUTH_CLIENT_ID` | Atlassian OAuth 2.0 client ID |
| `CARET_JIRA_OAUTH_CLIENT_SECRET` | Atlassian OAuth 2.0 client secret — env-only, never stored |
| `CARET_ADMIN_GROUP` | AD security group for admin access (e.g. `ROL-ADM-Admins`); leave empty to use Windows local admin |
| `CARET_MANAGEMENT_SERVER_URL` | Central management server URL (optional) |
| `CARET_MANAGEMENT_TOKEN` | Bearer token for management server checkins (optional) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | Cloud AI provider key — at least one required unless Ollama is running locally |

## AI Model Setup

Caret does not bundle model weights. Configure one of:
- **Local**: Install [Ollama](https://ollama.com) and pull a model (`ollama pull llama3.2`). No API key needed.
- **Cloud**: Set one of the API key env vars above. IT sets this at deployment; users never touch it.

If no model is configured, the Help tab shows an amber banner and disables the input until IT enables a model.

## Architecture

| Layer | Technology | Responsibility |
|---|---|---|
| Desktop shell | Tauri 2 (Rust + WebView2) | Window, IPC, privileged OS calls, UAC |
| Frontend | React + TypeScript (Vite) | UI |
| Backend sidecar | Python / FastAPI (`caret-backend.exe`) | AI chat, storage, monitoring, Jira, management checkin |
| Storage | SQLite (aiosqlite) | Conversations, incidents, config, OAuth tokens |

The backend runs on `localhost:8000` and is loopback-only — no inbound surface exposed to the network.

## Source of Truth

- [build/Core_blueprint.md](build/Core_blueprint.md)
- [build/BUILD_BLUEPRINT.md](build/BUILD_BLUEPRINT.md)
- [AAHP.md](AAHP.md)
- [CHANGELOG.md](CHANGELOG.md)
- [release.json](release.json)
