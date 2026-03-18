# Caret — Claude Code Instructions

## Resume Chain (read in order)
1. `build/Core_blueprint.md` — product mission, identity, guardrails
2. `build/BUILD_BLUEPRINT.md` — build contract, packaging rules, platform constraints
3. `AAHP.md` — current state, session notes, next priorities

Also:
- `build/checklists/smoke-test.md` — smoke test after every build
- `CHANGELOG.md` — update after every meaningful change

## Critical Architecture Rules (from BUILD_BLUEPRINT.md)
- **Windows only** — no `#[cfg(target_os = ...)]` platform guards in Rust. Use Windows APIs directly.
- Tauri shell stays thin — WebView2 + IPC only
- Rust owns privileged local actions (UAC, netsh, taskkill, services)
- Python sidecar owns AI, storage, monitoring, Jira, network calls
- Backend is loopback-only (`localhost:8000`)
- Settings are admin-gated — non-admins never see configuration

## Build Commands

### Full package (Rust + Frontend → MSI + NSIS, ~10 min first run)
```powershell
$env:CARGO_TARGET_DIR = 'C:\Users\lawrencem\cargo-targets\caret'
npm run windows:package
```
**CRITICAL**: Always set `CARGO_TARGET_DIR` outside OneDrive — OneDrive sync locks files mid-compile.

### Backend sidecar only (Python → EXE, ~2 min)
```powershell
.\build\windows\build-backend.ps1
```
Outputs to `C:\Users\lawrencem\caret-pyinstaller\dist\caret-backend.exe`, then copies to `src-tauri/resources/windows/`.

### Install after build — USE NSIS, NOT MSI
```powershell
# Kill running app first
Stop-Process -Name 'caret' -ErrorAction SilentlyContinue
Stop-Process -Name 'caret-backend' -ErrorAction SilentlyContinue
# Install (NSIS handles same-version reinstall correctly; MSI silently skips it)
Start-Process 'C:\Users\lawrencem\cargo-targets\caret\release\bundle\nsis\Caret_0.1.9_x64-setup.exe' -ArgumentList '/S' -Wait
# Clear WebView cache if frontend changes don't appear
Remove-Item 'C:\Users\lawrencem\AppData\Local\com.tws.caret\EBWebView\Default\Cache' -Recurse -Force -ErrorAction SilentlyContinue
# Launch
Start-Process 'C:\Users\lawrencem\AppData\Local\Caret\Caret.exe'
```

## Known Issues & Fixes Applied

| Issue | Root Cause | Fix |
|---|---|---|
| CMD windows flashing | `Command::new()` creates visible console per process | `CREATE_NO_WINDOW (0x08000000)` on all Rust `Command` calls |
| Backend crash on startup | litellm data files missing from PyInstaller bundle | `--collect-submodules litellm --collect-data litellm` in build-backend.ps1 |
| Rust build fails | OneDrive locks `src-tauri/target/` | `CARGO_TARGET_DIR=C:\Users\lawrencem\cargo-targets\caret` |
| PyInstaller build fails | OneDrive locks `build/windows/pyinstaller-build/` | workpath/distpath → `C:\Users\lawrencem\caret-pyinstaller\` |
| MSI reinstall is silent no-op | MSIEXEC skips same-version | Use NSIS `/S` instead |
| Frontend changes not visible | WebView2 cache | Clear `EBWebView\Default\Cache` |

## Environment (this dev machine)
- Python: `C:\Program Files\Python313`
- litellm: `C:\Users\lawrencem\AppData\Roaming\Python\Python313\site-packages\litellm`
- Cargo target: `C:\Users\lawrencem\cargo-targets\caret`
- PyInstaller output: `C:\Users\lawrencem\caret-pyinstaller\`
- Install location: `C:\Users\lawrencem\AppData\Local\Caret\`
