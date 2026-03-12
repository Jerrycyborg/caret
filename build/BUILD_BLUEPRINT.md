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

## Visible Product Scope

Included:
- Sessions
- Support
- System
- Security
- Settings

Removed from visible product:
- Marketplace
- Workflows
- OpenClaw/Wraith product exposure

## Packaging Rules

Keep the app light:
- no bundled model weights
- no Docker
- no external Python requirement on target devices
- no generic shell runtime

## Fork Baseline

Caret forks from:
- `personal-oxy-baseline-v0.6.2`

The original Oxy repo remains the personal/internal build.
