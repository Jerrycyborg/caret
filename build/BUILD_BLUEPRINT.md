# Oxy Build Blueprint

## Why This Build Exists

Based on the current project checkpoint and repository docs, Oxy exists to become a deeply OS-integrated AI desktop assistant, not just a chat shell.

This is the intended product direction:

- Use local OS capabilities directly from a desktop app.
- Combine a desktop shell, Python AI backend, and local system tooling into one operator surface.
- Grow toward plugins, hardware-aware execution, and multi-agent workflows.
- Ship first on macOS and Ubuntu with a release process that is repeatable and supportable.

This statement is an explicit build assumption derived from `AAHP.md` and `README.md`, so the repo has a documented build purpose instead of implied context.

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
- hard approval boundaries for sensitive system mutations
- adapter-first integration for a few critical tools, not broad shallow coverage
- hardware-aware detect-and-route execution, not deep vendor-specific optimization

### In Scope for V1

- chat and backend orchestration
- system inspection and resource awareness
- execution target detection for CPU/GPU/NPU-style routing signals
- plugin and tool adapter foundation
- a small number of critical tool-adapter contracts
- privileged OS actions with explicit approval:
  - firewall enable/disable
  - service start/stop/restart
  - user lock/unlock
  - process termination

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
- `build/BUILD_BLUEPRINT.md`

## Acceptance Gates

### Gate A: Code Health

- [ ] `npm install`
- [ ] `npm run verify:frontend`
- [ ] `npm run verify:rust`

### Gate B: App Viability

- [ ] Backend starts with `npm run backend`
- [ ] Desktop app starts with `npm run tauri dev`
- [ ] Chat works against the backend
- [ ] Plugin flows use the compiled Rust plugin module
- [ ] Tool adapters are visible through a common registry/contract
- [ ] Execution targets are visible through a common resource model
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

The repo is improving, but these are still real release risks:

- privileged OS actions do not yet have a production privilege/elevation model
- plugin and tool adapter distribution are still internal/demo level
- end-to-end smoke coverage is still thin
- packaging/signing ownership is not yet encoded in the repo

## Operating Rule

If a build or verification step is added, it should live under `build/` unless the underlying tool requires a fixed path.
