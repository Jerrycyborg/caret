# Windows Release Checklist

## Goal

Ship a Windows desktop build that verifies on Windows, handles local support monitoring correctly, and uses a safe UAC-backed path for privileged actions.

## CI Requirements

- [ ] Windows workflow completes `npm install`
- [ ] `npm run verify:frontend` passes on Windows
- [ ] `npm run verify:rust` passes on Windows
- [ ] `build/ci/verify-security.sh` passes on Windows

## Local Validation

- [ ] App launches on supported Windows version
- [ ] Backend launches locally
- [ ] Chat round-trip works
- [ ] Support lane renders incident queues and detail correctly
- [ ] Windows support monitoring reads CPU, memory, process, and cleanup targets correctly
- [ ] Workflows remain separate from support incidents
- [ ] Security panel read-only commands return usable data
- [ ] Approved privileged actions trigger a Windows UAC prompt
- [ ] Denied or canceled UAC auth leaves system state unchanged
- [ ] Linked IT ticket creation still reports back into Oxy

## Release Notes

- [ ] Target Windows version is recorded
- [ ] Installer artifact is archived
- [ ] Known Windows limitations are documented
