# AAHP — Oxy Handoff

## Source Of Truth

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

## Product Role

Oxy is:

- a local-first AI operator hub
- a device-support assistant
- a developer-support assistant
- the main reporting surface for OpenClaw and Wraith

Ownership:

- frontend: sessions, chat, tasks, approvals, timeline
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
- external executors report back into Oxy task/session history
- agent roles are supervised metadata only:
  - planner
  - executor
  - reviewer

## Current Constraints

- OpenClaw and Wraith are structured executor adapters, not peer orchestrators
- OpenClaw and Wraith are not live-integrated yet; current build uses the executor contract and Oxy-side reporting model
- privileged local actions stay in Rust
- Telegram and WhatsApp are session/channel contracts right now, not full provider integrations
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

1. stabilize the new task-domain/executor contract with tests
2. make chat/session reporting richer across channels
3. wire a real Telegram adapter first
4. then wire OpenClaw and Wraith integrations behind the executor adapter contract
