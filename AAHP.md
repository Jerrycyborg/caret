# AAHP — Caret Handoff

## Product Vision

Caret is a local-first IT support assistant for Windows devices.
Three pillars:
1. **IT support chat** — user describes a device problem, Caret helps resolve it
2. **Health monitoring** — automated daemon detects disk/CPU/mem/process issues and queues fixes
3. **Jira tickets from incidents** — single-click ticket creation with incident logs attached

## Product Lanes

| Lane | Purpose |
|---|---|
| Home | Dashboard — CPU/RAM/disk tiles, active incident list, quick actions |
| Help | AI-powered IT support chat |
| Incidents | Monitoring, auto-fix queue, escalation, Jira ticket creation |
| Security | Compliance status — firewall, BitLocker, event errors; admin-gated UAC actions |
| Settings | Admin-only config — Jira, support policy, admin group, management server |

## Current State (v0.1.9)

- Windows-only build — all macOS/Linux code removed from Rust layer
- Backend sidecar (`caret-backend.exe`) is Python/FastAPI, runs on localhost:8000
- Support daemon: checks device health every 5 min, creates incidents, queues auto-fixes
- Jira ticket creation: `Create IT ticket` button on any incident → POSTs logs + context to Jira
- Jira OAuth 2.0 (3LO): IT deploys `CARET_JIRA_OAUTH_CLIENT_ID` + `CARET_JIRA_OAUTH_CLIENT_SECRET`; users click "Sign in with Jira" in Incidents panel; tokens stored in DB and auto-refreshed
- Management channel: optional control server URL in Settings; checkin daemon runs every 60s; `CARET_MANAGEMENT_TOKEN` bearer header sent when set
- Security panel: compliance status (firewall, BitLocker, event errors, connections); admin-gated UAC actions
- Admin access: Windows local admin (default); AD group via `CARET_ADMIN_GROUP` env var or Settings field
- Settings: admin-gated — non-admins see "managed by IT" view; admins see full config
- Help tab: graceful no-AI state — amber banner + disabled input when no model is configured
- Config sections: `org`, `ticketing`, `support_policy`, `management`

## Next Priority

1. Microsoft Copilot auth (MSAL SSO) — on hold, needs Azure AD app registration
2. Broaden auto-fix: more remediation classes beyond `cleanup_candidates`, `diagnostics`, `readiness_refresh`
3. Windows installer packaging with env var injection at deploy time
4. Management server (central control plane)

## Build Rules

1. Update `AAHP.md` + `CHANGELOG.md` after each meaningful change
2. `Core_blueprint.md` and `BUILD_BLUEPRINT.md` are source of truth for product scope
3. No feature additions beyond what is explicitly asked
4. Read only relevant files/sections — no whole-file reads when a grep will do
5. Focus on stable, shippable, working code

## Resume Chain

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`
