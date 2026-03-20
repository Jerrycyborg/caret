use crate::run_command;
use serde::{Deserialize, Serialize};
use tauri::command;

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ServiceAction {
    Start,
    Stop,
    Restart,
}

impl ServiceAction {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Start => "start",
            Self::Stop => "stop",
            Self::Restart => "restart",
        }
    }
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum PrivilegedActionRequest {
    Firewall { enabled: bool },
    Service { name: String, action: ServiceAction },
    UserLock { name: String, lock: bool },
    TerminateProcess { pid: u32 },
    FlushDns,
    ClearTeamsCache,
    ResetOneDrive,
    RestartAudioDevices,
    RunSystemRepair,
    CleanDisk,
}

#[derive(Clone, Serialize)]
pub struct PrivilegedActionPreview {
    pub action_type: String,
    pub action_label: String,
    pub target: String,
    pub reason: String,
    pub approval_required: bool,
    pub mutating: bool,
    pub platform: String,
    pub execution_path: String,
}

#[derive(Clone, Serialize)]
pub struct PrivilegedActionResult {
    pub status: String,
    pub action_type: String,
    pub action_label: String,
    pub target: String,
    pub message: String,
    pub details: Option<String>,
    pub approval_required: bool,
    pub mutating: bool,
}

struct PlannedPrivilegedCommand {
    program: String,
    args: Vec<String>,
    needs_elevation: bool,
}

fn is_safe_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.bytes().all(|byte| {
            matches!(byte, b'a'..=b'z' | b'A'..=b'Z' | b'0'..=b'9' | b'_' | b'-' | b'.' | b'@')
        })
}

fn ensure_safe_identifier(kind: &str, value: &str) -> Result<(), String> {
    if is_safe_identifier(value) {
        Ok(())
    } else {
        Err(format!(
            "Invalid {kind}. Only letters, numbers, ., -, _, and @ are allowed."
        ))
    }
}

fn preview_for_action(request: &PrivilegedActionRequest) -> PrivilegedActionPreview {
    match request {
        PrivilegedActionRequest::Firewall { enabled } => PrivilegedActionPreview {
            action_type: "firewall".to_string(),
            action_label: if *enabled {
                "Enable firewall".to_string()
            } else {
                "Disable firewall".to_string()
            },
            target: "system firewall".to_string(),
            reason: "Firewall configuration changes affect host-level network protection.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval + Windows UAC prompt".to_string(),
        },
        PrivilegedActionRequest::Service { name, action } => PrivilegedActionPreview {
            action_type: "service".to_string(),
            action_label: format!("{} service", action.as_str()),
            target: name.clone(),
            reason: "Service lifecycle changes modify running system processes and availability.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval + Windows UAC prompt".to_string(),
        },
        PrivilegedActionRequest::UserLock { name, lock } => PrivilegedActionPreview {
            action_type: "user_lock".to_string(),
            action_label: if *lock {
                "Lock user".to_string()
            } else {
                "Unlock user".to_string()
            },
            target: name.clone(),
            reason: "User account changes alter who can access the machine.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval + Windows UAC prompt".to_string(),
        },
        PrivilegedActionRequest::TerminateProcess { pid } => PrivilegedActionPreview {
            action_type: "terminate_process".to_string(),
            action_label: "Terminate process".to_string(),
            target: format!("PID {pid}"),
            reason: "Process termination interrupts a running system task or connection.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval + Windows UAC prompt".to_string(),
        },
        PrivilegedActionRequest::FlushDns => PrivilegedActionPreview {
            action_type: "flush_dns".to_string(),
            action_label: "Flush DNS cache".to_string(),
            target: "DNS resolver cache".to_string(),
            reason: "Clears stale DNS entries. Fixes Teams, browser, and VPN connectivity issues. Requires elevation.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval + Windows UAC prompt".to_string(),
        },
        PrivilegedActionRequest::ClearTeamsCache => PrivilegedActionPreview {
            action_type: "clear_teams_cache".to_string(),
            action_label: "Clear Teams cache".to_string(),
            target: "Microsoft Teams cache folders".to_string(),
            reason: "Kills Teams and deletes its local cache. Fixes call lag, login loops, and rendering issues. No elevation required.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval — runs as current user (no UAC)".to_string(),
        },
        PrivilegedActionRequest::ResetOneDrive => PrivilegedActionPreview {
            action_type: "reset_one_drive".to_string(),
            action_label: "Reset OneDrive sync".to_string(),
            target: "OneDrive process".to_string(),
            reason: "Kills OneDrive and restarts it with /reset. Fixes stuck sync, high CPU, and repeated sign-in prompts. No elevation required.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval — runs as current user (no UAC)".to_string(),
        },
        PrivilegedActionRequest::RestartAudioDevices => PrivilegedActionPreview {
            action_type: "restart_audio_devices".to_string(),
            action_label: "Restart audio devices".to_string(),
            target: "PnP audio and sound devices".to_string(),
            reason: "Disables then re-enables all audio/sound PnP devices. Fixes mic not working, no audio output, and device errors. Requires elevation.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval + Windows UAC prompt".to_string(),
        },
        PrivilegedActionRequest::CleanDisk => PrivilegedActionPreview {
            action_type: "clean_disk".to_string(),
            action_label: "Clean disk".to_string(),
            target: "User TEMP files and Recycle Bin".to_string(),
            reason: "Removes your TEMP folder contents and empties the Recycle Bin. No user documents are deleted. Runs as your current user — no admin required.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval — runs as current user (no UAC)".to_string(),
        },
        PrivilegedActionRequest::RunSystemRepair => PrivilegedActionPreview {
            action_type: "run_system_repair".to_string(),
            action_label: "Run DISM + SFC system repair".to_string(),
            target: "Windows component store + system files".to_string(),
            reason: "DISM /RestoreHealth repairs the Windows component store (downloads replacements from Windows Update), then SFC /scannow fixes corrupted system files. Fixes driver failures, service crashes, and NTFS errors. Requires internet. Takes 15–30 minutes — runs in a visible window you can monitor.".to_string(),
            approval_required: true,
            mutating: true,
            platform: "windows".to_string(),
            execution_path: "in-app approval + Windows UAC prompt (visible repair window)".to_string(),
        },
    }
}

fn plan_privileged_action(
    request: &PrivilegedActionRequest,
) -> Result<PlannedPrivilegedCommand, String> {
    match request {
        PrivilegedActionRequest::Firewall { enabled } => Ok(PlannedPrivilegedCommand {
            program: "netsh".to_string(),
            args: vec![
                "advfirewall".to_string(),
                "set".to_string(),
                "allprofiles".to_string(),
                "state".to_string(),
                if *enabled { "on" } else { "off" }.to_string(),
            ],
            needs_elevation: true,
        }),
        PrivilegedActionRequest::Service { name, action } => {
            ensure_safe_identifier("service name", name)?;
            let ps = match action {
                ServiceAction::Start => format!("Start-Service -Name '{name}'"),
                ServiceAction::Stop => format!("Stop-Service -Name '{name}'"),
                ServiceAction::Restart => format!("Restart-Service -Name '{name}'"),
            };
            Ok(PlannedPrivilegedCommand {
                program: "powershell".to_string(),
                args: vec!["-Command".to_string(), ps],
                needs_elevation: true,
            })
        }
        PrivilegedActionRequest::UserLock { name, lock } => {
            ensure_safe_identifier("user name", name)?;
            Ok(PlannedPrivilegedCommand {
                program: "net".to_string(),
                args: vec![
                    "user".to_string(),
                    name.clone(),
                    if *lock { "/active:no" } else { "/active:yes" }.to_string(),
                ],
                needs_elevation: true,
            })
        }
        PrivilegedActionRequest::TerminateProcess { pid } => Ok(PlannedPrivilegedCommand {
            program: "taskkill".to_string(),
            args: vec!["/PID".to_string(), pid.to_string(), "/F".to_string()],
            needs_elevation: true,
        }),
        PrivilegedActionRequest::FlushDns => Ok(PlannedPrivilegedCommand {
            program: "powershell".to_string(),
            args: vec![
                "-NoProfile".to_string(),
                "-NonInteractive".to_string(),
                "-WindowStyle".to_string(),
                "Hidden".to_string(),
                "-Command".to_string(),
                "ipconfig /flushdns; ipconfig /registerdns".to_string(),
            ],
            needs_elevation: true,
        }),
        PrivilegedActionRequest::ClearTeamsCache => Ok(PlannedPrivilegedCommand {
            program: "powershell".to_string(),
            args: vec![
                "-NoProfile".to_string(),
                "-NonInteractive".to_string(),
                "-WindowStyle".to_string(),
                "Hidden".to_string(),
                "-Command".to_string(),
                // Kill Teams; clear old classic Teams paths + new MSIX LocalCache tree
                [
                    "Get-Process -Name 'ms-teams','Teams' -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue;",
                    "Start-Sleep -Seconds 2;",
                    "$n = 0;",
                    // Old classic Teams subfolders
                    "foreach ($p in @(",
                    "  \"$env:APPDATA\\Microsoft\\Teams\\Cache\",",
                    "  \"$env:APPDATA\\Microsoft\\Teams\\blob_storage\",",
                    "  \"$env:APPDATA\\Microsoft\\Teams\\databases\",",
                    "  \"$env:APPDATA\\Microsoft\\Teams\\GPUCache\",",
                    "  \"$env:APPDATA\\Microsoft\\Teams\\IndexedDB\",",
                    "  \"$env:APPDATA\\Microsoft\\Teams\\Local Storage\",",
                    "  \"$env:APPDATA\\Microsoft\\Teams\\tmp\"",
                    ")) { if (Test-Path $p) { Remove-Item $p -Recurse -Force -EA SilentlyContinue; $n++ } };",
                    // New Teams (MSIX) — scan LocalCache and delete known cache folder names
                    "$newRoot = \"$env:LOCALAPPDATA\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\";",
                    "if (Test-Path $newRoot) {",
                    "  $cacheNames = @('Cache','GPUCache','blob_storage','databases','IndexedDB','tmp','Code Cache','DawnCache','ShaderCache','EBWebView');",
                    "  Get-ChildItem $newRoot -Recurse -Directory -EA SilentlyContinue |",
                    "    Where-Object { $cacheNames -contains $_.Name } |",
                    "    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -EA SilentlyContinue; $n++ };",
                    "  Get-ChildItem $newRoot -File -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue",
                    "};",
                    "\"Cleared $n Teams cache folders. Restart Teams to reconnect.\"",
                ].join(" "),
            ],
            needs_elevation: false,
        }),
        PrivilegedActionRequest::ResetOneDrive => Ok(PlannedPrivilegedCommand {
            program: "powershell".to_string(),
            args: vec![
                "-NoProfile".to_string(),
                "-NonInteractive".to_string(),
                "-WindowStyle".to_string(),
                "Hidden".to_string(),
                "-Command".to_string(),
                concat!(
                    "Get-Process -Name 'OneDrive' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; ",
                    "Start-Sleep -Seconds 3; ",
                    "$od = \"$env:LOCALAPPDATA\\Microsoft\\OneDrive\\OneDrive.exe\"; ",
                    "if(Test-Path $od){ Start-Process $od -ArgumentList '/reset'; \"OneDrive reset initiated. It will restart and re-sync automatically.\" } ",
                    "else { \"OneDrive not found at expected path.\" }"
                ).to_string(),
            ],
            needs_elevation: false,
        }),
        PrivilegedActionRequest::RunSystemRepair => Ok(PlannedPrivilegedCommand {
            // Launched in a visible PowerShell window so user can monitor progress.
            // Does NOT use -Wait or -WindowStyle Hidden — handled by execute_visible_elevated.
            program: "powershell".to_string(),
            args: vec![
                "-NoProfile".to_string(),
                "-Command".to_string(),
                concat!(
                    "Write-Host 'Step 1/2: Running DISM /RestoreHealth (downloads from Windows Update)...' -ForegroundColor Cyan; ",
                    "DISM /Online /Cleanup-Image /RestoreHealth; ",
                    "Write-Host ''; ",
                    "Write-Host 'Step 2/2: Running SFC /scannow...' -ForegroundColor Cyan; ",
                    "sfc /scannow; ",
                    "Write-Host ''; ",
                    "Write-Host 'Repair complete. A reboot is recommended.' -ForegroundColor Green; ",
                    "Read-Host 'Press Enter to close'"
                ).to_string(),
            ],
            needs_elevation: true,
        }),
        PrivilegedActionRequest::CleanDisk => Ok(PlannedPrivilegedCommand {
            program: "powershell".to_string(),
            args: vec![
                "-NoProfile".to_string(),
                "-NonInteractive".to_string(),
                "-WindowStyle".to_string(),
                "Hidden".to_string(),
                "-Command".to_string(),
                concat!(
                    "$freed = 0; ",
                    "try { $freed += (Get-ChildItem $env:TEMP -Recurse -Force -EA SilentlyContinue | Measure-Object -Property Length -Sum).Sum; ",
                    "  Remove-Item \"$env:TEMP\\*\" -Recurse -Force -EA SilentlyContinue } catch {}; ",
                    "try { Clear-RecycleBin -Force -EA SilentlyContinue } catch {}; ",
                    "$mb = [math]::Round($freed / 1MB, 1); \"Cleaned ${mb} MB of temporary files and emptied Recycle Bin.\""
                ).to_string(),
            ],
            needs_elevation: false,
        }),
        PrivilegedActionRequest::RestartAudioDevices => Ok(PlannedPrivilegedCommand {
            program: "powershell".to_string(),
            args: vec![
                "-NoProfile".to_string(),
                "-NonInteractive".to_string(),
                "-WindowStyle".to_string(),
                "Hidden".to_string(),
                "-Command".to_string(),
                concat!(
                    "$d = Get-PnpDevice | Where-Object { $_.Class -in @(\"AudioEndpoint\",\"Media\",\"SoundSystem\") }; ",
                    "$n=0; foreach($dev in $d){ ",
                        "Disable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false -ErrorAction SilentlyContinue; ",
                        "Start-Sleep -Milliseconds 500; ",
                        "Enable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false -ErrorAction SilentlyContinue; ",
                        "$n++ }; ",
                    "\"Restarted $n audio device(s). Test your mic and speakers.\""
                ).to_string(),
            ],
            needs_elevation: true,
        }),
    }
}

fn escape_powershell_single_quoted(input: &str) -> String {
    input.replace('\'', "''")
}

fn classify_privileged_error(error: &str) -> &'static str {
    let lower = error.to_lowercase();
    if lower.contains("user canceled")
        || lower.contains("cancelled")
        || lower.contains("canceled")
    {
        "denied"
    } else if lower.contains("permission denied")
        || lower.contains("not permitted")
        || lower.contains("access is denied")
        || lower.contains("requires administrator")
        || lower.contains("interactive authentication required")
        || lower.contains("requested operation requires elevation")
    {
        "insufficient_privileges"
    } else if lower.contains("invalid ") {
        "invalid_target"
    } else if lower.contains("not supported") {
        "unsupported_platform"
    } else {
        "execution_failed"
    }
}

/// Launches the command with UAC elevation in a VISIBLE terminal window without waiting.
/// Used for long-running tasks (DISM) where blocking the UI is not acceptable.
fn execute_visible_elevated(command: PlannedPrivilegedCommand) -> Result<String, String> {
    let script = format!(
        "Start-Process -FilePath '{}' -ArgumentList @({}) -Verb RunAs",
        escape_powershell_single_quoted(&command.program),
        command
            .args
            .iter()
            .map(|arg| format!("'{}'", escape_powershell_single_quoted(arg)))
            .collect::<Vec<_>>()
            .join(", ")
    );
    run_command("powershell", ["-NoProfile", "-Command", script.as_str()])?;
    Ok("Repair launched in a separate window. Monitor progress there. Reboot when it completes.".to_string())
}

fn execute_with_platform_auth(command: PlannedPrivilegedCommand) -> Result<String, String> {
    let script = format!(
        "$p = Start-Process -FilePath '{}' -ArgumentList @({}) -Verb RunAs -WindowStyle Hidden -Wait -PassThru; Write-Output $p.ExitCode",
        escape_powershell_single_quoted(&command.program),
        command
            .args
            .iter()
            .map(|arg| format!("'{}'", escape_powershell_single_quoted(arg)))
            .collect::<Vec<_>>()
            .join(", ")
    );
    let result = run_command("powershell", ["-NoProfile", "-Command", script.as_str()])?;
    let exit_code = result
        .lines()
        .last()
        .unwrap_or_default()
        .trim()
        .parse::<i32>()
        .map_err(|_| format!("Unexpected Windows elevation result: {result}"))?;
    if exit_code == 0 {
        Ok("OK".to_string())
    } else {
        Err(format!("Privileged Windows action exited with code {exit_code}"))
    }
}

#[command]
pub fn preview_privileged_action(request: PrivilegedActionRequest) -> PrivilegedActionPreview {
    preview_for_action(&request)
}

#[command]
pub fn execute_privileged_action(
    request: PrivilegedActionRequest,
    approved: bool,
) -> PrivilegedActionResult {
    let preview = preview_for_action(&request);
    if !approved {
        return PrivilegedActionResult {
            status: "denied".to_string(),
            action_type: preview.action_type,
            action_label: preview.action_label,
            target: preview.target,
            message: "Action canceled before execution.".to_string(),
            details: None,
            approval_required: true,
            mutating: true,
        };
    }

    let planned = match plan_privileged_action(&request) {
        Ok(planned) => planned,
        Err(error) => {
            return PrivilegedActionResult {
                status: classify_privileged_error(&error).to_string(),
                action_type: preview.action_type,
                action_label: preview.action_label,
                target: preview.target,
                message: "Sensitive OS action failed safely.".to_string(),
                details: Some(error),
                approval_required: true,
                mutating: true,
            }
        }
    };

    let exec_result = match &request {
        PrivilegedActionRequest::RunSystemRepair => execute_visible_elevated(planned),
        _ if planned.needs_elevation => execute_with_platform_auth(planned),
        _ => run_command(&planned.program.clone(), planned.args.clone()),
    };
    match exec_result {
        Ok(message) => PrivilegedActionResult {
            status: "executed".to_string(),
            action_type: preview.action_type,
            action_label: preview.action_label,
            target: preview.target,
            message: "Sensitive OS action executed through the platform privilege runner.".to_string(),
            details: Some(message),
            approval_required: true,
            mutating: true,
        },
        Err(error) => PrivilegedActionResult {
            status: classify_privileged_error(&error).to_string(),
            action_type: preview.action_type,
            action_label: preview.action_label,
            target: preview.target,
            message: "Sensitive OS action failed safely.".to_string(),
            details: Some(error),
            approval_required: true,
            mutating: true,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{plan_privileged_action, preview_privileged_action, PrivilegedActionRequest, ServiceAction};

    #[test]
    fn preview_contains_execution_path() {
        let preview = preview_privileged_action(PrivilegedActionRequest::Firewall { enabled: true });
        assert!(preview.approval_required);
        assert!(!preview.execution_path.is_empty());
    }

    #[test]
    fn invalid_service_name_is_rejected() {
        let plan = plan_privileged_action(&PrivilegedActionRequest::Service {
            name: "bad;name".to_string(),
            action: ServiceAction::Start,
        });
        assert!(plan.is_err());
    }
}
