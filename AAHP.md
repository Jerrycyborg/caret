# AAHP — Oxy Handoff

## Source Of Truth

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

Release tracking:

- `release.json` = current repo version + milestone marker
- `CHANGELOG.md` = compact milestone history

## Product Role

Oxy is:

- a local-first AI operator hub
- a device-support assistant
- a developer-support assistant
- the main reporting surface for OpenClaw and Wraith

Ownership:

- frontend: sessions, chat, support, workflows, approvals, timeline
- backend: orchestration, routing, policy, executor selection
- Rust: privileged local OS actions only

## Current Build State

- conversations now act as multi-channel sessions:
  - `desktop`
  - `telegram`
  - `whatsapp`
- tasks carry:
  - `task_class`
  - `execution_domain`
  - `reporting_target`
  - `approval_scope`
  - `assigned_executor`
  - `result_channel`
- task classes currently route to:
  - `device_support` -> `local_device_executor`
  - `developer_support` -> `local_dev_executor`
  - `project_build` -> `openclaw_executor`
  - `security_assessment` / `security_review` -> `wraith_executor`
- approvals are moving toward:
  - task-level plan approval
  - boundary approval for privileged local actions
- the shared task engine now carries support-lane metadata:
  - `task_kind`
  - `support_category`
  - `support_severity`
  - `support_decision_reason`
  - `support_recommended_fixes`
  - `support_source_signal`
  - `support_detected_at`
  - `support_last_decision_at`
  - `trigger_source`
  - `auto_fix_eligible`
  - `auto_fix_attempted`
  - `auto_fix_result`
- external executors report back into Oxy task/session history
- task creation, approval changes, and retries now write compact task reports back into conversation history
- Tauri-only panels now degrade safely in web/dev preview instead of crashing on missing runtime APIs
- chat now returns a local fallback response when the configured LLM provider is unavailable
- Files is no longer a top-level product tab; system status is now surfaced through a readable System dashboard
- Terminal is no longer a primary product tab; Support now owns local device incidents while Workflows owns repo/executor tasks
- Device Support is explicitly local-first and can monitor or triage issues without any LLM attached
- backend now runs a support daemon/watcher with deterministic checks, cooldown-based dedupe, support severity states, and safe auto-fix queueing
- queued safe fixes are now visible first and only auto-run on a later daemon cycle; they can also be triggered manually from the Support UI
- support incidents now expose explicit actions:
  - run safe fix
  - escalate
  - create IT ticket
- `last auto-fix` can now show real completed safe remediations
- Support now renders:
  - `Now`
  - `Monitoring`
  - `Fix Queue`
  - `Escalations`
  - `History`
- Support now uses a split-pane incident console with:
  - selected incident detail
  - decision rationale
  - recommended fixes
  - audit trail
  - task timeline
- support platform checks are now isolated behind a platform helper so Windows support has a defined code path
- Workflows now filters to non-support tasks so git/repo adapters stop dominating the local-support lane
- Settings now covers provider connections, integrations, approval policy, and runtime preferences instead of only model connectors
- Settings now also carries deployment-level org identity, ticketing, support policy, workflow policy, and integration toggles
- support incidents now store linked external ticket metadata on the shared task engine
- Jira is now the first live ticket adapter behind Oxy’s support lane
- provider secrets and Jira token are now runtime/env-only instead of being persisted in SQLite
- the unused Tauri shell capability has been removed from the desktop runtime surface
- a lightweight security verification lane now checks for shell-capability, shell-interpolation, and secret-persistence regressions
- agent roles are supervised metadata only:
  - planner
  - executor
  - reviewer
- backend contract tests now cover:
  - task classification and execution-domain routing
  - task-level approval and privileged boundary flow
  - executor registry/reporting contract
  - channel session reuse for Telegram/WhatsApp-style messages
  - support incident persistence and support daemon queue/escalation reporting
  - support incident detail payloads
  - queue-now / auto-run-next-cycle behavior

## Current Constraints

- OpenClaw and Wraith are structured executor adapters, not peer orchestrators
- OpenClaw and Wraith are not live-integrated yet; current build uses the executor contract and Oxy-side reporting model
- org-ready means single-tenant configurable right now, not multi-tenant
- privileged local actions stay in Rust
- OS-native secure secret storage is still not implemented; current model is env/runtime only
- Telegram now has a webhook-ready adapter path plus Oxy-side reporting, but bot deployment/secrets are still open
- WhatsApp is still a session/channel contract right now, not a full provider integration
- Windows now has backend support-monitoring coverage, fixed read-only command paths, a UAC-backed privileged execution path, and a CI verification lane, but broad runtime validation and packaging proof are still open
- Windows now also has a local MSI bootstrap script at `build/windows/install-from-git.ps1` so a git checkout can be installed and launched with one PowerShell command
- Windows packaging now targets a normal installed-app flow: MSI + setup EXE from GitHub Releases with a bundled backend sidecar EXE that Tauri launches automatically
- browser/API adapters are still deferred
- hardware/model routing is still deferred
- no autonomous multi-agent runtime yet

## Resume Rule

On resume:

1. verify the source-of-truth chain first
2. extend the existing task/session/executor contract instead of creating a second orchestration path
3. keep Oxy as the reporting surface
4. keep privileged local actions in Rust

## Next Recommended Focus

1. prove Jira ticket creation against a real deployment config
2. validate the packaged Windows lane on a real Windows device or runner artifact
3. broaden support auto-fix carefully while keeping it allowlist-only
4. then wire OpenClaw and Wraith integrations behind the executor adapter contract
