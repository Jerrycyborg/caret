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
- queued safe fixes can now be executed automatically by the daemon or manually from the Support UI
- support incidents now expose explicit actions:
  - run safe fix
  - escalate
- `last auto-fix` can now show real completed safe remediations
- Support now renders:
  - `Now`
  - `Monitoring`
  - `Fix Queue`
  - `Escalations`
  - `History`
- support platform checks are now isolated behind a platform helper so Windows support has a defined code path
- Workflows now filters to non-support tasks so git/repo adapters stop dominating the local-support lane
- Settings now covers provider connections, integrations, approval policy, and runtime preferences instead of only model connectors
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

## Current Constraints

- OpenClaw and Wraith are structured executor adapters, not peer orchestrators
- OpenClaw and Wraith are not live-integrated yet; current build uses the executor contract and Oxy-side reporting model
- privileged local actions stay in Rust
- Telegram now has a webhook-ready adapter path plus Oxy-side reporting, but bot deployment/secrets are still open
- WhatsApp is still a session/channel contract right now, not a full provider integration
- Windows is now partially prepared at the backend support-monitoring layer, but the Tauri/Rust privilege and machine-control layer is still not Windows-ready
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

1. make support auto-fix broader but still allowlist-only
2. wire Telegram deployment/secrets and prove the adapter outside local tests
3. then wire OpenClaw and Wraith integrations behind the executor adapter contract
4. keep release hardening and verification cleanup visible while integrations land
