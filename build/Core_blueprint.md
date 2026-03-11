# Oxy Core Blueprint

## Source Role

This is the top product document for the repo.

Use the source-of-truth order:

1. `build/Core_blueprint.md`
2. `build/BUILD_BLUEPRINT.md`
3. `AAHP.md`

## Product Direction

Oxy is a supervised local orchestration kernel for macOS and Ubuntu.

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
- tasks
- approvals
- execution timeline
- system panels

### Backend

Owns:

- conversation context
- session/task orchestration
- task and step state machine
- approval-first execution policy
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

### Deferred

- browser/API adapters
- plugin sandbox and plugin manifest
- hardware/model routing
- multi-agent orchestration

## Operating Rules

- extend the current repo, do not redesign it
- prefer small additive backend services and routes
- keep chat usable without requiring task creation
- require approval before backend writes
- keep docs compact and update only the tracked source-of-truth files
