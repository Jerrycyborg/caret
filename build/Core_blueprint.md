# Oxy Core Blueprint

## Source Role

This is the top product document for the repo.

Use the source-of-truth order:

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

## Product Direction

Oxy is a supervised local orchestration kernel for macOS and Ubuntu.

It is:

- a local-first device and developer assistant
- the main reporting surface for connected executor systems
- the control layer above OpenClaw and Wraith

Target behavior:

- plan
- ask
- execute
- observe
- suggest next move

Oxy is not just chat, not an unrestricted autonomous agent, and not yet a multi-agent system.

## Core System Shape

### Frontend

Owns:

- chat
- session switching
- tasks
- approvals
- execution timeline
- system panels

### Backend

Owns:

- conversation context
- multi-channel session routing
- session/task orchestration
- execution-domain routing
- task and step state machine
- task-level approval policy with privileged boundaries
- tool registry and safe local adapters

### Rust/Tauri

Owns:

- system inspection
- privileged OS actions
- platform-native security and machine control

Rule:

- backend tools handle local repo and workflow tasks
- privileged OS mutations stay in Rust only

## Current Milestone Track

### Milestone 1

Viable Oxy kernel:

- backend session/task orchestrator
- task + step state model
- approvals, executions, policy events
- SQLite persistence
- task list, approval panel, timeline

### Milestone 2

Local adapter layer:

- tool registry
- file read/write
- git status/diff
- git log/show
- project tree/read-many/search
- bounded shell/build execution

### Milestone 3

Local hub + external executor alignment:

- multi-channel sessions
- task classes and execution domains
- task-level approval with privileged boundaries
- executor adapters for:
  - local device support
  - local developer support
  - OpenClaw
  - Wraith
- desktop as the main reporting console

### Deferred

- browser/API adapters
- plugin sandbox and plugin manifest
- hardware/model routing
- autonomous multi-agent orchestration beyond supervised agent roles

## Operating Rules

- extend the current repo, do not redesign it
- prefer small additive backend services and routes
- keep chat usable without requiring task creation
- use task-level approval by default for mutating plans
- use explicit boundary approval for privileged local actions
- keep docs compact and update only the tracked source-of-truth files
