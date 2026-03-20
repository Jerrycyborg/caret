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

## Session Notes (2026-03-19, cont. #3)
- Fleet deployment built: `deploy-linux.sh` for ISPConfig, `caret-mgmt.service` systemd unit, `nginx.conf` for `/admin` subpath, `fleet-installer.nsi` + `build-fleet-installer.ps1` for 100-machine Windows rollout via GPO/Intune/PDQ. Commit: `6cf4eb7`.
- Deployment flow: (1) run deploy-linux.sh on ISPConfig server → (2) add nginx snippet to ISPConfig vhost → (3) set Jira/org config in dashboard at `https://caret.tws-partners.com/admin/` → (4) build fleet installer with `build-fleet-installer.ps1` → (5) deploy `Caret-Fleet-Setup.exe` via GPO/Intune.

## Session Notes (2026-03-19, cont. #2)
- Central config push: management server `fleet_config` table + `GET/PUT /v1/config`; checkin response includes config; Caret client applies it via `_apply_server_config()`. IT sets Jira credentials once on server, all devices pick up on next checkin. Commit: `effc9a2`.

## Session Notes (2026-03-19, cont.)
- Jira integration completed: Settings Jira config card (project key, issue type, OAuth client ID/secret, Save/Sign in/Sign out/Test buttons, connection badge). OAuth polling fixed from one-shot 6s to interval polling every 3s up to 2min. Commit: `a74c1d1`.
- To set up Jira: create OAuth 2.0 app at developer.atlassian.com → set redirect URI to `http://localhost:8000/v1/settings/jira/oauth/callback` → enter client ID + secret in Settings → click Sign in with Jira.

## Session Notes (2026-03-19)
- CleanDisk fixed: was hanging app because `needs_elevation: true` routed through `-Wait` UAC path. Dropped `C:\Windows\Temp` cleanup (needs admin); now user-level only (user TEMP + Recycle Bin). Commit: `be6d965`.
- Certificate expiry detection shipped: Rust `cert_warnings` in `ComplianceStatus` (parallel PowerShell thread), SecurityPanel "Certificates" card (green OK / amber N expiring), backend `check_expiring_certificates()` + `cert_expiry_warning` daemon signal. Commit: `9ad4546`.
- Central management server built: `management-server/` — FastAPI + SQLite, fleet dashboard at `/`, REST API for checkins/devices/summary, bearer token auth, online/stale/offline status. Commit: `19389f0`.
- Client checkin payload expanded: `disk_used_pct`, `open_incidents`, `compliance_issues` now sent on each checkin.
- Next priority: fleet installer with env var injection, then Jira.

## Session Notes (2026-03-18, cont. #4)
- Admin detection still failing after whoami SID fix: root cause was PATH — `whoami` in Caret process resolved to wrong binary. Fixed by using `$env:SystemRoot\System32\whoami.exe` absolute path + fallback via `net localgroup Administrators` checking both local and domain-prefixed username (`ADS\lawrencem`). Commit: `eae1341`.
- Dark/light theme toggle added to sidebar footer (sun/moon icon, persists via localStorage). Commit: `1c2e9be`.
- Favicon replaced — custom SVG icon (purple gradient diamond) generated via Python PIL + `tauri icon` CLI; title fixed from "Oxy" to "Caret". Commit: `2147768`.
- Admin actions redesigned: flat button row → 3-column card grid with group label + icon + name. Double firewall buttons removed; replaced with single contextual card. Commit: `1c2e9be`.
- Added CleanDisk, contextual Restart Print Spooler, Windows Update age detection. Commit: `6ee2cb8`.

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

## Session Notes (2026-03-20)
- v0.2.6 pre-fleet polish: all Tier 1/2/3 plan items implemented and verified. Commit: pending.
- Fleet-breaking bugs fixed: management daemon wrong dict key (`incidents_summary` → `summary`); stale version defaults (`0.1.2`/`0.1.9` → `0.2.6`); SecurityPanel UAC cancel freeze (try/catch on both invoke calls); plugin relative path → `app_data_dir()`.
- Code quality: `BACKEND_URL` extracted to `src/config.ts` (7 files updated); support_daemon chained comparison fixed; duplicate `run_command` removed from `privilege/mod.rs`; `run_command` made `pub(crate)` in `lib.rs`.
- CPU spike fix: `ProcessRefreshKind::everything()` removed from `get_system_info` — was enumerating all 200+ processes on every Home tab load. Now only CPU + memory refresh.
- Security panel speed: 4 separate PS spawns (defender, reboot, spooler, certs) merged into 1 combined script; `recv_timeout(10s)` on all channels; 60s startup delay added to support daemon.
- Help tab: native `<select>` model dropdown replaced with Copilot pill UI (fixes WebView2 dropdown close bug). AI provider locked to Microsoft Copilot (`azure/gpt-4o`). `backend/routers/models.py` simplified to Copilot-only.
- Clear Teams Cache fix: old script targeted only one specific EBWebView subfolder (always 0 on New Teams). New script dynamically scans full `LocalCache` tree for known cache folder names — works for both classic and MSIX New Teams.
- UX fixes: "Monitor" badge on Home → "Normal" (less alarming); action result card now shows specific result text first (not generic "Sensitive OS action..."); "Running with elevated privileges…" → "Running…" (non-UAC actions were showing wrong label); confirm button shows "run now" vs "run with UAC" correctly based on execution_path.

## Current State (v0.2.6)

- **Security panel**: 8 compliance cards — Firewall, Disk Encryption (tri-state), Antivirus, Windows Update, Print Spooler, Certificates (30-day expiry), System Events (expandable + inline fix buttons), Network
- **Admin actions** (all verified working): Flush DNS (UAC), Clear Teams Cache (no UAC, New+classic Teams), Reset OneDrive (no UAC), Restart Audio Devices (UAC), Clean Disk (no UAC, user TEMP + Recycle Bin), DISM + SFC Repair (visible elevated window)
- **AI**: Locked to Microsoft Copilot (`azure/gpt-4o`). Copilot pill in Help tab with Ready/Not configured badge. Model status from `/v1/models/status`.
- **Home**: CPU/RAM/disk tiles; "Healthy" / "Normal" / "Needs Attention" badge (not "Monitor"); backend poll at 10s; 60s daemon startup delay reduces launch CPU spike.
- **Detection signals**: disk, CPU, RAM, Windows Update staleness, Defender off, Spooler stopped, audio/camera device errors, OneDrive stuck, Teams call lag, certificate expiry
- **Fleet**: management server (ISPConfig + Nginx + systemd), NSIS fleet installer with env var injection, central config push on checkin
- **Admin detection**: absolute path whoami + `net localgroup` fallback; local and domain admins
- **Dark/light theme**: sidebar footer toggle, localStorage-persisted
- Settings hidden from non-admins; Jira config env-var-only

## Next Priorities
1. Verify fleet installer env var injection with real machine (`Caret-Fleet-Setup.exe` via GPO/Intune)
2. End-to-end smoke test on a fresh Windows VM (non-admin user + admin user)
3. Backend sidecar rebuild if Python deps changed

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

1. **Fleet installer with env var injection** — NSIS deploy with `CARET_JIRA_*`, `CARET_ADMIN_GROUP`, `CARET_MANAGEMENT_*` pre-baked. Prerequisite for fleet rollout.
2. **Microsoft Copilot auth (MSAL SSO)** — on hold, needs Azure AD app registration.

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
