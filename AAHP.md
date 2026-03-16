# AAHP — Caret Handoff

## Product Vision

Caret is a local-first IT support assistant for Windows devices.
Three pillars:
1. **IT support chat** — user describes a device problem, Caret helps resolve it
2. **Health monitoring** — automated daemon detects disk/CPU/mem/process issues and queues fixes
3. **Jira tickets from incidents** — single-click ticket creation with incident logs attached

## Product Lanes

- `Sessions` — IT support chat
- `Support` — monitoring, incidents, auto-fix, Jira escalation
- `System` — live device health (CPU, RAM, disk, processes)
- `Security` — firewall, services, users, audit log
- `Settings` — model config, Jira, support policy, management server URL

## Current State (v0.1.9)

- Windows-only build — all macOS/Linux code removed from Rust layer
- Backend sidecar (`caret-backend.exe`) is Python/FastAPI, runs on localhost:8000
- Support daemon: checks device health every 5 min, creates incidents, queues auto-fixes
- Jira ticket creation: `Create IT ticket` button on any incident → POSTs logs + context to Jira
- Management channel: optional control server URL in Settings, checkin daemon runs every 60s
- Security panel: compliance status (firewall, BitLocker, event errors, connections); admin-gated UAC actions
- Admin access: Windows local admin (default); AD group (`ROL-ADM-Admins`) via env `CARET_ADMIN_GROUP` or Settings field
- Jira OAuth 2.0: IT deploys with `CARET_JIRA_OAUTH_CLIENT_ID` + `CARET_JIRA_OAUTH_CLIENT_SECRET`; users click "Sign in with Jira", tokens auto-refresh
- `backend/services/config.py`: clean sections — `org`, `ticketing`, `support_policy`, `integrations`, `management`

## Next Priority

1. ~~Nav restructure: Home, Help, Incidents, Security, Settings~~ — done (v0.1.3)
2. ~~Startup stabilisation + orphan cleanup~~ — done (v0.1.4)
3. ~~Security panel rebuild + admin access~~ — done (v0.1.5)
4. ~~Verify Jira ticket creation end-to-end~~ — done (v0.1.6); use "Test connection" in Settings to validate with real credentials
5. ~~Wire `admin_group` into Rust `get_admin_status`~~ — done (v0.1.5)
6. Microsoft Copilot auth (MSAL SSO) — on hold, needs Azure AD app registration
7. Broaden auto-fix: more remediation classes

## Build Rules

1. Update AAHP.md + CHANGELOG.md after each meaningful change
2. `Core_blueprint.md` and `BUILD_BLUEPRINT.md` are source of truth
3. No feature additions beyond what is explicitly asked
4. Read only relevant files/sections — no whole-file reads when a grep will do
5. Focus on stable, shippable, working code

## Resume Chain

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`
