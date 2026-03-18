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

## Session Notes (2026-03-18, cont. #4)
- Admin detection still failing after whoami SID fix: root cause was PATH — `whoami` in Caret process resolved to wrong binary. Fixed by using `$env:SystemRoot\System32\whoami.exe` absolute path + fallback via `net localgroup Administrators` checking both local and domain-prefixed username (`ADS\lawrencem`).
- Dark/light theme toggle added to sidebar footer (sun/moon icon, persists via localStorage).
- Favicon replaced — custom SVG icon (purple gradient diamond) generated via Python PIL + `tauri icon` CLI; title fixed from "Oxy" to "Caret".
- Admin actions redesigned: flat button row → 3-column card grid with group label + icon + name.
- Double firewall buttons removed; replaced with single contextual card (shows "Disable" when on, "Enable" when off).
- Added CleanDisk admin action: deletes user TEMP, Windows\Temp, empties Recycle Bin — via UAC elevation.
- Added contextual "Restart Print Spooler" card — only appears when spooler is stopped.
- Fixed disk usage check to use C:\ (was using Path.home() which is misleading on Windows).
- Added Windows Update age detection: checks `LastSuccessTime` registry key; signals `windows_update_stale` at ≥30 days (action_required) and ≥14 days (monitoring).

## Session Notes (2026-03-18, cont. #3)
- BitLocker showed "Off" even when active: `Get-BitLockerVolume` requires an elevated process token; Tauri runs non-elevated so it always caught and returned `$false`. Fixed: replaced with `manage-bde -status C:` which works without elevation.
- Admin not detected: `IsInRole(Administrator)` checks UAC token elevation, not group membership — non-elevated admins returned false. Fixed: use `whoami /groups /fo csv | ConvertFrom-Csv` and check for SID `S-1-5-32-544` (Builtin\Administrators) which is present in the token regardless of UAC state.
- System Events card now clickable: added `get_recent_events()` Tauri command (PowerShell pipe, pipe-delimited format); SecurityPanel fetches on first expand and shows time/level/source/message list with error/warn row colouring.

## Session Notes (2026-03-18, cont. #2)
- Settings tab redesign: Jira config card removed — Jira is IT-deployed via env vars, not per-device UI. Settings now contains only: Deployment (org), Management server, Admin group, Support policy, AI model keys.
- Settings hidden from non-admins in sidebar nav — admin check lifted to App.tsx, passed as `isAdmin` prop to Sidebar; nav filters out Settings for regular users.
- Incidents "Create IT ticket" now shows inline "Sign in with Jira to create ticket" button if Jira OAuth is configured but user not authenticated — no navigation to Settings needed.
- Next: Broader auto-fix remediation classes (disk cleanup, Windows Update, DNS flush, print spooler, service restart).

## Session Notes (2026-03-18, cont.)
- Incidents tab: per-section `.support-scroll` divs had no height constraint — all subsections (Now/Monitoring/Fix Queue/Escalations/History) had tiny scroll areas. Fixed by removing `overflow-y` from `.support-scroll` and adding `overflow-y: auto` to `.support-section` — the whole panel now scrolls as one unit.
- Security tab slowness/crash: `get_compliance_status` ran 4 system commands sequentially (~5s). Refactored to run all 4 in parallel using `std::thread::spawn` + `mpsc::channel`. Load time now ~1-2s (bounded by slowest single check). BitLocker PowerShell wrapped in `try { } catch { $false }` to prevent crash on machines without BitLocker.
- Build rule followed: Grep-first, offset+limit reads only. AAHP+CHANGELOG updated per rule #1.

## Session Notes (2026-03-18)
- Backend sidecar was crashing on startup — litellm data files missing from PyInstaller bundle. Fixed with `--collect-submodules litellm --collect-data litellm` in `build-backend.ps1`.
- CMD/PowerShell windows were flashing on Security tab open and backend launch — fixed with `CREATE_NO_WINDOW` on all `Command::new()` calls in Rust (no `#[cfg]` guards per build rules).
- Home dashboard had zero CSS — all home classes were unstyled. Full Home CSS added to `App.css`.
- Install lesson: use NSIS `/S`, not `msiexec /quiet` — MSI silently skips same-version reinstall.
- Build artifacts moved outside OneDrive: `CARGO_TARGET_DIR=C:\Users\lawrencem\cargo-targets\caret`, PyInstaller → `C:\Users\lawrencem\caret-pyinstaller\`.
- Rebuild needed: Rust `#[cfg]` guards were added then removed (violates Windows-only rule). Need one more full build to ship clean.

## Current State (v0.2.0)

- **Auto-fix expanded**: 3 new Windows health signals — Windows Update pending reboot, Print Spooler stopped, Defender disabled
- Detection runs every 5 min via daemon; new signals create incidents, queue fixes or escalations automatically
- Settings tab: Jira card removed — config is env-var-only (IT deploys); Settings hidden from non-admin nav
- Jira OAuth: inline "Sign in with Jira" on incident detail pane — no Settings navigation needed

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

1. **Better detection signals** — certificate errors (expiring certs in user store), RDP issues, proxy/SSL intercept detection. Catch before user calls IT.
2. **Fleet installer with env var injection** — NSIS deploy with `CARET_JIRA_*`, `CARET_ADMIN_GROUP`, `CARET_MANAGEMENT_*` pre-baked. Prerequisite for fleet rollout.
3. **Management server** — central fleet view: device health, open incidents, patterns across machines.
4. Microsoft Copilot auth (MSAL SSO) — on hold, needs Azure AD app registration.

## Build Rules

1. Update `AAHP.md` + `CHANGELOG.md` after each meaningful change
2. `Core_blueprint.md` and `BUILD_BLUEPRINT.md` are source of truth for product scope
3. No feature additions beyond what is explicitly asked
4. Read only relevant files/sections — Grep first to find the line, then Read with offset+limit. Never read whole files speculatively.
4a. Run /compact when context is getting long.
5. Focus on stable, shippable, working code

## Resume Chain

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`
