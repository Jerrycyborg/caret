#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if rg -n "shell:allow-execute|shell:allow-open" src-tauri/capabilities/default.json >/dev/null 2>&1; then
  echo "Security check failed: Tauri shell capability is still enabled."
  exit 1
fi

if rg -n "tauri_plugin_shell::init|tauri-plugin-shell" src-tauri/src src-tauri/Cargo.toml >/dev/null 2>&1; then
  echo "Security check failed: Tauri shell plugin is still wired into the desktop runtime."
  exit 1
fi

if rg -n "sh -c" backend src-tauri/src >/dev/null 2>&1; then
  echo "Security check failed: shell interpolation detected."
  exit 1
fi

if rg -n "INSERT INTO api_keys|SELECT provider, key_value FROM api_keys" backend >/dev/null 2>&1; then
  echo "Security check failed: provider secrets are still being persisted or reloaded from SQLite."
  exit 1
fi

echo "Security verification passed."
