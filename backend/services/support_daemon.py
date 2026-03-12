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
from services.orchestrator import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_REJECTED,
    create_task,
)
from services.support_platform import (
    allowlisted_cleanup_targets,
    collect_cpu_load_pct,
    collect_memory_used_pct,
    count_active_connections,
    read_processes,
    support_platform_id,
)

CHECK_INTERVAL_SECONDS = int(os.environ.get("OXY_SUPPORT_DAEMON_INTERVAL", "300"))
TRIGGER_COOLDOWN_MINUTES = int(os.environ.get("OXY_SUPPORT_DAEMON_COOLDOWN_MINUTES", "360"))

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
                "summary": row["summary"],
                "recommended_fixes": fixes,
                "last_task_id": row["last_task_id"],
                "trigger_count": row["trigger_count"],
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
    return SupportSnapshot(
        disk_used_pct=round(disk_used_pct, 2),
        cpu_load_pct=round(cpu_load_pct, 2),
        teams_cpu_pct=round(teams_cpu_pct, 2),
        active_connections=active_connections,
        mem_used_pct=round(mem_used_pct, 2),
        camera_ready=camera_ready,
        printer_ready=printer_ready,
        background_heavy_count=background_heavy_count,
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
                severity="escalated",
                title="Camera and audio readiness",
                summary="Meeting activity is present but no camera/audio service signal was detected.",
                prompt="Inspect camera/audio readiness and prepare supervised remediation before the next meeting.",
                recommended_fixes=["check media permissions", "inspect audio/video helper services"],
                escalation_reason="Camera or audio readiness may require privileged or permission-sensitive intervention.",
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
                severity="monitoring",
                title="Printer and network readiness",
                summary=f"Detected {snapshot.active_connections} active connections and no printer service signal.",
                prompt="Monitor printer/network readiness and prepare diagnosis if connectivity degrades.",
                recommended_fixes=["watch network-heavy apps", "inspect printer/network service availability"],
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
            await process_support_fix_queue()
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
    context = {
        "task_kind": "support_incident",
        "support_category": issue.category,
        "support_severity": issue.severity,
        "trigger_source": "watcher",
        "auto_fix_eligible": bool(auto_fix),
        "auto_fix_attempted": bool(auto_fix),
        "auto_fix_result": "",
    }
    if auto_fix:
        context["support_severity"] = auto_fix["support_severity"]
        context["auto_fix_result"] = auto_fix["result"]
        support_severity = auto_fix["support_severity"]
    elif issue.escalation_reason:
        context["support_severity"] = "escalated"
        context["auto_fix_result"] = issue.escalation_reason
        support_severity = "escalated"

    task = await create_task(issue.prompt, task_context=context)
    return task["task"]["id"], support_severity


async def process_support_fix_queue() -> int:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT *
            FROM tasks
            WHERE task_kind = 'support_incident'
              AND support_severity = 'fix_queued'
              AND auto_fix_eligible = 1
            ORDER BY updated_at ASC
            LIMIT 10
            """
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

    result: dict[str, str]
    category = task.get("support_category") or ""
    if category == "disk":
        result = _apply_cleanup_candidate_fix()
    elif category in {"performance", "meetings"}:
        result = _apply_diagnostic_fix()
    else:
        result = {
            "support_severity": "blocked",
            "auto_fix_result": "No safe automatic remediation is allowlisted for this category. Manual review is required.",
            "next_suggested_action": "Review the incident and decide whether to escalate or create a supervised workflow.",
            "event_type": "support_fix_blocked",
            "event_message": "Safe auto-fix is not available for this incident.",
        }

    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            UPDATE tasks
            SET support_severity = ?, auto_fix_attempted = 1, auto_fix_result = ?,
                next_suggested_action = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                result["support_severity"],
                result["auto_fix_result"],
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
                next_suggested_action = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            ("Escalated. Review the incident in Support and use Security or Workflows for supervised follow-up.", task_id),
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
            "support_severity": "fix_queued",
            "result": "Prepared cleanup candidates for cache, temp, downloads, and build output review. No files were deleted automatically.",
        }
    if issue.auto_fix_kind == "capture_diagnostics":
        return {
            "support_severity": "fix_queued",
            "result": "Captured local diagnostics and queued supervised remediation. No processes were terminated automatically.",
        }
    return None


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
        "trigger_source": task["trigger_source"],
        "auto_fix_eligible": bool(task["auto_fix_eligible"]),
        "auto_fix_attempted": bool(task["auto_fix_attempted"]),
        "auto_fix_result": task["auto_fix_result"],
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
        "event_type": "support_fix_applied",
        "event_message": "Prepared cleanup candidates for allowlisted temp/cache paths.",
    }


def _apply_diagnostic_fix() -> dict[str, str]:
    processes = read_processes()
    heaviest = sorted(processes, key=lambda item: item.get("rss_kb", 0), reverse=True)[:3]
    summary = ", ".join(f"{proc['name']} ({round(proc['rss_kb'] / 1024, 1)} MB)" for proc in heaviest) if heaviest else "no process details captured"
    return {
        "support_severity": "fixed",
        "auto_fix_result": f"Captured local diagnostics and refreshed the support record. Top processes: {summary}.",
        "next_suggested_action": "Review the captured diagnostics and continue monitoring for recurrence.",
        "event_type": "support_fix_applied",
        "event_message": "Captured local diagnostics for safe remediation.",
    }


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
