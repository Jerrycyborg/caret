# Changelog

## 0.2.5 — Fleet deployment: Linux server + Nginx + NSIS installer (2026-03-19)

### Management server — production deployment
- `server.py`: `CARET_ROOT_PATH` env var for `/admin` subpath support (FastAPI `root_path`)
- `caret-mgmt.service`: systemd unit — runs as `www-data`, auto-restarts on failure
- `nginx.conf`: reverse proxy config for `caret.tws-partners.com/admin/`
- `deploy-linux.sh`: one-shot deploy to ISPConfig server — installs deps, venv, systemd, Nginx snippet

### Fleet installer (Windows)
- `build/windows/fleet-installer.nsi`: NSIS script wraps Caret EXE; writes `CARET_MANAGEMENT_SERVER_URL`, `CARET_MANAGEMENT_TOKEN`, `CARET_ADMIN_GROUP`, `CARET_ORG_NAME` as HKLM env vars; sets Caret autostart
- `build/windows/build-fleet-installer.ps1`: interactive builder — prompts for config, calls makensis, outputs `Caret-Fleet-Setup.exe` ready for GPO/Intune/PDQ/SCCM

## 0.2.4 — Central config push via management server (2026-03-19)

### Management server
- `fleet_config` SQLite table; `GET /v1/config` (masked secrets); `PUT /v1/config` (saves all fleet config server-side)
- `POST /v1/devices/checkin` response now includes `config` dict (non-secret keys) — devices auto-apply on each checkin
- Dashboard: Fleet Configuration panel with all config fields (org, Jira, admin group); secrets stored server-side only

### Caret client
- `backend/services/management.py`: `_apply_server_config()` merges server-pushed config into local sections (ticketing, org, management) after every successful checkin — no per-device setup needed

## 0.2.3 — Jira Integration (2026-03-19)

### Settings — Jira config card
- `src/components/Settings.tsx`: added `ticketing` section to `ConfigState`; Jira config card in "Org and Ticketing" panel — project key, issue type, OAuth client ID, write-only client secret, connection status badge, Save / Sign in with Jira / Sign out / Test connection buttons

### Support — OAuth polling fix
- `src/components/Support.tsx`: replaced one-shot 6s `setTimeout` with `setInterval` polling every 3s (up to 40 attempts = 2 min) in both the top banner and incident detail sign-in button — reliably detects OAuth completion without timing out

## 0.2.2 — Central Management Server (2026-03-19)

### New: management-server/
- `server.py`: FastAPI + SQLite fleet server — `POST /v1/devices/checkin` (upsert device record + append checkin history); `GET /v1/devices` (fleet list with online/stale/offline status); `GET /v1/devices/{hostname}` (detail + last 20 checkins); `GET /v1/fleet/summary` (totals + avg health); `GET /` HTML fleet dashboard (auto-refreshes 30s, health bars, bearer token auth)
- `requirements.txt`: fastapi + uvicorn
- `run.ps1`: creates .venv, installs deps, starts server on port 8100
- Device status: online (<3m), stale (<15m), offline (>15m since last checkin)

### Enhancement — Client Checkin Payload
- `backend/services/management.py`: checkin now sends `disk_used_pct` (from daemon last_snapshot), `open_incidents` + `compliance_issues` (from daemon incidents_summary) so the fleet dashboard shows meaningful health data per device

## 0.2.1 — Certificate Expiry Detection + CleanDisk User-level Fix (2026-03-19)

### Bug Fixes
- `src-tauri/src/privilege/mod.rs`: `CleanDisk` now runs user-level (no UAC) — removes `C:\Windows\Temp` step (requires elevation), cleans only user TEMP + Recycle Bin; fixes app hang on click
- App was hanging after "Clean disk" click: `needs_elevation: true` routed through `execute_with_platform_auth` which blocks UI thread; fixed by setting `needs_elevation: false`

### New Detection Signal — Certificate Expiry
- `backend/services/support_platform.py`: `check_expiring_certificates(days=30)` — PowerShell query of `Cert:\CurrentUser\My`; returns list of `{Subject, Expiry, DaysLeft}` per expiring cert
- `backend/services/support_daemon.py`: `expiring_certs: list` field on `SupportSnapshot`; `cert_expiry_warning` incident — `action_required` if ≤7 days, `monitoring` otherwise; directs user to contact IT for renewal
- `src-tauri/src/lib.rs`: `cert_warnings: usize` added to `ComplianceStatus`; parallel thread checks `Cert:\CurrentUser\My` and counts certs expiring within 30 days
- `src/components/SecurityPanel.tsx`: "Certificates" card added to compliance grid — green "OK" / amber "N expiring"; included in summary bar issues count

## 0.2.0 — Admin Actions + Theme + Detection Signals (2026-03-18, cont. #4)

### Bug Fixes
- `src-tauri/src/lib.rs`: Admin detection fixed again — uses absolute path `$env:SystemRoot\System32\whoami.exe` + fallback via `net localgroup Administrators` matching both local and domain-prefixed names (`ADS\username`)
- `backend/services/support_daemon.py`: Disk usage now checks `C:\` instead of `Path.home()` — gives accurate system drive stats on Windows

### UI
- `src/App.css`: Light theme added (`[data-theme="light"]` CSS variables); sidebar footer + theme toggle button styles
- `src/App.tsx`: Theme state with localStorage persistence; applies `data-theme` to `<html>`
- `src/components/Sidebar.tsx`: Theme toggle button (sun/moon) in sidebar footer
- `src/components/SecurityPanel.tsx`: Admin action buttons redesigned as 3-column card grid (icon + group label + name); removed double firewall buttons, replaced with single contextual card
- `index.html`: Title fixed from "Oxy" to "Caret"; favicon updated to custom SVG icon
- `src/caret-icon.svg`: New Caret SVG favicon (purple gradient diamond)
- `src-tauri/icons/`: All platform icon sizes regenerated from custom 1024×1024 PNG source

### New Admin Actions
- `src-tauri/src/privilege/mod.rs`: `CleanDisk` action — deletes user TEMP, `C:\Windows\Temp`, empties Recycle Bin via UAC; reports freed MB
- `src/components/SecurityPanel.tsx`: "Clean disk" card added to admin grid; contextual "Restart Print Spooler" card appears only when spooler is stopped

### New Detection Signal
- `backend/services/support_platform.py`: `check_windows_update_age_days()` — reads `LastSuccessTime` from Windows Update registry key
- `backend/services/support_daemon.py`: `windows_update_age_days` field in `SupportSnapshot`; `windows_update_stale` signal at ≥30 days (action_required) and ≥14 days (monitoring)

## 0.2.0 — Security Bug Fixes + System Events Drill-down (2026-03-18, cont. #3)

### Bug Fixes — Security Panel
- `src-tauri/src/lib.rs`: BitLocker detection fixed — replaced `Get-BitLockerVolume` (requires elevation) with `manage-bde -status C:` (works without elevation); previously always showed "Off" on non-elevated Tauri process
- `src-tauri/src/lib.rs`: Admin detection fixed — replaced `IsInRole(Administrator)` (checks UAC token elevation) with `whoami /groups /fo csv | ConvertFrom-Csv | Where SID -eq S-1-5-32-544`; now correctly detects local admin membership regardless of UAC state

### Feature — System Events Drill-down
- `src-tauri/src/lib.rs`: new `get_recent_events()` command — PowerShell pipe fetches last 50 System log events filtered to Error/Warning, returns up to 25 as `Vec<SystemEvent>` (time, id, level, source, message)
- `src/components/SecurityPanel.tsx`: System Events card is now clickable — expands inline to show event list with error (red) / warning (amber) row colouring; lazy-loads on first expand
- `src/App.css`: `.sec-events-list`, `.sec-event-row`, `.sec-event-error/warn`, `.sec-event-time/level/source/msg` styles added

## 0.2.0 — Security Panel Redesign + Expanded Compliance (2026-03-18)

### UI — Security Panel
- `src/components/SecurityPanel.tsx`: full redesign — replaced flat `compliance-row` list with card grid; 7 cards: Firewall, Disk Encryption, Antivirus, Windows Update, Print Spooler, System Events, Network; each card has SVG icon, status badge (ok/warn/critical), detail text, colour-coded left border
- `src/components/SecurityPanel.tsx`: summary bar at top — "All security checks passed" or "X issues detected"
- `src/components/SecurityPanel.tsx`: `ComplianceStatus` interface extended with `defender_enabled`, `pending_reboot`, `spooler_running`
- `src/App.css`: full Security panel CSS — `.sec-grid`, `.sec-card`, `.sec-ok/warn/critical/info`, `.sec-card-icon/body/title/detail`, `.sec-badge`, `.sec-summary` variants, `.sec-loading`

### Rust — Expanded Compliance Checks
- `src-tauri/src/lib.rs`: `ComplianceStatus` gains `defender_enabled`, `pending_reboot`, `spooler_running`
- `src-tauri/src/lib.rs`: `get_compliance_status()` adds 3 parallel thread checks — Defender registry key, Update reboot-pending registry keys, Print Spooler service status via PowerShell

## 0.2.0 — Broader Auto-Fix Signals (2026-03-18)

### Backend — New Health Detection Signals
- `backend/services/support_platform.py`: added `check_windows_update_pending_reboot()` — registry check for `WindowsUpdate\Auto Update\RebootRequired`, `Component Based Servicing\RebootPending`, `PendingFileRenameOperations`
- `backend/services/support_platform.py`: added `check_windows_service_running(name)` — `sc query` wrapper; defaults True on error to avoid false positives
- `backend/services/support_platform.py`: added `check_windows_defender_enabled()` — reads `DisableRealtimeMonitoring` registry key; True when key absent (3rd-party AV or Defender active)
- `backend/services/support_daemon.py`: `SupportSnapshot` gains `pending_reboot`, `spooler_running`, `defender_enabled` fields
- `backend/services/support_daemon.py`: `collect_support_snapshot()` calls the three new checks each daemon cycle
- `backend/services/support_daemon.py`: three new `SupportIssue` signals in `evaluate_support_snapshot()`:
  - `windows_update_reboot_pending` → `report_update_pending` auto-fix
  - `print_spooler_stopped` → `report_spooler_stopped` (escalates to IT — restart requires admin)
  - `defender_disabled` → `report_av_disabled` (escalates to IT security as incident)
- `backend/services/support_daemon.py`: three new apply functions and fix dispatcher entries for above categories

## 0.1.9 — Settings Cleanup + Jira UX Redesign (2026-03-18, cont. #2)

### UX — Settings
- `src/components/Settings.tsx`: removed Jira ticketing card entirely — Jira config is IT-deployed via env vars (`CARET_JIRA_OAUTH_CLIENT_ID`, `CARET_JIRA_OAUTH_CLIENT_SECRET`, etc.), not per-device UI; removed `ticketing` from `ConfigState` type and `EMPTY_CONFIG`; removed `jiraOauth` state and its fetch
- `src/components/Settings.tsx`: Settings page now shows only: Deployment identity, Management server, Admin group, Support policy, AI model keys

### UX — Navigation
- `src/App.tsx`: admin check lifted to app root — fetches config then invokes `get_admin_status` on mount; passes `isAdmin` boolean to Sidebar
- `src/components/Sidebar.tsx`: `isAdmin` prop added; Settings nav item filtered out for non-admin users

### UX — Incidents / Jira OAuth
- `src/components/Support.tsx`: "Create IT ticket" button in incident detail pane now shows "Sign in with Jira to create ticket" inline if Jira OAuth is configured but user not authenticated — one click opens browser, no Settings navigation needed

## 0.1.9 — Security Panel + Incidents Scroll Fix (2026-03-18, cont.)

### Performance
- `src-tauri/src/lib.rs`: `get_compliance_status` — all 4 checks (firewall, BitLocker, netstat, WinEvent) now run in parallel via `std::thread::spawn` + `mpsc::channel`; load time reduced from ~5s sequential to ~1-2s
- `src-tauri/src/lib.rs`: BitLocker PowerShell check wrapped in `try { } catch { $false }` — prevents crash on machines where `Get-BitLockerVolume` is unavailable

### UI — Incidents Panel
- `src/App.css`: `.support-section` gets `overflow-y: auto`; `.support-scroll` per-section overflow removed — whole panel now scrolls as one unit instead of multiple tiny constrained scroll areas

## 0.1.9 — Build & Runtime Fixes + Home Dashboard Redesign (2026-03-18)

### Bug Fixes
- `build/windows/build-backend.ps1`: added `--collect-submodules litellm --collect-data litellm` — litellm data files (model prices, cost map, etc.) were missing from PyInstaller bundle, causing backend crash on every startup
- `build/windows/build-backend.ps1`: moved `workpath`/`distpath` to `C:\Users\...\caret-pyinstaller\` — OneDrive was locking the old `build/windows/pyinstaller-build/` path mid-compile
- `src-tauri/src/lib.rs`: added `CREATE_NO_WINDOW (0x08000000)` to `run_command()` and `launch_backend_sidecar()` — suppresses CMD/PowerShell console window flash when Security tab loads or backend starts
- `src-tauri/src/privilege/mod.rs`: same `CREATE_NO_WINDOW` fix in `run_command()`; added `-WindowStyle Hidden` to `Start-Process -Verb RunAs` call

### UI — Home Dashboard
- `src/components/Home.tsx`: full redesign — time-of-day greeting, CPU brand shown, metric tiles with SVG icons + colour-coded percentage readouts, action cards with chevron animation replacing plain buttons, severity dot indicators on incident rows
- `src/App.css`: added complete Home CSS (was entirely missing — all `.home*`, `.health-tile*`, `.tile-*` classes were unstyled); refined CSS variables (darker bg, `--bg-card`, `--accent-glow`, `--shadow-card`, dim variants for success/warn/danger)

### UI — Sidebar
- `src/components/Sidebar.tsx`: replaced emoji nav icons with monoline SVG icons; logo now includes a layered stack SVG mark alongside the wordmark

### Project Hygiene
- `CLAUDE.md` (new): Claude Code instructions referencing resume chain (`Core_blueprint.md` → `BUILD_BLUEPRINT.md` → `AAHP.md`), build commands, known issues table, install notes

## 0.1.0 — Caret Fork Baseline

- forked from `personal-oxy-baseline-v0.6.2`
- rebranded the app, installer, sidecar, and local data path to `Caret`
- removed visible marketplace and workflow shell lanes from the product shell
- hid visible OpenClaw/Wraith references while preserving dormant backend stability
- kept Jira visible in Settings and Support
- kept Windows packaging path intact for the new product line

## 0.1.9 — Security Hardening + Oxy Remnant Removal

- Deleted `backend/services/telegram_adapter.py` and `backend/routers/channels.py` — Oxy leftovers, no place in a desktop IT support app
- Removed `integrations` config section (`telegram_enabled`, `whatsapp_enabled`) from backend, frontend type, and Settings UI
- Removed "Channel availability" card from Settings
- `backend/main.py`: removed `channels` router registration

- `src-tauri/src/lib.rs`: `get_admin_status` — strict allowlist validation on `admin_group` before PowerShell interpolation; rejects any value containing characters outside `[a-zA-Z0-9 \-_.]`; group name now passed via PS variable to eliminate string injection
- `backend/services/jira_oauth.py`: `_pending_states` — added 10-minute TTL per state and hard cap of 20 concurrent states; prune runs on every `build_auth_url` and `exchange_code` call
- `backend/services/config.py`: removed `OXY_` legacy env var fallback — dead code from fork ancestor
- `backend/main.py`: CORS tightened from `allow_methods=["*"]` and `allow_headers=["*"]` to explicit lists
- `backend/services/management.py`: checkin request now includes `Authorization: Bearer {CARET_MANAGEMENT_TOKEN}` header when `CARET_MANAGEMENT_TOKEN` env var is set

## 0.1.8 — Zero-Config User Experience

- `src/components/Settings.tsx`: admin-gated — non-admins see "Managed by IT" with management server status only; full settings visible to admins only; admin check runs on mount using configured `admin_group`
- `src/components/Support.tsx`: "Sign in with Jira" banner added — shown contextually when IT has configured OAuth but the user hasn't connected yet; disappears once signed in
- Users open the app and everything works — no credentials to enter, no settings to configure

## 0.1.7 — Jira OAuth 2.0 (3LO)

- `backend/database.py`: `oauth_tokens` table added
- `backend/services/jira_oauth.py` (new): OAuth flow — auth URL generation, code exchange, token refresh, status, clear; `app_configured` flag tells frontend whether IT has deployed credentials
- `backend/services/config.py`: `jira_oauth_client_id` added to ticketing section (env: `CARET_JIRA_OAUTH_CLIENT_ID`); `jira_oauth_client_secret` env-only (`CARET_JIRA_OAUTH_CLIENT_SECRET`), never stored in DB
- `backend/routers/settings.py`: `POST /oauth/start`, `GET /oauth/callback` (browser redirect handler), `GET /oauth/status`, `DELETE /oauth`
- `backend/services/ticketing.py`: Bearer token used when OAuth is connected; falls back to Basic auth
- `src/components/Settings.tsx`: users see "Sign in with Jira" button if IT has configured OAuth, "OAuth not configured — contact IT" if not; client ID/secret never exposed to users
- IT deploys with `CARET_JIRA_OAUTH_CLIENT_ID` + `CARET_JIRA_OAUTH_CLIENT_SECRET` env vars — one-time setup, all users get the Sign in button

## 0.1.6 — Jira Ticket Creation Fix + Test Connection

- `backend/services/ticketing.py`: fixed Jira description rendering — was a single ADF text node (newlines ignored), now splits into proper ADF paragraph nodes per line
- `backend/routers/settings.py`: new `POST /v1/settings/jira/test` endpoint — validates config, hits `/rest/api/3/myself`, returns `{ ok, authenticated_as }` or 400 with Jira's error detail
- `src/components/Settings.tsx`: "Test connection" button added to Jira card — shows `Connected as <display_name>` on success, error detail on failure; feedback stays visible 5s

## 0.1.5 — Security Panel Rebuild + Admin Access

- `src-tauri/src/lib.rs`: added `get_admin_status` (WindowsPrincipal local admin check, or AD group membership when `admin_group` is configured) and `get_compliance_status` (firewall, BitLocker, netstat ESTABLISHED count, EventLog errors)
- `src/components/SecurityPanel.tsx`: rebuilt from raw terminal dump to structured compliance view — firewall on/off, disk encryption, system event count, active connections; admin-gated action flow (idle → preview → UAC execute → done); non-admin users see view-only message; fetches `management.admin_group` from config and passes to `get_admin_status`
- `src/components/Settings.tsx`: added `management.admin_group` field — AD security group name; leave empty to use Windows local admin
- `backend/services/config.py`: added `admin_group` to `management` config section

## 0.1.4 — Startup Stabilisation + Orphan Cleanup

- `src-tauri/src/lib.rs`: new `get_backend_status` Tauri command — checks port, retries sidecar launch, returns `ready | starting | unavailable`
- `Home.tsx`: polls `get_backend_status` every 3s until ready, then loads incident data; shows clear startup state to user; stops polling once ready
- Deleted orphaned components: `Resources.tsx`, `Files.tsx`, `Terminal.tsx`, `ModelSelector.tsx`

## 0.1.3 — Nav Restructure + Home Dashboard

- `App.tsx`: View type is now `home | help | incidents | security | settings`
- `Sidebar.tsx`: new nav — Home, Help, Incidents, Security, Settings; chat list shown only on Help tab; removed System tab
- `Home.tsx` (new): device health tiles (CPU/RAM/disk), active incident list, "Get IT Help" + "View Incidents" quick actions, backend status indicator
- `Support` tab renamed to `Incidents`, `Sessions/Chat` renamed to `Help`
- System/Resources removed as standalone tab — health data promoted to Home
- `Resources.tsx` and `Files.tsx` and `Terminal.tsx` are now orphaned — safe to delete in cleanup pass

## 0.1.2 — Management Channel

- `backend/services/config.py`: added `management` section (`server_url`), removed Oxy leftovers (`workflow_policy`, `openclaw_enabled`/`wraith_enabled` from `integrations`), cleared default org name/env label
- `backend/services/management.py`: new checkin daemon — polls `{server_url}/v1/devices/checkin` every 60s with hostname, version, cpu/mem health; tracks status in memory (`not_configured` | `ok` | `unreachable` | `error`)
- `backend/routers/management.py`: new `GET /v1/management/status` endpoint
- `backend/main.py`: management daemon wired into lifespan alongside support daemon; version bumped to 0.1.2
- `src/components/Settings.tsx`: management card added (`management.server_url` field); live status badge reads from `/v1/management/status` (`Connected` / `Unreachable` / `Error` / `Not configured`)


## 0.1.1 — Windows-Only Debloat

- removed all macOS and Linux `#[cfg]` branches from `lib.rs`, `privilege/mod.rs`, `tools/mod.rs`
- `lib.rs`: sidecar lifecycle, system info commands, and OS commands are now Windows-only inline code
- `privilege/mod.rs`: removed `osascript`, `pfctl`, `launchctl`, `pwpolicy`, `kill`, `ufw`, `systemctl`, `usermod`, `sudo` paths; single Windows path per action
- `tools/mod.rs`: removed `ReferenceCliAdapter` (referenced `/usr/bin/printf`); registry is now `BackendSidecarAdapter` + `PluginRuntimeAdapter`; fixed stale "Oxy" reference
- `Cargo.toml`: removed `[patch.crates-io]` glib/gtk vendor patches (Linux GTK dependency, not needed on Windows)
- `get_home_dir` default fallback changed from `/` to `C:\`
