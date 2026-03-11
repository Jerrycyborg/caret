# Oxy Build Blueprint

## Why This Build Exists

This build exists to ship Oxy as an internal operator shell on macOS and Ubuntu.

Near-term product goal:

- supervised orchestration over local tools and machine resources
- Oxy as the main reporting/control surface for local and connected executors
- approval-first execution for writes and privileged actions
- compact task, approval, and timeline flow across chat and task UI
- repeatable local and CI verification

## Release Goal

Ship Oxy as a production-grade desktop assistant for macOS and Ubuntu with:

- a repeatable local verification path
- CI that mirrors release-readiness checks
- platform-specific release checklists
- explicit gates between development, verification, packaging, and shipping

## V1 Product Contract

V1 ships as an internal-only operator shell for power users on macOS and Ubuntu.

### Audience

- internal power users only
- controlled environments, not general consumer distribution

### Product Direction

- autonomous operator shell over local OS capabilities and your existing tool ecosystem
- high workflow autonomy for planning and multi-step execution
- in-app approval plus OS-native auth boundaries for sensitive system mutations
- adapter-first integration for a few critical tools, with local CLI adapters first
- hardware-aware detect-and-route execution, not deep vendor-specific optimization

### In Scope for V1

- chat with optional task handoff
- multi-channel session metadata for desktop, Telegram, and WhatsApp
- backend task orchestrator with ordered steps and timeline events
- task classes and execution domains:
  - `local_device`
  - `local_dev`
  - `openclaw`
  - `wraith`
- deterministic prompt classes for supervised task planning
- task-level plan approval with privileged boundary stops
- supervised agent-role state behind the orchestrator
- structured executor adapters:
  - `local_device_executor`
  - `local_dev_executor`
  - `openclaw_executor`
  - `wraith_executor`
- compact local tool registry:
  - `file.read`
  - `file.write`
  - `git.status`
  - `git.diff`
  - `git.log`
  - `git.show`
  - `project.search`
  - `project.tree`
  - `project.read_many`
  - bounded `shell.run`
  - allowlisted `build.run`
- privileged OS actions with explicit approval and Rust-only routing
- task list, approval panel, and execution timeline
- split product lanes:
  - `Support` for local incidents, fix queue, escalations, and history
  - `Workflows` for repo/dev, OpenClaw, and Wraith execution
- local support daemon that can watch device-health thresholds and auto-create supervised support incidents
- support incident metadata on the shared task engine:
  - `task_kind`
  - `support_category`
  - `support_severity`
  - `trigger_source`
  - `auto_fix_eligible`
  - `auto_fix_attempted`
  - `auto_fix_result`
- safe auto-fix allowlist for non-privileged local remediation only

### Non-Goals for V1

- public or non-technical user release
- unrestricted autonomous admin mode
- unattended privileged execution
- broad third-party plugin marketplace distribution
- deep Metal/CUDA/NPU optimization work
- many-tool shallow integration

## Release Lanes

### Lane 1: Developer Verification

Fast local feedback for active work.

- `npm run verify:frontend`
- `npm run verify:rust`
- `python -m unittest discover backend/tests`
- `npm run tauri dev`
- `npm run backend`

### Lane 2: Ubuntu Packaging Readiness

Proves Linux CI can install native dependencies, verify the codebase, and build the Tauri app.

- install Linux packaging dependencies
- run frontend verification
- run Rust verification
- run `npx tauri build`

### Lane 3: macOS Release Readiness

Proves the codebase verifies on macOS and is ready for a signed packaging pass.

- run frontend verification
- run Rust verification
- run `npx tauri build`
- complete the macOS release checklist before shipping

## Build Structure

Fixed-location files that must remain where their toolchains expect them:

- `.github/workflows/ci.yml`
- `package.json`
- `tsconfig.json`
- `vite.config.ts`
- `src-tauri/Cargo.toml`
- `src-tauri/tauri.conf.json`

Centralized build-maintenance files:

- `build/config/`
- `build/ci/`
- `build/checklists/`
- `build/Core_blueprint.md`
- `build/BUILD_BLUEPRINT.md`
- `AAHP.md`
- `release.json`
- `CHANGELOG.md`

## Acceptance Gates

### Gate A: Code Health

- [ ] `npm install`
- [ ] `npm run verify:frontend`
- [ ] `npm run verify:rust`
- [ ] `python -m unittest discover backend/tests`

### Gate B: App Viability

- [ ] Backend starts with `npm run backend`
- [ ] Desktop app starts with `npm run tauri dev`
- [ ] Chat works against the backend
- [ ] Session list can show channel source and session state
- [ ] Action-oriented chat can emit a task handoff
- [ ] Task handoff can include immediate read-only execution summary
- [ ] Support incidents stay visible in the Support lane instead of the Workflow lane
- [ ] Task updates can be written back into conversation/session history as compact reports
- [ ] Channel messages can resolve/create sessions and return compact replies
- [ ] Tasks show execution domain, assigned executor, and approval scope
- [ ] Support shows monitoring, fix queue, escalations, and history clearly
- [ ] Read-only task steps auto-run and record timeline events
- [ ] Write steps stop for approval and do not execute early
- [ ] Tool adapters are visible through a common registry/contract
- [ ] Executor adapters are visible through a common registry/contract
- [ ] `project.search` executes within workspace bounds
- [ ] Security actions fail safely when privileges are unavailable

### Gate C: Platform Readiness

- [ ] Ubuntu CI installs required native packages and completes `npx tauri build`
- [ ] macOS CI completes verification and local packaging validation is documented
- [ ] Release checklist is completed for the target platform

### Gate D: Shipping Readiness

- [ ] Feature scope for the release is explicit
- [ ] Sensitive OS actions have a defined privilege model
- [ ] Demo/stub features are either removed, gated, or labeled clearly
- [ ] Release owner and rollback path are defined

## Platform Checklists

- Ubuntu: `build/checklists/ubuntu-release.md`
- macOS: `build/checklists/macos-release.md`

## Production Risks Still Open

- privileged OS actions still need full release-grade elevation hardening
- backend approval policy is stronger, but not yet unified across every UI mutation path
- support auto-fix is intentionally narrow and only covers safe deterministic actions today
- OpenClaw and Wraith are adapter contracts only; live subsystem integration is still open
- Telegram now has a webhook-ready adapter path; provider deployment and secrets management are still open
- WhatsApp is still a session/channel contract only; provider wiring is still open
- browser/API adapters are deferred
- hardware/model routing is deferred
- packaging/signing ownership is still not encoded in the repo

## Handoff Rule

When resuming work:

1. read `build/Core_blueprint.md` for product direction
2. read `build/BUILD_BLUEPRINT.md` for build/release constraints
3. read `AAHP.md` for current implementation state
4. check `release.json` and `CHANGELOG.md` before cutting or describing a milestone

Do not create parallel roadmap or handoff files unless the repo explicitly adopts them as tracked sources of truth.

## Operating Rule

If a build or verification step is added, it should live under `build/` unless the underlying tool requires a fixed path.
