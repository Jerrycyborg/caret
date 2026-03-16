# Caret Core Blueprint

Caret is a local-first IT support assistant deployed to Windows devices.

## Product Mission

Give every user an always-on IT support tool that:
1. Helps them troubleshoot device issues through a guided support chat
2. Monitors device health and flags performance problems automatically
3. Creates Jira IT tickets from incidents with a single click, including relevant logs

## Core Identity

- **local-first**: runs on the device, no cloud dependency for core function
- **zero-config for users**: IT deploys credentials once; users open the app and everything works
- **support-first**: every feature exists to help the user or their IT team resolve device issues
- **lightweight**: no bundled model weights, no Docker, no Python requirement on target devices
- **policy-bounded**: auto-fix stays deterministic and within an explicit allowlist
- **safe around privileged actions**: UAC elevation required, all actions auditable

## Product Lanes

| Lane | Purpose |
|---|---|
| Home | Dashboard — CPU/RAM/disk health tiles, active incident list, quick actions |
| Help | AI-powered IT support chat |
| Incidents | Automated monitoring — incidents, auto-fix queue, escalation, Jira tickets |
| Security | Privileged visibility — firewall, BitLocker, event log, connections; admin-gated UAC actions |
| Settings | Admin-only — Jira config, support policy, admin group, management server |

## What Caret Is Not

- Not a generic AI assistant
- Not a plugin marketplace
- Not a workflow/task shell
- Not multi-platform (Windows only)

## Architectural Guardrails

- Tauri shell stays thin — WebView2, IPC only
- Rust owns privileged local actions (UAC, netsh, taskkill, services)
- Python backend sidecar owns AI, storage, monitoring, Jira, and network calls
- Backend is loopback-only (`localhost:8000`) — no inbound surface
- Management channel is opt-in, controlled by IT admin at deployment
- Settings are admin-gated — non-admins never see or touch configuration
