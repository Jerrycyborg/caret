<div align="center">

<pre>
   ____  _   ___   __
  / __ \| | / / | / /
 / / / /| |/ /| |/ / 
/ /_/ / |   / |   /  
\____/  |_|\_\ |_|\_\ 
</pre>

# Oxy

### Local-first AI operator hub for macOS and Ubuntu

<p>
  <strong>Tauri 2</strong>
  ·
  <strong>React 19</strong>
  ·
  <strong>Rust</strong>
  ·
  <strong>FastAPI</strong>
  ·
  <strong>SQLite</strong>
</p>

<p><strong>Plan → Ask → Execute → Observe → Report back</strong></p>

</div>

---

> Oxy is the user-facing control layer.
> It helps on the local machine, routes work to connected executors, and keeps results, approvals, and reporting in one place.

## Why Oxy

Oxy is being built as:

- a device-support assistant living on the machine
- a developer-support assistant for local project work
- a supervised operator shell for desktop, Telegram, and WhatsApp sessions
- the main reporting surface above OpenClaw and Wraith

It is not:

- a chat-only wrapper
- an unrestricted autonomous agent
- a peer orchestrator beside OpenClaw or Wraith

## Product Shape

Oxy currently follows one control model:

1. user asks through a session
2. Oxy classifies the task
3. Oxy plans the work
4. Oxy asks for approval when required
5. Oxy executes locally or delegates to an executor
6. Oxy reports progress and results back into the session

## Architecture

| Layer | Responsibility |
|---|---|
| Frontend | Sessions, chat, tasks, approvals, timeline, operator console surfaces |
| Backend | Orchestration, task routing, approval policy, executor selection, reporting |
| Rust / Tauri | Privileged local OS actions, system inspection, machine control |

Core rule:

- backend handles supervised task orchestration
- Rust owns privileged local machine actions
- OpenClaw and Wraith stay behind Oxy as executor systems

## What Oxy Can Do Today

### Sessions and Reporting

- desktop sessions
- Telegram/WhatsApp session contracts
- task and execution state attached to sessions
- session source and state visible in the UI

### Task System

- task classes:
  - `device_support`
  - `developer_support`
  - `project_build`
  - `security_assessment`
  - `security_review`
  - `general_local_assistance`
- execution domains:
  - `local_device`
  - `local_dev`
  - `openclaw`
  - `wraith`
- task-level plan approval
- explicit privileged boundary approval
- execution timeline and approval history

### Executors

- `local_device_executor`
- `local_dev_executor`
- `openclaw_executor`
- `wraith_executor`

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

## Current Direction

The repo is moving toward a local-first operator hub where:

- Oxy is the main UI and reporting surface
- OpenClaw handles build and software execution work
- Wraith handles specialist security workflows
- device-level assistance remains a first-class local capability

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

```sh
npm run verify:frontend
npm run verify:rust
npm run verify:all
```

Current local note:

- `tsc && vite build` is passing
- backend import/startup is passing
- Jest has intermittently failed on this cloud-synced workspace with `ETIMEDOUT` reads from `node_modules`

## Source Of Truth

The repo should be resumed in this order:

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

## Current Boundaries

In scope now:

- orchestrator hardening
- executor integration contracts
- approval and reporting cohesion
- session-centric operator UX

Still deferred:

- live OpenClaw integration
- live Wraith integration
- real Telegram/WhatsApp provider wiring
- browser/API adapters
- plugin sandbox
- hardware/model routing
- autonomous multi-agent runtime

## Repo Rule

Extend the current repo. Do not redesign it.
