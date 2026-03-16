# Caret Build Blueprint

This build exists to ship Caret as a lightweight local OS assistant, starting with Windows packaging and support-first behavior.

## Current Build Contract

Ship Caret as a desktop app with:
- bundled backend sidecar
- support-first UI
- safe auto-fix for bounded local issues
- Rust-backed privileged boundaries
- Jira visible to normal users
- optional local-model setup after install, not bundled in the installer
- management channel to a central control server (org-configured, disabled by default)

## Visible Product Scope

Included:
- Sessions
- Support
- System
- Security
- Settings (incl. management server config)

Removed from visible product:
- plugin marketplace surfaces
- workflow/task shell surfaces
- OpenClaw/Wraith product exposure

## Packaging Rules

Keep the app light:
- no bundled model weights
- no Docker
- no external Python requirement on target devices
- no generic shell runtime
- Windows-only target: no macOS or Linux build paths

## Platform Constraint

**Windows only.** All Rust code is written without `#[cfg]` platform guards.
macOS and Linux code paths have been removed. Do not reintroduce them.

## Fork Baseline

Caret forks from:
- `personal-oxy-baseline-v0.6.2`

The original Oxy repo remains the preserved personal/internal build.

## Central Control Plane (In Progress)

Architecture:
- Control server URL set in Settings (`management.server_url`), empty = disabled
- Sidecar polls control server on interval for policy/config deltas
- Sidecar sends device health snapshot on checkin
- Tauri layer reports management connection status to the UI

Scope boundary:
- The sidecar owns the management channel (not the Tauri/Rust layer)
- The Tauri layer only surfaces the connection status and the config field
