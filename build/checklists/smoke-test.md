# Caret Smoke Test Checklist

Run this checklist on a real Windows 10/11 device after installing a fresh build.

## Pre-Test Setup

- [ ] Install `caret_<version>_x64-setup.exe` on a clean Windows 10/11 machine
- [ ] Set the following env vars via IT deployment mechanism or a `.env` file alongside the sidecar:

| Variable | Test value |
|---|---|
| `CARET_JIRA_BASE_URL` | Your Jira instance URL |
| `CARET_JIRA_PROJECT_KEY` | A test project key |
| `CARET_JIRA_USER_EMAIL` | Service account email |
| `CARET_JIRA_API_TOKEN` | Valid API token |
| `CARET_JIRA_OAUTH_CLIENT_ID` | Atlassian OAuth client ID |
| `CARET_JIRA_OAUTH_CLIENT_SECRET` | Atlassian OAuth client secret |
| `CARET_ADMIN_GROUP` | `ROL-ADM-Admins` (or leave empty to test local admin fallback) |
| `CARET_MANAGEMENT_SERVER_URL` | Test management server URL (optional) |
| `CARET_MANAGEMENT_TOKEN` | Bearer token (optional) |
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | A valid cloud AI key — OR have Ollama running locally |

---

## 1. Startup

- [No] App launches without an error dialog or crash
- [No] Home dashboard loads — CPU, RAM, and disk tiles all show values
- [No...empty] Active incidents section renders (empty list is fine)
- [No] No "Backend offline" banner on first open
- [No] Backend online indicator shows green in the Help tab

---

## 2. Help Tab — No AI Configured

> Re-test with no API keys set and no Ollama running.

- [ ] Amber banner appears: "No AI model is configured for this device. Contact IT to enable the Help assistant."
- [No] Textarea is disabled
- [No] Send button is disabled
- [No] No crash or blank screen

---

## 3. Help Tab — AI Configured

- [No] Model selector is visible in the header
- [NO] Send a short message → response streams token by token
- [Yes] Shift+Enter inserts a newline; Enter sends
- [No] Conversation appears in the sidebar list after first message
- [No] Switching to a different conversation loads its history correctly

---

## 4. Incidents Panel

- [No] Panel loads without error
- [ ] Triggering a test incident from Home "Get IT Help" creates an entry in the list
- [ ] Incident detail view shows status, description, and timestamp
- [ ] "Create IT ticket" button is present on an incident with Jira configured

---

## 5. Jira — Basic Auth Ticket Creation

- [ ] Open an incident, click "Create IT ticket"
- [ ] Ticket appears in Jira with the correct project and issue type
- [ ] Description renders as multi-line paragraphs (not a single text blob)
- [ ] No raw newline characters visible in the Jira description

---

## 6. Jira — Test Connection (Admin)

- [ ] Open Settings as an admin
- [ ] Fill in Jira base URL, project key, user email
- [ ] Click "Test connection" → shows "Connected as \<display name\>"
- [ ] Invalid credentials → shows the error detail from Jira (not a generic failure)

---

## 7. Jira OAuth Flow

- [ ] IT has pre-set `CARET_JIRA_OAUTH_CLIENT_ID` + `CARET_JIRA_OAUTH_CLIENT_SECRET`
- [ ] Incidents panel shows "Sign in with Jira" banner for a non-connected user
- [ ] Clicking the button opens the system browser to the Atlassian authorise page
- [ ] After approving in the browser, the banner disappears within ~10 seconds
- [ ] A ticket created after OAuth uses Bearer token auth (verify in Jira audit log if available)
- [ ] "Sign out" in Settings clears the token; banner reappears in Incidents panel on next load

---

## 8. Settings — Non-Admin User

- [No] Log in as a standard domain user (not in `ROL-ADM-Admins` / not a local admin)
- [No] Open Settings → sees "Settings are managed by your IT department"
- [No] Management server status badge is visible
- [No] No editable fields are shown
- [No] No way to reach Jira credentials or support policy config

---

## 9. Settings — Admin User

- [ ] Log in as a member of `ROL-ADM-Admins` (or a local admin if `CARET_ADMIN_GROUP` is empty)
- [No] Open Settings → full config panel is visible
- [No] All sections present: Org, Ticketing, Support Policy, Management
- [No] Changes saved in Settings persist after app restart

---

## 10. Security Panel
(crashed. whole app - stuck)
- [No] Panel loads and shows: firewall state, BitLocker status, system event error count, active connection count
- [No] Non-admin user: action buttons are absent or show a "Requires admin" message
- [No] Admin user: clicking a remediation action triggers a UAC prompt
- [No] After UAC approval: action executes and result is shown in the panel

---

## 11. Management Checkin

- [ ] With `CARET_MANAGEMENT_SERVER_URL` set: Settings management card shows "Connected"
- [ ] Management server receives `POST /v1/devices/checkin` with hostname, version, and health payload
- [ ] With `CARET_MANAGEMENT_TOKEN` set: `Authorization: Bearer <token>` header is present in the checkin request
- [ ] With no URL set: status shows "Not configured" — no errors logged

---

## 12. Edge Cases and Security

- [No] Start app with no network → Ollama fetch times out silently (no crash; amber banner shown in Help tab)
- [ ] Set `CARET_ADMIN_GROUP` to a value with special characters (e.g. `foo;bar`) → user is treated as non-admin; no PowerShell execution; no injection
- [ ] Revoke Jira OAuth in Settings → "Sign in with Jira" banner reappears in Incidents panel on next load
- [ ] Kill the backend sidecar mid-conversation → "Could not reach the Caret backend" error appears in chat; backend status indicator flips to offline
- [No] Relaunch after sidecar kill → sidecar restarts automatically; app recovers without manual intervention
