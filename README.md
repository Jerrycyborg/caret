<div align="center">

# Oxy

### Supervised AI operator shell for macOS and Ubuntu

<p>
  <strong>Tauri 2</strong> •
  <strong>React 19</strong> •
  <strong>Rust</strong> •
  <strong>FastAPI</strong> •
  <strong>SQLite</strong>
</p>

<p>
  Plan → Ask → Execute → Observe → Suggest next move
</p>

</div>

---

## What Oxy Is

Oxy is not a chat wrapper and not an unrestricted autonomous agent.

It is an internal operator shell that can:

- turn action-oriented prompts into supervised tasks
- auto-run safe read steps
- stop writes for approval
- delegate privileged OS actions to the Rust layer
- keep task state, approvals, executions, and policy events in one flow

## Current Product Shape

Oxy currently works as a compact supervised kernel:

- chat with conversation persistence
- backend task orchestrator
- ordered step execution
- approval-first workflow for mutations
- execution timeline and approval panel
- Rust-only privileged system path

Current source-of-truth order:

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

## Architecture

### Frontend

- chat
- tasks
- approvals
- execution timeline
- system panels

### Backend

- task planning
- task and step state machine
- approval policy
- tool registry
- execution logging
- SQLite persistence

### Rust / Tauri

- system inspection
- privileged OS actions
- local machine control

Rule:

- backend handles repo and workflow actions
- Rust handles privileged OS mutations

## Current Capabilities

### Task Flow

- action-oriented chat can create a task handoff
- deterministic prompt classes for supervised tasks
- read steps auto-run
- write steps wait for approval
- privileged requests stay visible but are delegated to Rust

### Local Adapters

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

## Quick Start

### Prerequisites

- Node.js 18+
- Rust toolchain
- Python 3.9+

### Install

```sh
npm install
```

### Run Backend

```sh
npm run backend
```

### Run Desktop App

```sh
npm run tauri dev
```

## Verification

Frontend:

```sh
npm run verify:frontend
```

Rust:

```sh
npm run verify:rust
```

Full local target:

```sh
npm run verify:all
```

Current note:

- `tsc && vite build` is passing
- backend import/startup is passing
- Jest has intermittently failed on this cloud-synced workspace with `ETIMEDOUT` reads from `node_modules`

## Scope Boundaries

### In Scope Now

- orchestrator hardening
- approval policy unification
- local adapter growth
- tighter chat/task integration

### Deferred

- browser/API adapters
- plugin sandbox and plugin manifest
- hardware/model routing
- multi-agent orchestration

## Repo Guidance

- extend the current repo; do not redesign it
- keep privileged OS actions in Rust
- prefer additive changes over broad refactors
- keep docs compact and tracked through the blueprint chain
