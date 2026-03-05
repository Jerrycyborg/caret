mod plugins;
use plugins::oxy_plugin::{list_plugins, run_plugin, toggle_plugin_enabled, discover_plugins, install_plugin};
#[tauri::command]
fn set_firewall_enabled(enabled: bool) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = if enabled { "sudo pfctl -e" } else { "sudo pfctl -d" };
    #[cfg(target_os = "linux")]
    let cmd = if enabled { "sudo ufw enable" } else { "sudo ufw disable" };
    #[cfg(target_os = "windows")]
    let cmd = if enabled {
        "netsh advfirewall set allprofiles state on"
    } else {
        "netsh advfirewall set allprofiles state off"
    };
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}

#[tauri::command]
fn control_service(name: String, action: String) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = format!("sudo launchctl {} {}", action, name);
    #[cfg(target_os = "linux")]
    let cmd = format!("sudo systemctl {} {}", action, name);
    #[cfg(target_os = "windows")]
    let cmd = format!("powershell Start-Service -Name {}", name); // Only start for now
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}

#[tauri::command]
fn lock_user(name: String, lock: bool) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = if lock {
        format!("sudo pwpolicy -u {} -setpolicy 'isDisabled=1'", name)
    } else {
        format!("sudo pwpolicy -u {} -setpolicy 'isDisabled=0'", name)
    };
    #[cfg(target_os = "linux")]
    let cmd = if lock {
        format!("sudo usermod -L {}", name)
    } else {
        format!("sudo usermod -U {}", name)
    };
    #[cfg(target_os = "windows")]
    let cmd = if lock {
        format!("net user {} /active:no", name)
    } else {
        format!("net user {} /active:yes", name)
    };
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}

#[tauri::command]
fn terminate_connection(pid: u32) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = format!("sudo kill -9 {}", pid);
    #[cfg(target_os = "linux")]
    let cmd = format!("sudo kill -9 {}", pid);
    #[cfg(target_os = "windows")]
    let cmd = format!("taskkill /PID {} /F", pid);
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}
use serde::Serialize;
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

    SystemInfo { cpu, mem, disks, top_processes: procs }
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
    let cmd = "sudo pfctl -sr";
    #[cfg(target_os = "linux")]
    let cmd = "sudo iptables -L";
    #[cfg(target_os = "windows")]
    let cmd = "netsh advfirewall firewall show rule name=all";
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}

#[tauri::command]
fn get_services() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = "launchctl list";
    #[cfg(target_os = "linux")]
    let cmd = "systemctl list-units --type=service --state=running";
    #[cfg(target_os = "windows")]
    let cmd = "powershell Get-Service | Where-Object {$_.Status -eq 'Running'}";
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}

#[tauri::command]
fn get_users() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = "dscl . list /Users";
    #[cfg(target_os = "linux")]
    let cmd = "cut -d: -f1 /etc/passwd";
    #[cfg(target_os = "windows")]
    let cmd = "net user";
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}

#[tauri::command]
fn get_audit_log() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = "tail -n 100 /var/log/system.log";
    #[cfg(target_os = "linux")]
    let cmd = "tail -n 100 /var/log/syslog";
    #[cfg(target_os = "windows")]
    let cmd = "powershell Get-EventLog -LogName System -Newest 100";
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
}

#[tauri::command]
fn get_network_connections() -> Result<String, String> {
    #[cfg(target_os = "macos")]
    let cmd = "netstat -an";
    #[cfg(target_os = "linux")]
    let cmd = "netstat -tunap";
    #[cfg(target_os = "windows")]
    let cmd = "netstat -an";
    std::process::Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .map_err(|e| e.to_string())
        .and_then(|o| String::from_utf8(o.stdout).map_err(|e| e.to_string()))
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
            set_firewall_enabled,
            control_service,
            lock_user,
            terminate_connection,
            list_plugins,
            run_plugin,
            toggle_plugin_enabled,
            discover_plugins,
            install_plugin,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Oxy");
}

