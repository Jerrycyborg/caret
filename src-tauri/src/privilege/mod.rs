use serde::{Deserialize, Serialize};
use std::ffi::OsStr;
use std::process::Command;
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
}

fn run_command<I, S>(program: &str, args: I) -> Result<String, String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let output = Command::new(program)
        .args(args)
        .output()
        .map_err(|e| format!("Failed to run {program}: {e}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if output.status.success() {
        if stdout.is_empty() {
            Ok("OK".to_string())
        } else {
            Ok(stdout)
        }
    } else if !stderr.is_empty() {
        Err(stderr)
    } else if !stdout.is_empty() {
        Err(stdout)
    } else {
        Err(format!("{program} exited with status {}", output.status))
    }
}

fn current_platform() -> String {
    if cfg!(target_os = "macos") {
        "macos".to_string()
    } else if cfg!(target_os = "linux") {
        "ubuntu".to_string()
    } else if cfg!(target_os = "windows") {
        "windows".to_string()
    } else {
        "unsupported".to_string()
    }
}

fn execution_path_label() -> String {
    if cfg!(target_os = "macos") {
        "in-app approval + macOS administrator prompt".to_string()
    } else if cfg!(target_os = "linux") {
        "in-app approval + sudo".to_string()
    } else {
        "unsupported platform".to_string()
    }
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
            platform: current_platform(),
            execution_path: execution_path_label(),
        },
        PrivilegedActionRequest::Service { name, action } => PrivilegedActionPreview {
            action_type: "service".to_string(),
            action_label: format!("{} service", action.as_str()),
            target: name.clone(),
            reason: "Service lifecycle changes modify running system processes and availability.".to_string(),
            approval_required: true,
            mutating: true,
            platform: current_platform(),
            execution_path: execution_path_label(),
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
            platform: current_platform(),
            execution_path: execution_path_label(),
        },
        PrivilegedActionRequest::TerminateProcess { pid } => PrivilegedActionPreview {
            action_type: "terminate_process".to_string(),
            action_label: "Terminate process".to_string(),
            target: format!("PID {pid}"),
            reason: "Process termination interrupts a running system task or connection.".to_string(),
            approval_required: true,
            mutating: true,
            platform: current_platform(),
            execution_path: execution_path_label(),
        },
    }
}

fn plan_privileged_action(
    request: &PrivilegedActionRequest,
) -> Result<PlannedPrivilegedCommand, String> {
    match request {
        PrivilegedActionRequest::Firewall { enabled } => {
            #[cfg(target_os = "macos")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "/sbin/pfctl".to_string(),
                    args: vec![if *enabled { "-e" } else { "-d" }.to_string()],
                });
            }
            #[cfg(target_os = "linux")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "ufw".to_string(),
                    args: vec![if *enabled { "enable" } else { "disable" }.to_string()],
                });
            }
            #[cfg(target_os = "windows")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "netsh".to_string(),
                    args: vec![
                        "advfirewall".to_string(),
                        "set".to_string(),
                        "allprofiles".to_string(),
                        "state".to_string(),
                        if *enabled { "on" } else { "off" }.to_string(),
                    ],
                });
            }
        }
        PrivilegedActionRequest::Service { name, action } => {
            ensure_safe_identifier("service name", name)?;
            #[cfg(target_os = "macos")]
            {
                let target = format!("system/{name}");
                let args = match action {
                    ServiceAction::Start | ServiceAction::Restart => {
                        vec!["kickstart".to_string(), "-k".to_string(), target]
                    }
                    ServiceAction::Stop => {
                        vec!["kill".to_string(), "TERM".to_string(), target]
                    }
                };
                return Ok(PlannedPrivilegedCommand {
                    program: "launchctl".to_string(),
                    args,
                });
            }
            #[cfg(target_os = "linux")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "systemctl".to_string(),
                    args: vec![action.as_str().to_string(), name.clone()],
                });
            }
            #[cfg(target_os = "windows")]
            {
                let ps = match action {
                    ServiceAction::Start => format!("Start-Service -Name '{name}'"),
                    ServiceAction::Stop => format!("Stop-Service -Name '{name}'"),
                    ServiceAction::Restart => format!("Restart-Service -Name '{name}'"),
                };
                return Ok(PlannedPrivilegedCommand {
                    program: "powershell".to_string(),
                    args: vec!["-Command".to_string(), ps],
                });
            }
        }
        PrivilegedActionRequest::UserLock { name, lock } => {
            ensure_safe_identifier("user name", name)?;
            #[cfg(target_os = "macos")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "pwpolicy".to_string(),
                    args: vec![
                        "-u".to_string(),
                        name.clone(),
                        "-setpolicy".to_string(),
                        if *lock {
                            "isDisabled=1"
                        } else {
                            "isDisabled=0"
                        }
                        .to_string(),
                    ],
                });
            }
            #[cfg(target_os = "linux")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "usermod".to_string(),
                    args: vec![if *lock { "-L" } else { "-U" }.to_string(), name.clone()],
                });
            }
            #[cfg(target_os = "windows")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "net".to_string(),
                    args: vec![
                        "user".to_string(),
                        name.clone(),
                        if *lock { "/active:no" } else { "/active:yes" }.to_string(),
                    ],
                });
            }
        }
        PrivilegedActionRequest::TerminateProcess { pid } => {
            #[cfg(any(target_os = "macos", target_os = "linux"))]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "kill".to_string(),
                    args: vec!["-9".to_string(), pid.to_string()],
                });
            }
            #[cfg(target_os = "windows")]
            {
                return Ok(PlannedPrivilegedCommand {
                    program: "taskkill".to_string(),
                    args: vec!["/PID".to_string(), pid.to_string(), "/F".to_string()],
                    execution_path,
                });
            }
        }
    }

    #[allow(unreachable_code)]
    Err("Sensitive OS action is not supported on this platform.".to_string())
}

fn shell_escape(arg: &str) -> String {
    if arg.is_empty() {
        "''".to_string()
    } else {
        format!("'{}'", arg.replace('\'', "'\"'\"'"))
    }
}

fn escape_applescript_string(input: &str) -> String {
    input.replace('\\', "\\\\").replace('"', "\\\"")
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
        || lower.contains("a password is required")
        || lower.contains("sudo:")
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

fn execute_with_platform_auth(command: PlannedPrivilegedCommand) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    {
        let shell_command = std::iter::once(shell_escape(&command.program))
            .chain(command.args.iter().map(|arg| shell_escape(arg)))
            .collect::<Vec<_>>()
            .join(" ");
        let script = format!(
            "do shell script \"{}\" with administrator privileges",
            escape_applescript_string(&shell_command)
        );
        return run_command("osascript", ["-e", script.as_str()]);
    }

    #[cfg(target_os = "linux")]
    {
        return run_command(
            "sudo",
            std::iter::once("--")
                .chain(std::iter::once(command.program.as_str()))
                .chain(command.args.iter().map(|arg| arg.as_str())),
        );
    }

    #[cfg(target_os = "windows")]
    {
        let _ = command;
        return Err("Sensitive OS action is not supported on this platform.".to_string());
    }

    #[allow(unreachable_code)]
    Err("Sensitive OS action is not supported on this platform.".to_string())
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

    match execute_with_platform_auth(planned) {
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
