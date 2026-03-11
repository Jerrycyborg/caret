# macOS Release Checklist

## Goal

Ship a macOS desktop build that verifies locally, packages correctly, and is reviewed for platform-specific permissions and signing requirements.

## Verification

- [ ] `npm install` completes
- [ ] `npm run verify:frontend` passes
- [ ] `npm run verify:rust` passes
- [ ] `npx tauri build` completes on macOS

## Local Smoke Test

- [ ] App launches on target macOS version
- [ ] Backend launches locally
- [ ] Chat round-trip works
- [ ] Files, Terminal, and Resources panels open successfully
- [ ] Tool adapters are listed with health and capability metadata
- [ ] Reference CLI adapter executes and returns structured output
- [ ] Execution targets are shown in the Resources view
- [ ] Security panel behavior is reviewed under normal user permissions
- [ ] Security panel requires explicit approval before any mutation
- [ ] Approved privileged actions trigger a GUI-native administrator prompt
- [ ] Denied or canceled admin auth leaves system state unchanged
- [ ] Plugin install state persists across restart

## Release Controls

- [ ] Signing/notarization ownership is assigned
- [ ] Required app permissions are reviewed
- [ ] Packaging artifact is archived
- [ ] Known limitations are documented
