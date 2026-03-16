# Windows Release Checklist

## Goal

Ship a Windows desktop build that verifies on Windows, handles local support monitoring correctly, and uses a safe UAC-backed path for privileged actions.

## CI Requirements

- [ ] Windows workflow completes `npm install`
- [ ] `npm run verify:frontend` passes on Windows
- [ ] `npm run verify:rust` passes on Windows
- [ ] `build/ci/verify-security.sh` passes on Windows

## Local Validation

- [ ] `build/windows/install-from-git.ps1` installs prerequisites or fails clearly
- [ ] `build/windows/install-from-git.ps1` builds an MSI and installs Caret locally
- [ ] installed Caret launches after bootstrap
- [ ] packaged Caret launches its bundled backend automatically
- [ ] packaged Caret works without Python installed on the target machine
- [ ] App launches on supported Windows version
- [ ] Backend launches locally
- [ ] Chat round-trip works
- [ ] Support lane renders incident queues and detail correctly
- [ ] Windows support monitoring reads CPU, memory, process, and cleanup targets correctly
- [ ] support remains the primary visible lane for incidents and auto-fix
- [ ] Security panel read-only commands return usable data
- [ ] Approved privileged actions trigger a Windows UAC prompt
- [ ] Denied or canceled UAC auth leaves system state unchanged
- [ ] linked IT ticket creation still reports back into Caret

## Release Notes

- [ ] Target Windows version is recorded
- [ ] GitHub Release includes MSI + setup EXE + checksum file
- [ ] Installer artifact is archived
- [ ] Known Windows limitations are documented
