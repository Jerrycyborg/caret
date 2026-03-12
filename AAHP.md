# AAHP — Caret Handoff

## Identity

Caret is the product fork of Oxy, narrowed into a local OS/device assistant.

Preserved baseline:
- Oxy personal/internal build remains at `personal-oxy-baseline-v0.6.2`

Visible product lanes:
- `Sessions`
- `Support`
- `System`
- `Security`
- `Settings`

Hidden/dormant from inherited codebase:
- Marketplace
- Workflows UI
- OpenClaw/Wraith visible product references

## Current State

- Windows packaging path is preserved and rebranded to Caret
- backend sidecar name is now `caret-backend.exe`
- local data directory defaults to `.caret`
- Jira remains visible to standard users in Settings and Support
- support is the main incident/action lane
- task/executor backend machinery remains in code for stability, but is not part of the visible product

## Next Priority

1. stabilize packaged app startup and backend retry states
2. stage Security loading for Windows responsiveness
3. broaden safe auto-fix for cleanup and small local issues
4. add optional first-run Ollama-compatible local model setup

## Resume Rule

When resuming work, use this chain in order:
1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`
