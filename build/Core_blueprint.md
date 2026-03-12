# Caret Core Blueprint

Caret is a supervised local OS assistant focused on device care.

## Core Identity

Caret is:
- local-first
- support-first
- lightweight
- policy-bounded
- safe around privileged actions

Caret is not a general plugin marketplace, not a visible workflow engine, and not a public multi-agent surface.
Dormant executor/task infrastructure may remain behind the scenes for stability, but the visible product is narrowed to device support.

## Main Product Lanes

- `Sessions` for support conversations and guided help
- `Support` for incidents, monitoring, auto-fix, escalation, and ticketing
- `System` for readable machine status
- `Security` for privileged machine visibility and controlled actions
- `Settings` for local model setup, Jira config, and deployment policy

## Architectural Guardrails

- Tauri shell stays thin
- Rust owns privileged local actions
- local backend stays loopback-only
- support incidents remain the main visible work unit
- auto-fix stays deterministic and auditable
- optional local models must not bloat the installer

## Near-Term Priority

1. stability of installed app behavior
2. support automation and safe remediation
3. lightweight local-model setup
4. org-ready ticketing and deployment config
