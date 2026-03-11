# Oxy

Oxy is an internal operator shell for macOS and Ubuntu built on Tauri, React, Rust, FastAPI, and SQLite.

Current direction:

- supervised task orchestration instead of chat-only interaction
- approval-first execution for writes
- Rust-only routing for privileged OS actions
- compact local adapter layer for repo and workflow tasks

The current source-of-truth order is:

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

## Current Capabilities

- chat with conversation persistence
- task planning from action-oriented prompts
- ordered task steps with timeline events
- read steps that auto-run
- write steps that pause for approval
- privileged actions delegated to the Rust security path
- local adapters for:
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

## Stack

- Tauri 2
- React 19 + TypeScript
- Rust
- FastAPI
- SQLite

## Development

Prerequisites:

- Node.js 18+
- Rust toolchain
- Python 3.9+

Install:

```sh
npm install
```

Run backend:

```sh
npm run backend
```

Run desktop app:

```sh
npm run tauri dev
```

## Verification

Frontend verification:

```sh
npm run verify:frontend
```

Rust verification:

```sh
npm run verify:rust
```

Full local target:

```sh
npm run verify:all
```

Note:

- on this cloud-synced workspace, Jest has intermittently failed with filesystem `ETIMEDOUT` reads from `node_modules`
- `tsc && vite build` and backend import/startup checks are currently passing

## Scope Boundaries

Current priority:

- orchestrator hardening
- unified approval policy
- local adapter growth
- tighter chat/task integration

Deferred:

- browser/API adapters
- plugin sandbox and plugin manifest
- hardware/model routing
- multi-agent orchestration

## Repo Guidance

- extend the current repo; do not redesign it
- keep privileged OS actions in Rust
- prefer small additive backend/frontend changes
- keep docs compact and update only the tracked source-of-truth files
