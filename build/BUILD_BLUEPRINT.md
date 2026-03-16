# Caret Build Blueprint

Ship Caret as a lightweight Windows desktop app with a bundled backend sidecar, support-first UI, and zero user configuration required.

## Current Build Contract

- Bundled backend sidecar (`caret-backend.exe`)
- Support-first UI: Home, Help, Incidents, Security, Settings
- Safe auto-fix for bounded local issues (deterministic allowlist)
- Rust-backed privileged boundaries with UAC elevation
- Jira ticket creation — Basic auth and OAuth 2.0 (3LO)
- AI chat — local Ollama or cloud API key; graceful no-model state if neither is configured
- Admin-gated Settings — non-admins see managed view
- Management channel to a central control server (org-configured, disabled by default)
- Optional local-model setup after install; not bundled in the installer

## Visible Product Scope

Included:
- Home dashboard
- Help (AI chat)
- Incidents (monitoring, auto-fix, Jira escalation)
- Security panel
- Settings (admin-only)

Not included:
- Plugin marketplace
- Workflow/task shell
- OpenClaw/Wraith product surfaces
- macOS or Linux build paths

## Packaging Rules

Keep the installer light:
- No bundled model weights
- No Docker
- No external Python requirement on target devices (sidecar is self-contained)
- No generic shell runtime
- Windows-only target: no `#[cfg]` platform guards in Rust code

## Platform Constraint

**Windows only.** All Rust code is written without `#[cfg]` platform guards.
macOS and Linux code paths have been removed. Do not reintroduce them.

## IT Deployment

All credentials and configuration are supplied via environment variables at deploy time.
Users never enter credentials. See [README.md](../README.md) for the full env var list.

## Central Control Plane

Architecture:
- Control server URL set in Settings (`management.server_url`), empty = disabled
- Sidecar polls control server every 60s with device health snapshot
- Bearer token auth via `CARET_MANAGEMENT_TOKEN` env var
- Tauri layer surfaces connection status and the config field only

Scope boundary:
- The sidecar owns the management channel (not the Tauri/Rust layer)
- The Tauri layer only surfaces connection status and the config field

## Fork Baseline

Caret forks from `personal-oxy-baseline-v0.6.2`.
The original Oxy repo remains the preserved personal/internal build.
