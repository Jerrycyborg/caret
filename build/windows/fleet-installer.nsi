; Caret Fleet Installer
; Wraps the Caret NSIS installer and injects org config as system env vars.
;
; Usage (build with makensis):
;   makensis /DMANAGEMENT_URL="https://caret.tws-partners.com/admin" ^
;            /DMANAGEMENT_TOKEN="your-secret-token" ^
;            /DADMIN_GROUP="ROL-ADM-Admins" ^
;            /DORG_NAME="TWS Partners AG" ^
;            fleet-installer.nsi
;
; Or use build-fleet-installer.ps1 which sets all params interactively.

!define PRODUCT_NAME "Caret"
!define INSTALLER_EXE "..\..\..\dist\Caret_0.1.9_x64-setup.exe"

; === Overridable via /D flags ===
!ifndef MANAGEMENT_URL
  !define MANAGEMENT_URL ""
!endif
!ifndef MANAGEMENT_TOKEN
  !define MANAGEMENT_TOKEN ""
!endif
!ifndef ADMIN_GROUP
  !define ADMIN_GROUP ""
!endif
!ifndef ORG_NAME
  !define ORG_NAME ""
!endif
!ifndef ENV_LABEL
  !define ENV_LABEL ""
!endif
!ifndef JIRA_PROJECT_KEY
  !define JIRA_PROJECT_KEY ""
!endif

Name "${PRODUCT_NAME} Fleet Installer"
OutFile "Caret-Fleet-Setup.exe"
RequestExecutionLevel admin
SilentInstall silent

!include "LogicLib.nsh"

Section "Install"
  ; Run the base Caret installer silently
  SetOutPath "$TEMP"
  File "${INSTALLER_EXE}"
  ExecWait '"$TEMP\Caret_0.1.9_x64-setup.exe" /S'
  Delete "$TEMP\Caret_0.1.9_x64-setup.exe"

  ; Write system-wide environment variables (HKLM — all users)
  !macro SetSysEnv key value
    ${If} "${value}" != ""
      WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "${key}" "${value}"
    !endif
  !macroend

  !insertmacro SetSysEnv "CARET_MANAGEMENT_SERVER_URL" "${MANAGEMENT_URL}"
  !insertmacro SetSysEnv "CARET_MANAGEMENT_TOKEN"      "${MANAGEMENT_TOKEN}"
  !insertmacro SetSysEnv "CARET_ADMIN_GROUP"           "${ADMIN_GROUP}"
  !insertmacro SetSysEnv "CARET_ORG_NAME"              "${ORG_NAME}"
  !insertmacro SetSysEnv "CARET_ENV_LABEL"             "${ENV_LABEL}"
  !insertmacro SetSysEnv "CARET_JIRA_PROJECT_KEY"      "${JIRA_PROJECT_KEY}"

  ; Broadcast environment change so running processes pick it up
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=500

  ; Auto-start Caret for current user
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Caret" \
    "$LOCALAPPDATA\Caret\Caret.exe"
SectionEnd
