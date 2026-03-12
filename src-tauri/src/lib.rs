pub mod plugins;
mod privilege;
mod tools;
use plugins::oxy_plugin::{discover_plugins, install_plugin, list_plugins, run_plugin, toggle_plugin_enabled};
use privilege::{execute_privileged_action, preview_privileged_action};
use serde::Serialize;
use std::ffi::OsStr;
use std::process::Command;
use tools::{execute_tool_adapter, list_tool_adapters};

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

#[cfg(target_os = "windows")]
fn run_powershell(script: &str) -> Result<String, String> {
    run_command("powershell", ["-NoProfile", "-Command", script])
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
    return run_powershell(
        "Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Status,Name,DisplayName | Format-Table -AutoSize",
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
    return run_powershell("Get-EventLog -LogName System -Newest 100 | Format-Table -AutoSize");

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
            execute_tool_adapter,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Oxy");
}
