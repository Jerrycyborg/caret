# Changelog

## 0.5.1 - 2026-03-12

- moved provider secrets and Jira token handling to runtime/env-only instead of SQLite persistence
- removed the unused Tauri shell capability from the desktop runtime
- added a lightweight security verification lane for shell scope and secret-persistence regressions

## 0.5.0 - 2026-03-12

- added deployment-level org, ticketing, support-policy, workflow-policy, and integration config
- added manual IT ticket creation from Support with Jira as the first ticket adapter
- added external ticket linkage on shared support incidents
- tightened safe auto-fix execution with policy-aware queue running and post-fix rechecks
- clarified Workflows as the supervised non-support execution lane

## 0.4.0 - 2026-03-11

- split the product into dedicated `Support` and `Workflows` lanes
- added support incident metadata on the shared task engine
- added deterministic support watcher states, fix queue, escalations, and history
- added safe auto-fix metadata and narrow allowlisted remediation queueing
- made chat/task handoffs aware of support incidents vs workflows
- aligned README, blueprints, and handoff docs with the support-lane milestone

## 0.3.0 - 2026-03-11

- aligned Oxy as a local-first hub over OpenClaw and Wraith
- added execution domains, executor adapters, and task-level approval routing
- added multi-channel session metadata and Telegram-ready channel contract

## 0.2.0 - 2026-03-11

- added supervised backend task kernel with approvals, timeline, and tool registry
- added deterministic planner classes and initial local adapters
- connected chat to task handoff and shared execution reporting

## 0.1.0 - 2026-03-11

- established desktop shell, backend, and Tauri privilege/runtime structure
- added build blueprint, handoff chain, and initial repo verification flow
