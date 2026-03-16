pub mod plugins;
mod privilege;
mod tools;
use plugins::caret_plugin::{discover_plugins, install_plugin, list_plugins, run_plugin, toggle_plugin_enabled};
use privilege::{execute_privileged_action, preview_privileged_action};
use serde::Serialize;
use std::ffi::OsStr;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{Manager, RunEvent};
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

fn run_powershell(script: &str) -> Result<String, String> {
    run_command(
        "powershell",
        ["-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
    )
}

fn command_exists(program: &str) -> bool {
    Command::new(program).arg("--version").output().is_ok()
}

struct BackendSidecarState(Mutex<Option<Child>>);

fn backend_port_open() -> bool {
    std::net::TcpStream::connect_timeout(
        &"127.0.0.1:8000".parse().expect("valid loopback socket"),
        Duration::from_millis(300),
    )
    .is_ok()
}

fn backend_sidecar_path(app: &tauri::AppHandle) -> Option<std::path::PathBuf> {
    use tauri::path::BaseDirectory;
    app.path()
        .resolve("resources/windows/caret-backend.exe", BaseDirectory::Resource)
        .ok()
        .filter(|path| path.exists())
}

fn launch_backend_sidecar(app: &tauri::AppHandle) -> Result<(), String> {
    if backend_port_open() {
        return Ok(());
    }

    let path = backend_sidecar_path(app)
        .ok_or_else(|| "Bundled backend sidecar was not found in packaged resources.".to_string())?;

    let child = Command::new(path)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to launch bundled backend sidecar: {e}"))?;

    let state = app.state::<BackendSidecarState>();
    let mut guard = state.0.lock().map_err(|_| "Failed to lock backend sidecar state.".to_string())?;
    *guard = Some(child);
    Ok(())
}

#[derive(Clone, Serialize)]
pub struct BackendStatus {
    pub status: String, // "ready" | "starting" | "unavailable"
    pub message: String,
}

#[tauri::command]
fn get_backend_status(app: tauri::AppHandle) -> BackendStatus {
    if backend_port_open() {
        return BackendStatus {
            status: "ready".to_string(),
            message: "Backend is running.".to_string(),
        };
    }

    // Try to launch if not already running
    match launch_backend_sidecar(&app) {
        Ok(_) => BackendStatus {
            status: "starting".to_string(),
            message: "Backend is starting…".to_string(),
        },
        Err(e) => {
            eprintln!("[caret] Backend unavailable: {e}");
            BackendStatus {
                status: "unavailable".to_string(),
                message: e,
            }
        }
    }
}

fn stop_backend_sidecar(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<BackendSidecarState>() {
        if let Ok(mut guard) = state.0.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

#[derive(Clone, Serialize)]
pub struct ExecutionTargetInfo {
    pub id: String,
    pub label: String,
    pub available: bool,
    pub reason: String,
}

fn detect_execution_targets() -> Vec<ExecutionTargetInfo> {
    vec![
        ExecutionTargetInfo {
            id: "cpu".to_string(),
            label: "CPU".to_string(),
            available: true,
            reason: "Always available local execution path.".to_string(),
        },
        ExecutionTargetInfo {
            id: "cuda".to_string(),
            label: "CUDA".to_string(),
            available: command_exists("nvidia-smi"),
            reason: if command_exists("nvidia-smi") {
                "NVIDIA tooling detected on host.".to_string()
            } else {
                "NVIDIA tooling not detected on host.".to_string()
            },
        },
    ]
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
        .unwrap_or_else(|| std::path::PathBuf::from("C:\\"))
        .to_string_lossy()
        .into_owned()
}

#[derive(Serialize)]
pub struct AdminStatus {
    pub is_admin: bool,
    pub method: String,
}

#[tauri::command]
fn get_admin_status(admin_group: Option<String>) -> AdminStatus {
    let group = admin_group.as_deref().unwrap_or("").trim().to_string();

    if !group.is_empty() {
        // Strictly validate: only allow characters safe in AD group names
        // Rejects anything that could break out of a PowerShell string literal
        let safe = group.chars().all(|c| c.is_alphanumeric() || matches!(c, '-' | '_' | ' ' | '.'));
        if !safe {
            return AdminStatus { is_admin: false, method: "ad_group:rejected_unsafe_name".to_string() };
        }
        // Embed the literal group name as a PowerShell variable to avoid string injection
        let script = format!(
            r#"$target = '{group}'; $g = ([System.Security.Principal.WindowsIdentity]::GetCurrent()).Groups | ForEach-Object {{ try {{ $_.Translate([System.Security.Principal.NTAccount]).Value }} catch {{ '' }} }}; ($g -match [regex]::Escape($target)).Count -gt 0"#
        );
        let is_admin = run_powershell(&script)
            .map(|out| out.trim().to_lowercase() == "true")
            .unwrap_or(false);
        return AdminStatus {
            is_admin,
            method: format!("ad_group:{group}"),
        };
    }

    // Default: Windows local admin check
    let script = "(New-Object System.Security.Principal.WindowsPrincipal(\
        [System.Security.Principal.WindowsIdentity]::GetCurrent())\
        ).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)";
    let is_admin = run_powershell(script)
        .map(|out| out.trim().to_lowercase() == "true")
        .unwrap_or(false);
    AdminStatus {
        is_admin,
        method: "windows_local_admin".to_string(),
    }
}

#[derive(Serialize)]
pub struct ComplianceStatus {
    pub firewall_on: bool,
    pub bitlocker_on: bool,
    pub active_connections: usize,
    pub recent_errors: usize,
}

#[tauri::command]
fn get_compliance_status() -> ComplianceStatus {
    let firewall_on = run_command("netsh", ["advfirewall", "show", "allprofiles"])
        .map(|out| out.lines().filter(|l| l.contains("State")).any(|l| l.contains("ON")))
        .unwrap_or(false);

    let bitlocker_on = run_powershell(
        "(Get-BitLockerVolume -MountPoint 'C:').ProtectionStatus -eq 'On'",
    )
    .map(|out| out.trim().to_lowercase() == "true")
    .unwrap_or(false);

    let active_connections = run_command("netstat", ["-an"])
        .map(|out| out.lines().filter(|l| l.contains("ESTABLISHED")).count())
        .unwrap_or(0);

    let recent_errors = run_powershell(
        "(Get-WinEvent -LogName System -MaxEvents 50 -ErrorAction SilentlyContinue \
        | Where-Object { $_.LevelDisplayName -in 'Error','Warning' } \
        | Measure-Object).Count",
    )
    .map(|out| out.trim().parse::<usize>().unwrap_or(0))
    .unwrap_or(0);

    ComplianceStatus {
        firewall_on,
        bitlocker_on,
        active_connections,
        recent_errors,
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            app.manage(BackendSidecarState(Mutex::new(None)));
            if let Err(e) = launch_backend_sidecar(app.handle()) {
                eprintln!("[caret] Backend sidecar failed to start: {e}");
                // Non-fatal — frontend will show "Backend offline" banner
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_system_info,
            get_backend_status,
            get_home_dir,
            get_admin_status,
            get_compliance_status,
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
        .build(tauri::generate_context!())
        .expect("error while building Caret");

    app.run(|app, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            stop_backend_sidecar(app);
        }
    });
}
