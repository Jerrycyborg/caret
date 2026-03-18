from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from database import get_db_path
from services.config import get_config_section
from services.orchestrator import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_REJECTED,
    create_task,
)
from services.support_platform import (
    allowlisted_cleanup_targets,
    check_audio_device_errors,
    check_onedrive_stuck,
    check_windows_defender_enabled,
    check_windows_service_running,
    check_windows_update_pending_reboot,
    collect_cpu_load_pct,
    collect_memory_used_pct,
    count_active_connections,
    read_processes,
    support_platform_id,
)

CHECK_INTERVAL_SECONDS = int(os.environ.get("CARET_SUPPORT_DAEMON_INTERVAL", "300"))
TRIGGER_COOLDOWN_MINUTES = int(os.environ.get("CARET_SUPPORT_DAEMON_COOLDOWN_MINUTES", "360"))

_daemon_state: dict[str, Any] = {
    "running": False,
    "interval_seconds": CHECK_INTERVAL_SECONDS,
    "last_run_at": None,
    "next_run_at": None,
    "last_error": "",
    "last_snapshot": None,
    "last_issues": [],
    "platform": support_platform_id(),
}


@dataclass
class SupportSnapshot:
    disk_used_pct: float
    cpu_load_pct: float
    teams_cpu_pct: float
    active_connections: int
    mem_used_pct: float = 0.0
    camera_ready: bool = True
    printer_ready: bool = True
    background_heavy_count: int = 0
    pending_reboot: bool = False
    spooler_running: bool = True
    defender_enabled: bool = True
    audio_device_errors: list = field(default_factory=list)
    onedrive_stuck: bool = False


@dataclass
class SupportIssue:
    key: str
    category: str
    severity: str
    title: str
    summary: str
    prompt: str
    recommended_fixes: list[str] = field(default_factory=list)
    auto_fix_kind: str | None = None
    escalation_reason: str = ""


async def init_support_tables() -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS support_watch_events (
                issue_key TEXT PRIMARY KEY,
                category TEXT NOT NULL DEFAULT 'performance',
                severity TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                recommended_fixes_json TEXT NOT NULL DEFAULT '[]',
                auto_fix_eligible INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                last_task_id TEXT,
                last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_triggered_at TEXT,
                trigger_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        await _ensure_column(db, "support_watch_events", "category", "TEXT NOT NULL DEFAULT 'performance'")
        await _ensure_column(db, "support_watch_events", "title", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "support_watch_events", "recommended_fixes_json", "TEXT NOT NULL DEFAULT '[]'")
        await _ensure_column(db, "support_watch_events", "auto_fix_eligible", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "support_watch_events", "active", "INTEGER NOT NULL DEFAULT 1")
        await db.commit()


async def support_daemon_status() -> dict[str, Any]:
    await init_support_tables()
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT issue_key, category, severity, title, summary, recommended_fixes_json,
                   auto_fix_eligible, active, last_task_id, last_seen_at, last_triggered_at, trigger_count
            FROM support_watch_events
            ORDER BY last_seen_at DESC
            """
        ) as cur:
            watcher_rows = [dict(row) for row in await cur.fetchall()]
        async with db.execute(
            """
            SELECT *
            FROM tasks
            WHERE task_kind = 'support_incident'
            ORDER BY updated_at DESC
            LIMIT 40
            """
        ) as cur:
            task_rows = [dict(row) for row in await cur.fetchall()]

    monitoring = []
    for row in watcher_rows:
        if not row["active"] or row["severity"] != "monitoring":
            continue
        fixes = json.loads(row["recommended_fixes_json"])
        monitoring.append(
            {
                "issue_key": row["issue_key"],
                "category": row["category"],
                "title": row["title"],
                "severity": row["severity"],
                "decision_kind": "monitoring",
                "decision_reason": "Signal crossed the early-warning threshold but has not become actionable yet.",
                "summary": row["summary"],
                "recommended_fixes": fixes,
                "last_task_id": row["last_task_id"],
                "trigger_count": row["trigger_count"],
                "source_signal": row["issue_key"],
                "detected_at": row["last_seen_at"],
                "last_decision_at": row["last_seen_at"],
            }
        )

    incidents = [_task_to_support_incident(row) for row in task_rows]
    fix_queue = [item for item in incidents if item["support_severity"] == "fix_queued"]
    escalations = [item for item in incidents if item["support_severity"] in {"action_required", "blocked", "escalated"}]
    history = [item for item in incidents if item["support_severity"] in {"fix_queued", "fixed", "blocked", "escalated", "action_required"}][:12]
    last_successful_auto_fix = next(
        (item for item in incidents if item["support_severity"] == "fixed" and item["auto_fix_attempted"]),
        None,
    )

    watcher_status = "active" if _daemon_state["running"] else ("needs_attention" if _daemon_state["last_error"] else "starting")
    return {
        **_daemon_state,
        "summary": {
            "platform": support_platform_id(),
            "watcher_status": watcher_status,
            "monitoring_count": len(monitoring),
            "queued_fix_count": len(fix_queue),
            "escalation_count": len(escalations),
            "active_incident_count": len(fix_queue) + len(escalations),
            "last_successful_auto_fix": last_successful_auto_fix,
        },
        "monitoring": monitoring,
        "fix_queue": fix_queue,
        "escalations": escalations,
        "history": history,
    }


def collect_support_snapshot() -> SupportSnapshot:
    home_usage = shutil.disk_usage(Path.home())
    disk_used_pct = ((home_usage.total - home_usage.free) / home_usage.total * 100.0) if home_usage.total else 0.0
    cpu_load_pct = collect_cpu_load_pct()
    mem_used_pct = collect_memory_used_pct()
    processes = read_processes()
    process_names = [process["name"].lower() for process in processes]
    teams_cpu_pct = max((process["cpu_pct"] for process in processes if "teams" in process["name"].lower()), default=0.0)
    background_heavy_count = sum(1 for process in processes if process["cpu_pct"] >= 15)
    camera_ready = any(token in name for name in process_names for token in ("camera", "avfoundation", "coreaudiod", "pipewire", "wireplumber"))
    printer_ready = any(token in name for name in process_names for token in ("cups", "printer", "print"))
    active_connections = count_active_connections()
    pending_reboot = check_windows_update_pending_reboot()
    spooler_running = check_windows_service_running("Spooler")
    defender_enabled = check_windows_defender_enabled()
    audio_device_errors = check_audio_device_errors()
    onedrive_stuck = check_onedrive_stuck()
    return SupportSnapshot(
        disk_used_pct=round(disk_used_pct, 2),
        cpu_load_pct=round(cpu_load_pct, 2),
        teams_cpu_pct=round(teams_cpu_pct, 2),
        active_connections=active_connections,
        mem_used_pct=round(mem_used_pct, 2),
        camera_ready=camera_ready,
        printer_ready=printer_ready,
        background_heavy_count=background_heavy_count,
        pending_reboot=pending_reboot,
        spooler_running=spooler_running,
        defender_enabled=defender_enabled,
        audio_device_errors=audio_device_errors,
        onedrive_stuck=onedrive_stuck,
    )


def evaluate_support_snapshot(snapshot: SupportSnapshot) -> list[SupportIssue]:
    issues: list[SupportIssue] = []

    if snapshot.disk_used_pct >= 80:
        issues.append(
            SupportIssue(
                key="disk_pressure",
                category="disk",
                severity="action_required",
                title="Disk pressure",
                summary=f"Home disk usage is at {snapshot.disk_used_pct:.0f}%.",
                prompt="Review disk pressure, identify cleanup candidates, and prepare safe supervised cleanup steps.",
                recommended_fixes=["review cache and temp directories", "inspect Downloads and build outputs", "queue cleanup candidates before deletion"],
                auto_fix_kind="queue_cleanup_candidates",
            )
        )
    elif snapshot.disk_used_pct >= 70:
        issues.append(
            SupportIssue(
                key="disk_pressure",
                category="disk",
                severity="monitoring",
                title="Disk pressure",
                summary=f"Home disk usage is at {snapshot.disk_used_pct:.0f}%.",
                prompt="Monitor disk growth and prepare cleanup guidance.",
                recommended_fixes=["monitor top space consumers", "prepare cleanup candidate list"],
            )
        )

    perf_pressure = max(snapshot.cpu_load_pct, snapshot.mem_used_pct)
    if perf_pressure >= 85:
        issues.append(
            SupportIssue(
                key="performance_pressure",
                category="performance",
                severity="action_required",
                title="Performance pressure",
                summary=f"CPU is at {snapshot.cpu_load_pct:.0f}% and memory is at {snapshot.mem_used_pct:.0f}%.",
                prompt="Capture diagnostics, inspect top background processes, and prepare supervised performance remediation.",
                recommended_fixes=["capture process diagnostics", "review memory-heavy apps", "inspect startup/background load"],
                auto_fix_kind="capture_diagnostics",
            )
        )
    elif perf_pressure >= 65:
        issues.append(
            SupportIssue(
                key="performance_pressure",
                category="performance",
                severity="monitoring",
                title="Performance pressure",
                summary=f"CPU is at {snapshot.cpu_load_pct:.0f}% and memory is at {snapshot.mem_used_pct:.0f}%.",
                prompt="Monitor performance drift and prepare diagnostics.",
                recommended_fixes=["watch sustained CPU or memory spikes", "track heavy background processes"],
            )
        )

    if snapshot.teams_cpu_pct >= 25:
        issues.append(
            SupportIssue(
                key="meeting_app_pressure",
                category="meetings",
                severity="action_required",
                title="Meeting app pressure",
                summary=f"Teams-like process load is at {snapshot.teams_cpu_pct:.0f}% CPU.",
                prompt="Capture meeting-app diagnostics and prepare supervised remediation before the next call.",
                recommended_fixes=["capture diagnostics", "review network load", "restart only with explicit approval"],
                auto_fix_kind="capture_diagnostics",
            )
        )
    elif snapshot.teams_cpu_pct >= 12:
        issues.append(
            SupportIssue(
                key="meeting_app_pressure",
                category="meetings",
                severity="monitoring",
                title="Meeting app pressure",
                summary=f"Teams-like process load is at {snapshot.teams_cpu_pct:.0f}% CPU.",
                prompt="Monitor meeting-app pressure before it becomes user-visible.",
                recommended_fixes=["watch meeting app resource use", "prepare pre-call checks"],
            )
        )

    if snapshot.teams_cpu_pct >= 10 and not snapshot.camera_ready:
        issues.append(
            SupportIssue(
                key="camera_audio_readiness",
                category="camera_audio",
                severity="action_required",
                title="Camera and audio readiness",
                summary="Meeting activity is present but no camera/audio service signal was detected.",
                prompt="Inspect camera/audio readiness and prepare supervised remediation before the next meeting.",
                recommended_fixes=["refresh readiness checks", "inspect media permissions", "inspect audio/video helper services"],
                auto_fix_kind="refresh_readiness",
            )
        )

    if snapshot.background_heavy_count >= 4:
        issues.append(
            SupportIssue(
                key="startup_background_load",
                category="startup_services",
                severity="action_required",
                title="Startup and background load",
                summary=f"{snapshot.background_heavy_count} background processes are above the heavy-load threshold.",
                prompt="Inspect startup and background load, then prepare supervised remediation.",
                recommended_fixes=["review startup agents", "prioritize heavy processes", "queue a support remediation plan"],
            )
        )
    elif snapshot.background_heavy_count >= 2:
        issues.append(
            SupportIssue(
                key="startup_background_load",
                category="startup_services",
                severity="monitoring",
                title="Startup and background load",
                summary=f"{snapshot.background_heavy_count} background processes are already heavy.",
                prompt="Monitor startup and background load before slowdown becomes visible.",
                recommended_fixes=["watch heavy background processes", "prepare startup review"],
            )
        )

    if snapshot.active_connections >= 400 and not snapshot.printer_ready:
        issues.append(
            SupportIssue(
                key="printer_network_readiness",
                category="printer_network",
                severity="action_required",
                title="Printer and network readiness",
                summary=f"Detected {snapshot.active_connections} active connections and no printer service signal.",
                prompt="Monitor printer/network readiness and prepare diagnosis if connectivity degrades.",
                recommended_fixes=["refresh readiness checks", "watch network-heavy apps", "inspect printer/network service availability"],
                auto_fix_kind="refresh_readiness",
            )
        )

    if snapshot.pending_reboot:
        issues.append(
            SupportIssue(
                key="windows_update_reboot_pending",
                category="windows_update",
                severity="action_required",
                title="Windows Update pending reboot",
                summary="Windows Update or system component changes are waiting for a reboot to complete.",
                prompt="Report Windows Update reboot pending status and advise user to schedule a restart.",
                recommended_fixes=["save open work and restart at a convenient time", "check Windows Update history for details", "escalate if reboot has been pending more than 7 days"],
                auto_fix_kind="report_update_pending",
            )
        )

    if not snapshot.spooler_running:
        issues.append(
            SupportIssue(
                key="print_spooler_stopped",
                category="printing",
                severity="action_required",
                title="Print spooler stopped",
                summary="The Windows Print Spooler service is not running. Printing will fail until it is restarted.",
                prompt="Report that the Print Spooler service is stopped and advise IT to restart it via admin action.",
                recommended_fixes=["restart the Print Spooler service (requires admin)", "clear stuck print jobs", "escalate if spooler keeps stopping"],
                auto_fix_kind="report_spooler_stopped",
                escalation_reason="Print Spooler restart requires elevated privileges — escalate to IT admin.",
            )
        )

    if not snapshot.defender_enabled:
        issues.append(
            SupportIssue(
                key="defender_disabled",
                category="security",
                severity="action_required",
                title="Antivirus protection disabled",
                summary="Windows Defender real-time protection appears to be disabled. Device may be unprotected.",
                prompt="Report that real-time protection is disabled and advise IT to investigate immediately.",
                recommended_fixes=["re-enable Windows Defender real-time protection", "verify a third-party AV is active and licensed", "escalate to security team if unexplained"],
                auto_fix_kind="report_av_disabled",
                escalation_reason="Disabled antivirus is a security incident — escalate to IT security immediately.",
            )
        )

    if snapshot.audio_device_errors:
        names = ", ".join(d.get("Name", "Unknown device") for d in snapshot.audio_device_errors[:2])
        count = len(snapshot.audio_device_errors)
        issues.append(
            SupportIssue(
                key="audio_device_error",
                category="audio_drivers",
                severity="action_required",
                title="Audio or camera device error",
                summary=f"{count} audio/camera device(s) reporting errors: {names}.",
                prompt="A PnP audio or camera device has an error code. Restarting the device may restore mic, speaker, or camera function.",
                recommended_fixes=["restart audio devices via Security panel", "check Device Manager for driver errors", "reinstall or update driver if restart fails"],
                auto_fix_kind="report_audio_device_error",
                escalation_reason="Driver restart requires admin elevation — use Security panel admin action or escalate to IT.",
            )
        )

    if snapshot.onedrive_stuck:
        issues.append(
            SupportIssue(
                key="onedrive_stuck",
                category="onedrive",
                severity="action_required",
                title="OneDrive sync stuck",
                summary="OneDrive is consuming excessive memory (>400 MB), which typically indicates a stuck sync operation.",
                prompt="OneDrive appears stuck. Resetting it will stop the process and restart it cleanly without data loss.",
                recommended_fixes=["reset OneDrive sync via Security panel", "sign out and back in to OneDrive", "check for large files blocking sync"],
                auto_fix_kind="report_onedrive_stuck",
            )
        )

    if snapshot.teams_cpu_pct >= 20 and snapshot.mem_used_pct >= 75:
        issues.append(
            SupportIssue(
                key="teams_call_performance",
                category="meetings",
                severity="action_required",
                title="Teams call performance degraded",
                summary=f"Teams is using {snapshot.teams_cpu_pct:.0f}% CPU while system memory is at {snapshot.mem_used_pct:.0f}%. Call quality will suffer.",
                prompt="System resources are heavily loaded during a Teams session. Clearing the Teams cache and flushing DNS typically resolves lag and dropped calls.",
                recommended_fixes=["clear Teams cache via Security panel (no restart required)", "flush DNS", "close unused browser tabs and background apps", "restart Teams after cache clear"],
                auto_fix_kind="report_teams_performance",
            )
        )

    return issues


async def run_support_daemon(stop_event: asyncio.Event) -> None:
    _daemon_state["running"] = True
    while not stop_event.is_set():
        try:
            now = datetime.now(timezone.utc)
            snapshot = await asyncio.to_thread(collect_support_snapshot)
            issues = evaluate_support_snapshot(snapshot)
            _daemon_state["last_run_at"] = now.isoformat()
            _daemon_state["next_run_at"] = (now + timedelta(seconds=CHECK_INTERVAL_SECONDS)).isoformat()
            _daemon_state["last_snapshot"] = asdict(snapshot)
            _daemon_state["last_issues"] = [asdict(issue) for issue in issues]
            _daemon_state["last_error"] = ""
            await _persist_support_issues(issues)
            await process_support_fix_queue(cycle_started_at=now.isoformat())
        except Exception as exc:
            _daemon_state["last_error"] = str(exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue
    _daemon_state["running"] = False
    _daemon_state["next_run_at"] = None


async def _persist_support_issues(issues: list[SupportIssue]) -> None:
    await init_support_tables()
    seen_at = datetime.now(timezone.utc).isoformat()
    active_keys = {issue.key for issue in issues}
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM support_watch_events") as cur:
            rows = await cur.fetchall()
            current = {row["issue_key"]: dict(row) for row in rows}
        await db.execute("UPDATE support_watch_events SET active = 0")
        await db.commit()

    prepared: list[tuple[SupportIssue, str | None, str | None, int, str]] = []
    for issue in issues:
        existing = current.get(issue.key)
        task_id = existing["last_task_id"] if existing else None
        triggered_at = existing["last_triggered_at"] if existing else None
        trigger_count = existing["trigger_count"] if existing else 0
        support_severity = issue.severity

        if issue.severity != "monitoring" and _should_trigger_again(triggered_at):
            task_id, support_severity = await _ensure_support_task(issue, existing)
            if task_id:
                triggered_at = seen_at
                trigger_count += 1
        elif issue.severity != "monitoring" and existing and existing.get("last_task_id"):
            task_id = existing["last_task_id"]

        prepared.append((issue, task_id, triggered_at, trigger_count, support_severity))

    async with aiosqlite.connect(get_db_path()) as db:
        for issue, task_id, triggered_at, trigger_count, support_severity in prepared:
            await db.execute(
                """
                INSERT INTO support_watch_events (
                    issue_key, category, severity, title, summary, recommended_fixes_json,
                    auto_fix_eligible, active, last_task_id, last_seen_at, last_triggered_at, trigger_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_key) DO UPDATE SET
                    category=excluded.category,
                    severity=excluded.severity,
                    title=excluded.title,
                    summary=excluded.summary,
                    recommended_fixes_json=excluded.recommended_fixes_json,
                    auto_fix_eligible=excluded.auto_fix_eligible,
                    active=excluded.active,
                    last_task_id=excluded.last_task_id,
                    last_seen_at=excluded.last_seen_at,
                    last_triggered_at=excluded.last_triggered_at,
                    trigger_count=excluded.trigger_count
                """,
                (
                    issue.key,
                    issue.category,
                    support_severity,
                    issue.title,
                    issue.summary,
                    json.dumps(issue.recommended_fixes),
                    1 if issue.auto_fix_kind else 0,
                    1,
                    task_id,
                    seen_at,
                    triggered_at,
                    trigger_count,
                ),
            )
        for issue_key, row in current.items():
            if issue_key in active_keys:
                continue
            await db.execute(
                "UPDATE support_watch_events SET active = 0, severity = ? WHERE issue_key = ?",
                ("healthy", issue_key),
            )
        await db.commit()


async def _ensure_support_task(issue: SupportIssue, existing: dict[str, Any] | None) -> tuple[str | None, str]:
    if existing and existing.get("last_task_id"):
        existing_task = await _fetch_task(existing["last_task_id"])
        if existing_task and existing_task["status"] not in {TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_REJECTED}:
            return existing["last_task_id"], existing_task.get("support_severity", issue.severity)

    auto_fix = _auto_fix_for_issue(issue)
    support_severity = issue.severity
    detected_at = datetime.now(timezone.utc).isoformat()
    context = {
        "task_kind": "support_incident",
        "support_category": issue.category,
        "support_severity": issue.severity,
        "support_decision_reason": _decision_reason_for_issue(issue, issue.severity),
        "support_recommended_fixes": issue.recommended_fixes,
        "support_source_signal": issue.key,
        "support_detected_at": detected_at,
        "support_last_decision_at": detected_at,
        "trigger_source": "watcher",
        "auto_fix_eligible": bool(auto_fix),
        "auto_fix_attempted": False,
        "auto_fix_result": "",
    }
    if auto_fix:
        context["support_severity"] = "fix_queued"
        context["support_decision_reason"] = auto_fix["queue_reason"]
        context["auto_fix_result"] = auto_fix["queue_result"]
        support_severity = "fix_queued"
    elif issue.escalation_reason:
        context["support_severity"] = "escalated"
        context["support_decision_reason"] = issue.escalation_reason
        context["auto_fix_result"] = issue.escalation_reason
        support_severity = "escalated"

    task = await create_task(issue.prompt, task_context=context)
    async with aiosqlite.connect(get_db_path()) as db:
        await _insert_policy_event(
            db,
            task["task"]["id"],
            "support_issue_detected",
            f"{issue.title} detected.",
            {"category": issue.category, "severity": issue.severity, "signal": issue.key},
        )
        if support_severity == "fix_queued":
            await _insert_policy_event(
                db,
                task["task"]["id"],
                "support_fix_queued",
                "Safe auto-fix queued for the next daemon cycle.",
                {"category": issue.category, "signal": issue.key},
            )
        elif support_severity == "escalated":
            await _insert_policy_event(
                db,
                task["task"]["id"],
                "support_escalated",
                "Incident escalated because it may require approval or privileged handling.",
                {"category": issue.category, "signal": issue.key},
            )
        await db.commit()
    return task["task"]["id"], support_severity


async def process_support_fix_queue(cycle_started_at: str | None = None) -> int:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        where_extra = ""
        params: list[Any] = []
        if cycle_started_at:
            where_extra = " AND support_last_decision_at < ?"
            params.append(cycle_started_at)
        async with db.execute(
            f"""
            SELECT *
            FROM tasks
            WHERE task_kind = 'support_incident'
              AND support_severity = 'fix_queued'
              AND auto_fix_eligible = 1
              {where_extra}
            ORDER BY updated_at ASC
            LIMIT 10
            """,
            tuple(params),
        ) as cur:
            tasks = [dict(row) for row in await cur.fetchall()]
    applied = 0
    for task in tasks:
        if await run_support_fix(task["id"]):
            applied += 1
    return applied


async def run_support_fix(task_id: str) -> bool:
    task = await _fetch_task(task_id)
    if not task or task.get("task_kind") != "support_incident" or not task.get("auto_fix_eligible"):
        return False
    support_policy = await get_config_section("support_policy")
    if not support_policy.get("auto_fix_enabled", True):
        return False
    remediation_class = _remediation_class_for_category(task.get("support_category") or "")
    if remediation_class not in set(support_policy.get("allowed_remediation_classes", [])):
        return False

    result: dict[str, str]
    category = task.get("support_category") or ""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            UPDATE tasks
            SET auto_fix_attempted = 1, support_last_decision_at = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), task_id),
        )
        await _insert_policy_event(
            db,
            task_id,
            "support_fix_started",
            "Safe auto-fix started.",
            {"support_category": category, "platform": support_platform_id()},
        )
        await db.commit()
    if category == "disk":
        result = _apply_cleanup_candidate_fix()
    elif category in {"performance", "meetings"}:
        result = _apply_diagnostic_fix()
    elif category in {"printer_network", "camera_audio"}:
        result = _apply_readiness_refresh_fix(category)
    elif category == "windows_update":
        result = _apply_update_pending_fix()
    elif category == "printing":
        result = _apply_spooler_stopped_fix()
    elif category == "security":
        result = _apply_av_disabled_fix()
    else:
        result = {
            "support_severity": "blocked",
            "auto_fix_result": "No safe automatic remediation is allowlisted for this category. Manual review is required.",
            "next_suggested_action": "Review the incident and decide whether to escalate or create a supervised workflow.",
            "event_type": "support_fix_blocked",
            "event_message": "Safe auto-fix is not available for this incident.",
            "decision_reason": "This category has no reversible, non-privileged auto-fix in the current allowlist.",
        }
    result = _post_fix_recheck(category, result)

    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            UPDATE tasks
            SET support_severity = ?, auto_fix_attempted = 1, auto_fix_result = ?,
                support_decision_reason = ?, support_last_decision_at = ?,
                next_suggested_action = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                result["support_severity"],
                result["auto_fix_result"],
                result["decision_reason"],
                datetime.now(timezone.utc).isoformat(),
                result["next_suggested_action"],
                task_id,
            ),
        )
        await _insert_policy_event(
            db,
            task_id,
            result["event_type"],
            result["event_message"],
            {"support_category": category, "platform": support_platform_id()},
        )
        await db.commit()
    return True


async def escalate_support_incident(task_id: str) -> bool:
    task = await _fetch_task(task_id)
    if not task or task.get("task_kind") != "support_incident":
        return False
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            UPDATE tasks
            SET support_severity = 'escalated',
                support_decision_reason = ?,
                support_last_decision_at = ?,
                next_suggested_action = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                "Manual escalation requested because the issue needs review or may cross a privileged boundary.",
                datetime.now(timezone.utc).isoformat(),
                "Escalated. Review the incident in Support and use Security for supervised follow-up.",
                task_id,
            ),
        )
        await _insert_policy_event(
            db,
            task_id,
            "support_escalated",
            "Support incident escalated for manual or privileged follow-up.",
            {"platform": support_platform_id()},
        )
        await db.commit()
    return True


def _auto_fix_for_issue(issue: SupportIssue) -> dict[str, str] | None:
    if issue.auto_fix_kind == "queue_cleanup_candidates":
        return {
            "queue_result": "Cleanup candidates are queued for review in allowlisted cache, temp, and download locations. No files were deleted automatically.",
            "queue_reason": "This issue matches a reversible, non-privileged cleanup-candidate workflow.",
        }
    if issue.auto_fix_kind == "capture_diagnostics":
        return {
            "queue_result": "Diagnostics collection is queued for the next daemon cycle. No processes were terminated automatically.",
            "queue_reason": "This issue matches a deterministic diagnostics capture workflow that is safe to run locally.",
        }
    if issue.auto_fix_kind == "refresh_readiness":
        return {
            "queue_result": "A local readiness refresh is queued for the next daemon cycle.",
            "queue_reason": "This issue matches a deterministic, non-privileged readiness refresh.",
        }
    if issue.auto_fix_kind == "report_update_pending":
        return {
            "queue_result": "Windows Update reboot status captured. User will be advised to schedule a restart.",
            "queue_reason": "Reporting pending reboot state is safe and non-privileged.",
        }
    if issue.auto_fix_kind == "report_spooler_stopped":
        return {
            "queue_result": "Print Spooler outage logged. Escalation queued — service restart requires admin action.",
            "queue_reason": "Detecting a stopped service is non-privileged; restart requires IT escalation.",
        }
    if issue.auto_fix_kind == "report_av_disabled":
        return {
            "queue_result": "Antivirus status captured. Escalation queued — this is a security incident requiring immediate IT review.",
            "queue_reason": "Detecting disabled AV is non-privileged; remediation requires IT security escalation.",
        }
    return None


def _apply_update_pending_fix() -> dict[str, str]:
    return {
        "support_severity": "fixed",
        "auto_fix_result": "Windows Update reboot is pending. User has been advised to save work and restart at a convenient time. No forced restart was performed.",
        "next_suggested_action": "Remind the user to restart within 24 hours to complete updates.",
        "event_type": "support_fix_completed",
        "event_message": "Windows Update reboot-pending status reported to user.",
        "decision_reason": "Reboot-pending status detected via registry. User notified; restart is at user discretion.",
    }


def _apply_spooler_stopped_fix() -> dict[str, str]:
    return {
        "support_severity": "escalated",
        "auto_fix_result": "Print Spooler is stopped. An IT ticket has been flagged for admin-level service restart. Printing is unavailable until resolved.",
        "next_suggested_action": "IT admin should restart the Spooler service and clear any stuck print jobs.",
        "event_type": "support_escalated",
        "event_message": "Print Spooler outage escalated to IT — service restart requires admin privileges.",
        "decision_reason": "Stopped Print Spooler detected. Service restart requires elevated privileges; escalated to IT.",
    }


def _apply_av_disabled_fix() -> dict[str, str]:
    return {
        "support_severity": "escalated",
        "auto_fix_result": "Windows Defender real-time protection is disabled. This has been escalated as a security incident. IT security team should investigate immediately.",
        "next_suggested_action": "IT security should verify whether a licensed third-party AV is active or re-enable Defender.",
        "event_type": "support_escalated",
        "event_message": "Disabled antivirus escalated to IT security as a potential security incident.",
        "decision_reason": "Defender real-time protection disabled — escalated immediately as per security policy.",
    }


def _remediation_class_for_category(category: str) -> str:
    if category == "disk":
        return "cleanup_candidates"
    if category in {"performance", "meetings"}:
        return "diagnostics"
    if category in {"windows_update", "printing", "security"}:
        return "diagnostics"
    return "readiness_refresh"


async def _fetch_task(task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def _insert_policy_event(
    db: aiosqlite.Connection,
    task_id: str,
    event_type: str,
    message: str,
    metadata: dict[str, Any],
) -> None:
    await db.execute(
        """
        INSERT INTO policy_events (id, task_id, step_id, event_type, message, metadata_json)
        VALUES (hex(randomblob(16)), ?, NULL, ?, ?, ?)
        """,
        (task_id, event_type, message, json.dumps(metadata)),
    )


def _task_to_support_incident(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["id"],
        "title": task["title"],
        "summary": task["summary"],
        "status": task["status"],
        "support_category": task["support_category"],
        "support_severity": task["support_severity"],
        "decision_kind": task["support_severity"],
        "decision_reason": task["support_decision_reason"],
        "recommended_fixes": json.loads(task["support_recommended_fixes_json"] or "[]"),
        "source_signal": task["support_source_signal"],
        "detected_at": task["support_detected_at"] or task["created_at"],
        "last_decision_at": task["support_last_decision_at"] or task["updated_at"],
        "trigger_source": task["trigger_source"],
        "auto_fix_eligible": bool(task["auto_fix_eligible"]),
        "auto_fix_attempted": bool(task["auto_fix_attempted"]),
        "auto_fix_result": task["auto_fix_result"],
        "external_ticket_system": task["external_ticket_system"],
        "external_ticket_key": task["external_ticket_key"],
        "external_ticket_url": task["external_ticket_url"],
        "external_ticket_status": task["external_ticket_status"],
        "external_ticket_created_at": task["external_ticket_created_at"],
        "assigned_executor": task["assigned_executor"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "next_suggested_action": task["next_suggested_action"],
    }


def _apply_cleanup_candidate_fix() -> dict[str, str]:
    targets = allowlisted_cleanup_targets()
    summaries = []
    for path in targets[:4]:
        size_bytes = _safe_directory_size(path)
        summaries.append(f"{path.name}: {round(size_bytes / (1024 * 1024), 1)} MB")
    detail = "Prepared safe cleanup candidates in allowlisted locations."
    if summaries:
        detail += " " + " | ".join(summaries)
    return {
        "support_severity": "fixed",
        "auto_fix_result": detail,
        "next_suggested_action": "Review cleanup candidates and keep monitoring disk pressure.",
        "event_type": "support_fix_completed",
        "event_message": "Prepared cleanup candidates for allowlisted temp/cache paths.",
        "decision_reason": "A safe cleanup-candidate workflow completed without deleting files or requiring privileges.",
    }


def _apply_diagnostic_fix() -> dict[str, str]:
    processes = read_processes()
    heaviest = sorted(processes, key=lambda item: item.get("rss_kb", 0), reverse=True)[:3]
    summary = ", ".join(f"{proc['name']} ({round(proc['rss_kb'] / 1024, 1)} MB)" for proc in heaviest) if heaviest else "no process details captured"
    return {
        "support_severity": "fixed",
        "auto_fix_result": f"Captured local diagnostics and refreshed the support record. Top processes: {summary}.",
        "next_suggested_action": "Review the captured diagnostics and continue monitoring for recurrence.",
        "event_type": "support_fix_completed",
        "event_message": "Captured local diagnostics for safe remediation.",
        "decision_reason": "A deterministic diagnostics capture completed successfully and remained within the safe local allowlist.",
    }


def _apply_readiness_refresh_fix(category: str) -> dict[str, str]:
    label = "network/printer" if category == "printer_network" else "camera/audio"
    return {
        "support_severity": "fixed",
        "auto_fix_result": f"Refreshed {label} readiness checks and updated the local support record. No privileged actions were performed.",
        "next_suggested_action": "Review the refreshed readiness state and continue monitoring.",
        "event_type": "support_fix_completed",
        "event_message": f"Refreshed {label} readiness state.",
        "decision_reason": "A deterministic readiness refresh completed successfully and remained within the safe local allowlist.",
    }


def _decision_reason_for_issue(issue: SupportIssue, severity: str) -> str:
    if severity == "monitoring":
        return "The signal crossed an early-warning threshold but remains below the action boundary."
    if issue.escalation_reason:
        return issue.escalation_reason
    if issue.auto_fix_kind:
        return "The issue crossed the action boundary and matches a safe non-privileged remediation pattern."
    return "The issue crossed the action boundary but needs user review because no safe automatic remediation is allowlisted."


def _post_fix_recheck(category: str, result: dict[str, str]) -> dict[str, str]:
    snapshot = collect_support_snapshot()
    updated = dict(result)
    if category == "disk" and snapshot.disk_used_pct >= 80:
        updated["support_severity"] = "monitoring"
        updated["auto_fix_result"] += " Disk pressure is still elevated, so Caret moved the incident back to monitoring."
        updated["next_suggested_action"] = "Review the cleanup candidates and consider creating an IT ticket if storage pressure remains high."
        updated["decision_reason"] = "The safe remediation prepared cleanup candidates, but disk pressure remains above the action threshold."
        return updated
    if category in {"performance", "meetings"} and max(snapshot.cpu_load_pct, snapshot.mem_used_pct, snapshot.teams_cpu_pct) >= 75:
        updated["support_severity"] = "monitoring"
        updated["auto_fix_result"] += " Load is still elevated, so Caret is keeping the issue under monitoring."
        updated["next_suggested_action"] = "Review diagnostics and escalate if the issue continues."
        updated["decision_reason"] = "Diagnostics completed, but the machine is still under visible load."
        return updated
    if category == "printer_network" and not snapshot.printer_ready:
        updated["support_severity"] = "escalated"
        updated["auto_fix_result"] += " Printer readiness is still degraded after the refresh."
        updated["next_suggested_action"] = "Escalate the incident or create an IT ticket for network or printer follow-up."
        updated["decision_reason"] = "Readiness refresh completed, but the printer/network signal is still missing."
        return updated
    if category == "camera_audio" and not snapshot.camera_ready:
        updated["support_severity"] = "escalated"
        updated["auto_fix_result"] += " Camera/audio readiness is still degraded after the refresh."
        updated["next_suggested_action"] = "Escalate the incident or create an IT ticket for media-device follow-up."
        updated["decision_reason"] = "Readiness refresh completed, but the media readiness signal is still missing."
        return updated
    return updated


def _safe_directory_size(path: Path) -> int:
    total = 0
    try:
        if not path.exists() or not path.is_dir():
            return 0
        for item in path.iterdir():
            try:
                if item.is_file():
                    total += item.stat().st_size
                elif item.is_dir():
                    total += sum(child.stat().st_size for child in item.rglob("*") if child.is_file())
            except Exception:
                continue
    except Exception:
        return 0
    return total


def _should_trigger_again(last_triggered_at: str | None) -> bool:
    if not last_triggered_at:
        return True
    try:
        then = datetime.fromisoformat(last_triggered_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - then >= timedelta(minutes=TRIGGER_COOLDOWN_MINUTES)


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        existing = {row[1] for row in await cur.fetchall()}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
