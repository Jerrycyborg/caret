pub mod plugins;
mod tools;
use plugins::oxy_plugin::{discover_plugins, install_plugin, list_plugins, run_plugin, toggle_plugin_enabled};
use serde::{Deserialize, Serialize};
use std::ffi::OsStr;
use std::process::Command;
use tools::list_tool_adapters;

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

fn is_safe_identifier(value: &str) -> bool {
    !value.is_empty()
        && value
            .bytes()
            .all(|byte| matches!(byte, b'a'..=b'z' | b'A'..=b'Z' | b'0'..=b'9' | b'_' | b'-' | b'.' | b'@'))
}

fn ensure_safe_identifier(kind: &str, value: &str) -> Result<(), String> {
    if is_safe_identifier(value) {
        Ok(())
    } else {
        Err(format!("Invalid {kind}. Only letters, numbers, ., -, _, and @ are allowed."))
    }
}

fn command_exists(program: &str) -> bool {
    Command::new(program).arg("--version").output().is_ok()
}

#[derive(Clone, Serialize)]
pub struct ExecutionTargetInfo {
    pub id: String,
    pub label: String,
    pub available: bool,
    pub reason: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
enum ServiceAction {
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

#[derive(Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum PrivilegedActionRequest {
    Firewall { enabled: bool },
    Service { name: String, action: ServiceAction },
    UserLock { name: String, lock: bool },
    TerminateProcess { pid: u32 },
}

#[derive(Clone, Serialize)]
struct PrivilegedActionPreview {
    action_type: String,
    action_label: String,
    target: String,
    reason: String,
    approval_required: bool,
    mutating: bool,
    platform: String,
}

#[derive(Clone, Serialize)]
struct PrivilegedActionResult {
    status: String,
    action_type: String,
    action_label: String,
    target: String,
    message: String,
    details: Option<String>,
    approval_required: bool,
    mutating: bool,
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
        },
        PrivilegedActionRequest::Service { name, action } => PrivilegedActionPreview {
            action_type: "service".to_string(),
            action_label: format!("{} service", action.as_str()),
            target: name.clone(),
            reason: "Service lifecycle changes modify running system processes and availability.".to_string(),
            approval_required: true,
            mutating: true,
            platform: current_platform(),
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
        },
        PrivilegedActionRequest::TerminateProcess { pid } => PrivilegedActionPreview {
            action_type: "terminate_process".to_string(),
            action_label: "Terminate process".to_string(),
            target: format!("PID {pid}"),
            reason: "Process termination interrupts a running system task or connection.".to_string(),
            approval_required: true,
            mutating: true,
            platform: current_platform(),
        },
    }
}

fn classify_privileged_error(error: &str) -> &'static str {
    let lower = error.to_lowercase();
    if lower.contains("permission denied")
        || lower.contains("not permitted")
        || lower.contains("access is denied")
        || lower.contains("requires administrator")
        || lower.contains("interactive authentication required")
    {
        "insufficient_privileges"
    } else if lower.contains("invalid ") || lower.contains("unknown plugin") {
        "invalid_target"
    } else if lower.contains("not supported") {
        "unsupported_platform"
    } else {
        "execution_failed"
    }
}

fn set_firewall_enabled(enabled: bool) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    return run_command("/sbin/pfctl", if enabled { vec!["-e"] } else { vec!["-d"] });
    #[cfg(target_os = "linux")]
    return run_command("ufw", if enabled { vec!["enable"] } else { vec!["disable"] });
    #[cfg(target_os = "windows")]
    return run_command(
        "netsh",
        if enabled {
            vec!["advfirewall", "set", "allprofiles", "state", "on"]
        } else {
            vec!["advfirewall", "set", "allprofiles", "state", "off"]
        },
    );

    #[allow(unreachable_code)]
    Err("Firewall control is not supported on this platform.".to_string())
}

fn control_service(name: String, action: ServiceAction) -> Result<String, String> {
    ensure_safe_identifier("service name", &name)?;

    #[cfg(target_os = "macos")]
    {
        let target = format!("system/{name}");
        return match action {
            ServiceAction::Start | ServiceAction::Restart => {
                run_command("launchctl", ["kickstart", "-k", target.as_str()])
            }
            ServiceAction::Stop => run_command("launchctl", ["kill", "TERM", target.as_str()]),
        };
    }
    #[cfg(target_os = "linux")]
    {
        return run_command("systemctl", [action.as_str(), name.as_str()]);
    }
    #[cfg(target_os = "windows")]
    {
        return match action {
            ServiceAction::Start => run_command(
                "powershell",
                ["-Command", &format!("Start-Service -Name '{}'", name)],
            ),
            ServiceAction::Stop => run_command(
                "powershell",
                ["-Command", &format!("Stop-Service -Name '{}'", name)],
            ),
            ServiceAction::Restart => run_command(
                "powershell",
                ["-Command", &format!("Restart-Service -Name '{}'", name)],
            ),
        };
    }

    #[allow(unreachable_code)]
    Err("Service control is not supported on this platform.".to_string())
}

fn lock_user(name: String, lock: bool) -> Result<String, String> {
    ensure_safe_identifier("user name", &name)?;

    #[cfg(target_os = "macos")]
    return run_command(
        "pwpolicy",
        if lock {
            vec!["-u", name.as_str(), "-setpolicy", "isDisabled=1"]
        } else {
            vec!["-u", name.as_str(), "-setpolicy", "isDisabled=0"]
        },
    );
    #[cfg(target_os = "linux")]
    return run_command(
        "usermod",
        if lock {
            vec!["-L", name.as_str()]
        } else {
            vec!["-U", name.as_str()]
        },
    );
    #[cfg(target_os = "windows")]
    return run_command(
        "net",
        if lock {
            vec!["user", name.as_str(), "/active:no"]
        } else {
            vec!["user", name.as_str(), "/active:yes"]
        },
    );

    #[allow(unreachable_code)]
    Err("User locking is not supported on this platform.".to_string())
}

fn terminate_connection(pid: u32) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    {
        let pid_string = pid.to_string();
        return run_command("kill", ["-9", pid_string.as_str()]);
    }
    #[cfg(target_os = "linux")]
    {
        let pid_string = pid.to_string();
        return run_command("kill", ["-9", pid_string.as_str()]);
    }
    #[cfg(target_os = "windows")]
    {
        let pid_string = pid.to_string();
        return run_command("taskkill", ["/PID", pid_string.as_str(), "/F"]);
    }

    #[allow(unreachable_code)]
    Err("Connection termination is not supported on this platform.".to_string())
}

fn execute_privileged_action_inner(request: &PrivilegedActionRequest) -> Result<String, String> {
    match request {
        PrivilegedActionRequest::Firewall { enabled } => set_firewall_enabled(*enabled),
        PrivilegedActionRequest::Service { name, action } => {
            control_service(name.clone(), action.clone())
        }
        PrivilegedActionRequest::UserLock { name, lock } => lock_user(name.clone(), *lock),
        PrivilegedActionRequest::TerminateProcess { pid } => terminate_connection(*pid),
    }
}

fn detect_execution_targets() -> Vec<ExecutionTargetInfo> {
    let mut targets = vec![ExecutionTargetInfo {
        id: "cpu".to_string(),
        label: "CPU".to_string(),
        available: true,
        reason: "Always available local execution path.".to_string(),
    }];

    if cfg!(target_os = "macos") {
        targets.push(ExecutionTargetInfo {
            id: "metal".to_string(),
            label: "Metal".to_string(),
            available: true,
            reason: "macOS target detected; Metal-backed acceleration path is available for future routing.".to_string(),
        });
    } else {
        targets.push(ExecutionTargetInfo {
            id: "metal".to_string(),
            label: "Metal".to_string(),
            available: false,
            reason: "Metal is only available on macOS.".to_string(),
        });
    }

    targets.push(ExecutionTargetInfo {
        id: "cuda".to_string(),
        label: "CUDA".to_string(),
        available: command_exists("nvidia-smi"),
        reason: if command_exists("nvidia-smi") {
            "NVIDIA tooling detected on host.".to_string()
        } else {
            "NVIDIA tooling not detected on host.".to_string()
        },
    });

    targets.push(ExecutionTargetInfo {
        id: "npu".to_string(),
        label: "NPU".to_string(),
        available: cfg!(target_os = "macos"),
        reason: if cfg!(target_os = "macos") {
            "Apple platform detected; NPU/Neural Engine routing is a future candidate.".to_string()
        } else {
            "Dedicated NPU routing is not detected in the current build.".to_string()
        },
    });

    targets
}

#[tauri::command]
fn preview_privileged_action(request: PrivilegedActionRequest) -> PrivilegedActionPreview {
    preview_for_action(&request)
}

#[tauri::command]
fn execute_privileged_action(
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

    match execute_privileged_action_inner(&request) {
        Ok(message) => PrivilegedActionResult {
            status: "executed".to_string(),
            action_type: preview.action_type,
            action_label: preview.action_label,
            target: preview.target,
            message: "Sensitive OS action executed.".to_string(),
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
use sysinfo::{CpuRefreshKind, Disks, MemoryRefreshKind, ProcessRefreshKind, RefreshKind, System};

#[derive(Serialize)]
pub struct CpuInfo {
    pub usage: f32,
    pub core_count: usize,
    pub brand: String,
}

#[derive(Serialize)]
pub struct MemInfo {
    pub used_gb: f64,
    pub total_gb: f64,
    pub used_pct: f64,
}

#[derive(Serialize)]
pub struct DiskInfo {
    pub name: String,
    pub mount: String,
    pub used_gb: f64,
    pub total_gb: f64,
    pub used_pct: f64,
}

#[derive(Serialize)]
pub struct ProcessInfo {
    pub pid: u32,
    pub name: String,
    pub cpu_pct: f32,
    pub mem_mb: f64,
}

#[derive(Serialize)]
pub struct SystemInfo {
    pub cpu: CpuInfo,
    pub mem: MemInfo,
    pub disks: Vec<DiskInfo>,
    pub top_processes: Vec<ProcessInfo>,
    pub execution_targets: Vec<ExecutionTargetInfo>,
}

#[tauri::command]
fn get_system_info() -> SystemInfo {
    let mut sys = System::new_with_specifics(
        RefreshKind::nothing()
            .with_cpu(CpuRefreshKind::everything())
            .with_memory(MemoryRefreshKind::everything())
            .with_processes(ProcessRefreshKind::everything()),
    );
    // Second refresh so CPU usage deltas are meaningful
    std::thread::sleep(sysinfo::MINIMUM_CPU_UPDATE_INTERVAL);
    sys.refresh_cpu_all();
    sys.refresh_memory();

    let usage: f32 = sys.cpus().iter().map(|c| c.cpu_usage()).sum::<f32>()
        / sys.cpus().len().max(1) as f32;

    let cpu = CpuInfo {
        usage,
        core_count: sys.cpus().len(),
        brand: sys.cpus().first().map(|c| c.brand().to_owned()).unwrap_or_default(),
    };

    let total_bytes = sys.total_memory();
    let used_bytes = sys.used_memory();
    let total_gb = total_bytes as f64 / 1_073_741_824.0;
    let used_gb = used_bytes as f64 / 1_073_741_824.0;
    let mem = MemInfo {
        used_gb,
        total_gb,
        used_pct: if total_gb > 0.0 { used_gb / total_gb * 100.0 } else { 0.0 },
    };

    let disks_info = Disks::new_with_refreshed_list();
    let disks: Vec<DiskInfo> = disks_info
        .iter()
        .map(|d| {
            let total = d.total_space() as f64 / 1_073_741_824.0;
            let avail = d.available_space() as f64 / 1_073_741_824.0;
            let used = (total - avail).max(0.0);
            DiskInfo {
                name: d.name().to_string_lossy().into_owned(),
                mount: d.mount_point().to_string_lossy().into_owned(),
                used_gb: used,
                total_gb: total,
                used_pct: if total > 0.0 { used / total * 100.0 } else { 0.0 },
            }
        })
        .collect();

    let mut procs: Vec<ProcessInfo> = sys
        .processes()
        .values()
        .map(|p| ProcessInfo {
            pid: p.pid().as_u32(),
            name: p.name().to_string_lossy().into_owned(),
            cpu_pct: p.cpu_usage(),
            mem_mb: p.memory() as f64 / 1_048_576.0,
        })
        .collect();
    procs.sort_by(|a, b| b.cpu_pct.partial_cmp(&a.cpu_pct).unwrap_or(std::cmp::Ordering::Equal));
    procs.truncate(20);

    SystemInfo {
        cpu,
        mem,
        disks,
        top_processes: procs,
        execution_targets: detect_execution_targets(),
    }
}


#[tauri::command]
fn get_home_dir() -> String {
    dirs::home_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("/"))
        .to_string_lossy()
        .into_owned()
}

#[tauri::command]
fn get_firewall_status() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    return run_command("/sbin/pfctl", ["-s", "info"]);
    #[cfg(target_os = "linux")]
    return run_command("ufw", ["status"]);
    #[cfg(target_os = "windows")]
    return run_command("netsh", ["advfirewall", "show", "allprofiles"]);

    #[allow(unreachable_code)]
    Err("Firewall status is not supported on this platform.".to_string())
}

#[tauri::command]
fn get_services() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    return run_command("launchctl", ["list"]);
    #[cfg(target_os = "linux")]
    return run_command(
        "systemctl",
        ["list-units", "--type=service", "--state=running"],
    );
    #[cfg(target_os = "windows")]
    return run_command(
        "powershell",
        ["Get-Service", "|", "Where-Object", "{$_.Status -eq 'Running'}"],
    );

    #[allow(unreachable_code)]
    Err("Service listing is not supported on this platform.".to_string())
}

#[tauri::command]
fn get_users() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    return run_command("dscl", [".", "list", "/Users"]);
    #[cfg(target_os = "linux")]
    return run_command("cut", ["-d:", "-f1", "/etc/passwd"]);
    #[cfg(target_os = "windows")]
    return run_command("net", ["user"]);

    #[allow(unreachable_code)]
    Err("User listing is not supported on this platform.".to_string())
}

#[tauri::command]
fn get_audit_log() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    return run_command("log", ["show", "--last", "1h", "--style", "compact"]);
    #[cfg(target_os = "linux")]
    return run_command("journalctl", ["-n", "100", "--no-pager"]);
    #[cfg(target_os = "windows")]
    return run_command("powershell", ["Get-EventLog", "-LogName", "System", "-Newest", "100"]);

    #[allow(unreachable_code)]
    Err("Audit log access is not supported on this platform.".to_string())
}

#[tauri::command]
fn get_network_connections() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    return run_command("netstat", ["-an"]);
    #[cfg(target_os = "linux")]
    return run_command("ss", ["-tunap"]);
    #[cfg(target_os = "windows")]
    return run_command("netstat", ["-an"]);

    #[allow(unreachable_code)]
    Err("Network connection listing is not supported on this platform.".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            get_system_info,
            get_home_dir,
            get_firewall_status,
            get_services,
            get_users,
            get_audit_log,
            get_network_connections,
            preview_privileged_action,
            execute_privileged_action,
            list_plugins,
            run_plugin,
            toggle_plugin_enabled,
            discover_plugins,
            install_plugin,
            list_tool_adapters,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Oxy");
}
