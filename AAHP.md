# AAHP — Oxy Development Checkpoint

Adaptive AI-Handoff Protocol for this repo.

## Source Of Truth

Use these documents in this order:

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

If this file conflicts with the build blueprints, the build blueprints win.

## Project

**Name:** Oxy

**Definition:** Oxy is a user-supervised local orchestration assistant for tools, apps, and workflows on the machine.

It is not just a chat UI and not a fully autonomous agent.

Target behavior:

- plan
- ask
- execute
- observe
- suggest next move

**Primary stack:** Tauri 2 + React 19/TypeScript + Rust + FastAPI + SQLite

**Platforms:** macOS and Ubuntu

**Audience:** internal power users

## Product Direction

Oxy is heading toward:

- a session orchestrator kernel in the backend
- approval-first execution for all mutating or privileged actions
- a tool registry and adapter layer for local tools and services
- a Rust bridge for privileged OS actions and deep system access
- hardware-aware routing for local versus cloud execution later

## Current Architecture

### Frontend

Owns:

- chat
- settings
- resources
- files
- terminal
- security
- tasks

### Backend

Owns:

- conversation persistence
- model and settings routes
- task orchestration
- task state machine
- approvals and execution timeline
- tool registry for safe first adapters

### Rust/Tauri

Owns:

- system inspection
- privileged OS action bridge
- local adapter metadata exposed to UI

## Current Milestone State

### Stable

- conversation/chat flow with persistence
- settings and model selection
- resources/files/terminal panels
- security panel with Rust-routed privileged actions
- build verification and CI structure

### Current Build State

- backend task orchestration is active and tied to conversation context
- task responses are compact:
  - `task`
  - `steps`
  - `approvals`
  - `timeline`
  - `next_suggested_action`
- SQLite tracks:
  - tasks
  - task_steps
  - approvals
  - executions
  - tool_runs
  - policy_events
- read steps auto-run
- write steps require approval
- privileged steps are visible but delegated to Rust
- tool registry currently includes:
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
- chat can emit a task handoff for action-oriented prompts
- task handoff can include immediate read-only execution summary
- tasks UI shows active/completed tasks, pending/resolved approvals, and timeline events

### Still Open

- planner is deterministic and prompt-class based, but still shallow
- approval policy is not yet unified across every non-task UI mutation path
- browser/API adapters are deferred
- plugin sandbox and plugin manifest are deferred
- hardware/model routing is deferred
- no multi-agent layer yet

## Task State Model

Task states:

- `draft`
- `proposed`
- `awaiting_approval`
- `running`
- `done`
- `failed`

Step states:

- `draft`
- `proposed`
- `awaiting_approval`
- `running`
- `done`
- `failed`
- `rejected`

Policy:

- read actions auto-run
- write actions require approval
- privileged OS actions stay in Rust

## Tool Layer

Current backend tool registry includes:

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

Rules:

- no shell interpolation
- workspace-bounded file access
- approval before writes
- git reads auto-run
- privileged machine control is not exposed through backend tools

## Build And Verification

Primary local verification:

```bash
npm run verify:all
```

Development:

```bash
npm run backend
npm run tauri dev
```

CI:

- verify on Ubuntu and macOS
- package on Ubuntu

## Repo Guidance

- Extend the current repo; do not redesign it.
- Prefer additive backend services and routers over sweeping refactors.
- Keep chat flow working.
- Keep privileged OS actions in Rust.
- Use the tasks/orchestrator layer for future tool and workflow growth.

## Next Recommended Focus

1. strengthen planner depth and task decomposition
2. unify approval policy across all mutating actions
3. connect more of the chat flow directly to supervised execution
4. expand safe local adapters before browser/API work
5. add hardware/model routing after the orchestrator is stronger
