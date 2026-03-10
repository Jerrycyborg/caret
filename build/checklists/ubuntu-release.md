# Ubuntu Release Checklist

## Goal

Ship a Linux build that is reproducible in CI and manually smoke-tested before release.

## CI Requirements

- [ ] Ubuntu workflow installs native Tauri/Linux build dependencies
- [ ] `npm install` completes
- [ ] `npm run verify:frontend` passes
- [ ] `npm run verify:rust` passes
- [ ] `npx tauri build` completes on Ubuntu

## Local Validation

- [ ] App launches on supported Ubuntu version
- [ ] Backend launches locally
- [ ] Chat round-trip works
- [ ] Files, Terminal, and Resources panels open successfully
- [ ] Tool adapters are listed with health and capability metadata
- [ ] Execution targets are shown in the Resources view
- [ ] Security panel fails safely when privileges are unavailable
- [ ] Security panel requires explicit approval before any mutation
- [ ] Plugin install state persists across restart

## Release Notes

- [ ] Target Ubuntu version is recorded
- [ ] Packaging artifacts are archived
- [ ] Known limitations are documented
