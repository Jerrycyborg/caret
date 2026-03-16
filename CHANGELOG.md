# Changelog

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
