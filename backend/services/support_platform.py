from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def support_platform_id() -> str:
    system = platform.system().lower()
    if system.startswith("darwin"):
        return "macos"
    if system.startswith("windows"):
        return "windows"
    if system.startswith("linux"):
        return "ubuntu" if _looks_like_ubuntu() else "linux"
    return system or "unknown"


def collect_cpu_load_pct() -> float:
    if os.name == "nt":
        return _windows_cpu_load_pct()
    cpu_count = os.cpu_count() or 1
    try:
        load_avg = os.getloadavg()[0]
        return min(100.0, (load_avg / cpu_count) * 100.0)
    except (AttributeError, OSError):
        return 0.0


def collect_memory_used_pct() -> float:
    if os.name == "nt":
        return _windows_memory_used_pct()
    try:
        if shutil.which("vm_stat"):
            result = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True)
            pages = {}
            page_size = 4096
            for line in result.stdout.splitlines():
                if "page size of" in line:
                    try:
                        page_size = int(line.split("page size of", 1)[1].split("bytes", 1)[0].strip())
                    except Exception:
                        page_size = 4096
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                value = value.strip().rstrip(".").replace(".", "")
                if value.isdigit():
                    pages[key.strip()] = int(value)
            active = pages.get("Pages active", 0) + pages.get("Pages wired down", 0) + pages.get("Pages occupied by compressor", 0)
            free = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
            total = active + free + pages.get("Pages inactive", 0)
            if total > 0:
                return active / total * 100.0
        if shutil.which("free"):
            result = subprocess.run(["free", "-m"], capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if line.lower().startswith("mem:"):
                    parts = line.split()
                    total = float(parts[1])
                    used = float(parts[2])
                    if total > 0:
                        return used / total * 100.0
    except Exception:
        return 0.0
    return 0.0


def read_processes() -> list[dict[str, Any]]:
    if os.name == "nt":
        return _windows_processes()
    try:
        result = subprocess.run(["ps", "-Ao", "comm=,%cpu=,rss="], capture_output=True, text=True, check=True)
    except Exception:
        return []
    processes = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        name, cpu_raw, rss_raw = parts
        try:
            processes.append({"name": name, "cpu_pct": float(cpu_raw), "rss_kb": int(rss_raw)})
        except ValueError:
            continue
    return processes


def count_active_connections() -> int:
    if os.name == "nt":
        command = ["netstat", "-an"]
    elif Path("/usr/sbin/ss").exists() or Path("/bin/ss").exists() or shutil.which("ss"):
        command = ["ss", "-tan"]
    else:
        command = ["netstat", "-an"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except Exception:
        return 0
    return sum(1 for line in result.stdout.splitlines() if line.strip() and ("ESTAB" in line or "ESTABLISHED" in line))


def allowlisted_cleanup_targets() -> list[Path]:
    candidates: list[Path] = []
    home = Path.home()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Temp")
        candidates.append(home / "Downloads")
    elif support_platform_id() == "macos":
        candidates.extend([home / "Library" / "Caches", home / "Downloads"])
    else:
        candidates.extend([home / ".cache", home / "Downloads", Path(tempfile.gettempdir())])
    return [path for path in candidates if path.exists()]


def check_windows_update_pending_reboot() -> bool:
    """True if Windows Update or CBS is waiting for a reboot (registry key exists)."""
    if os.name != "nt":
        return False
    import winreg
    reboot_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
    ]
    for subkey in reboot_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey):
                return True
        except OSError:
            continue
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager") as key:
            val, _ = winreg.QueryValueEx(key, "PendingFileRenameOperations")
            if val:
                return True
    except OSError:
        pass
    return False


def check_windows_service_running(service_name: str) -> bool:
    """True if the named Windows service is in RUNNING state. Defaults True on error to avoid false positives."""
    if os.name != "nt":
        return True
    try:
        result = subprocess.run(["sc", "query", service_name], capture_output=True, text=True, timeout=5)
        return "RUNNING" in result.stdout
    except Exception:
        return True


def check_windows_defender_enabled() -> bool:
    """True if Windows Defender real-time protection is enabled (DisableRealtimeMonitoring == 0 or absent)."""
    if os.name != "nt":
        return True
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Defender\Real-Time Protection") as key:
            val, _ = winreg.QueryValueEx(key, "DisableRealtimeMonitoring")
            return val == 0
    except OSError:
        return True  # Key absent = Defender active or 3rd-party AV managing it


def check_audio_device_errors() -> list[dict]:
    """Returns PnP audio/camera devices with error status. Empty list = all healthy."""
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
             "Get-PnpDevice | Where-Object { $_.Status -eq 'Error' -and $_.Class -in @('AudioEndpoint','Media','SoundSystem','Camera','Image') } "
             "| Select-Object Name,InstanceId,Status | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15,
        )
        raw = result.stdout.strip()
        if not raw:
            return []
        import json
        data = json.loads(raw)
        return [data] if isinstance(data, dict) else data
    except Exception:
        return []


def check_onedrive_stuck() -> bool:
    """True if OneDrive is running but consuming excessive memory (>400 MB) — likely stuck."""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
             "$p = Get-Process -Name OneDrive -ErrorAction SilentlyContinue; "
             "if ($p) { ($p | Measure-Object WorkingSet64 -Sum).Sum / 1MB } else { -1 }"],
            capture_output=True, text=True, timeout=10,
        )
        val = float(result.stdout.strip())
        return val > 400  # >400 MB is abnormally high for OneDrive
    except Exception:
        return False


def check_expiring_certificates(days: int = 30) -> list[dict]:
    """Returns certs in CurrentUser\\My expiring within `days` days. Empty = all healthy."""
    if os.name != "nt":
        return []
    try:
        script = (
            f"$w = (Get-Date).AddDays({days}); "
            "Get-ChildItem Cert:\\CurrentUser\\My -ErrorAction SilentlyContinue "
            "| Where-Object { $_.NotAfter -lt $w -and $_.NotAfter -gt (Get-Date) } "
            "| Select-Object @{n='Subject';e={$_.Subject}}, @{n='Expiry';e={$_.NotAfter.ToString('yyyy-MM-dd')}}, "
            "  @{n='DaysLeft';e={[int]($_.NotAfter - (Get-Date)).TotalDays}} "
            "| ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            capture_output=True, text=True, timeout=15,
        )
        raw = result.stdout.strip()
        if not raw:
            return []
        import json
        data = json.loads(raw)
        return [data] if isinstance(data, dict) else data
    except Exception:
        return []


def check_windows_update_age_days() -> int:
    """Returns days since last successful Windows Update install. -1 if unknown."""
    if os.name != "nt":
        return -1
    import winreg
    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\Results\Install"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            val, _ = winreg.QueryValueEx(key, "LastSuccessTime")
            from datetime import datetime, timezone
            last = datetime.strptime(str(val).strip(), "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - last).days
    except Exception:
        return -1


def _windows_cpu_load_pct() -> float:
    commands = [
        ["powershell", "-NoProfile", "-Command", "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue"],
        ["wmic", "cpu", "get", "loadpercentage", "/value"],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            text = result.stdout.strip()
            if not text:
                continue
            if "LoadPercentage=" in text:
                return float(text.split("LoadPercentage=", 1)[1].splitlines()[0].strip())
            for token in text.replace("\r", "\n").split():
                try:
                    return float(token)
                except ValueError:
                    continue
        except Exception:
            continue
    return 0.0


def _windows_memory_used_pct() -> float:
    commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$os=Get-CimInstance Win32_OperatingSystem; (($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize)*100",
        ],
        ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            text = result.stdout.strip()
            if not text:
                continue
            if "FreePhysicalMemory=" in text and "TotalVisibleMemorySize=" in text:
                values = {}
                for line in text.splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        values[key.strip()] = float(value.strip())
                total = values.get("TotalVisibleMemorySize", 0.0)
                free = values.get("FreePhysicalMemory", 0.0)
                if total > 0:
                    return ((total - free) / total) * 100.0
            for token in text.replace("\r", "\n").split():
                try:
                    return float(token)
                except ValueError:
                    continue
        except Exception:
            continue
    return 0.0


def _windows_processes() -> list[dict[str, Any]]:
    commands = [
        ["powershell", "-NoProfile", "-Command", "Get-Process | Select-Object ProcessName,WorkingSet64 | ConvertTo-Csv -NoTypeInformation"],
        ["tasklist", "/FO", "CSV", "/NH"],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            if "Get-Process" in " ".join(command):
                rows = []
                for line in result.stdout.splitlines()[1:]:
                    cells = [cell.strip().strip('"') for cell in line.split(",")]
                    if len(cells) >= 2:
                        try:
                            rows.append({"name": cells[0], "cpu_pct": 0.0, "rss_kb": int(float(cells[1]) / 1024)})
                        except ValueError:
                            continue
                if rows:
                    return rows
            else:
                rows = []
                for line in result.stdout.splitlines():
                    cells = [cell.strip().strip('"') for cell in line.split('","')]
                    if len(cells) >= 5:
                        mem = cells[4].replace(",", "").replace(" K", "")
                        try:
                            rows.append({"name": cells[0], "cpu_pct": 0.0, "rss_kb": int(mem)})
                        except ValueError:
                            continue
                if rows:
                    return rows
        except Exception:
            continue
    return []


def _looks_like_ubuntu() -> bool:
    try:
        text = Path("/etc/os-release").read_text()
    except Exception:
        return False
    return "ubuntu" in text.lower()
