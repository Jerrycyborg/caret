import aiosqlite
import os
from pathlib import Path

DB_PATH = Path(os.environ.get("OXY_DB_PATH", str(Path.home() / ".oxy" / "oxy.db")))


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT 'ollama/llama3.2',
                channel_type TEXT NOT NULL DEFAULT 'desktop',
                channel_user_id TEXT,
                channel_thread_id TEXT,
                session_status TEXT NOT NULL DEFAULT 'active',
                last_task_id TEXT,
                last_executor TEXT,
                last_agent_state TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                provider TEXT PRIMARY KEY,
                key_value TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                section TEXT PRIMARY KEY,
                value_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                prompt TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                task_class TEXT NOT NULL DEFAULT 'general_local_assistance',
                execution_domain TEXT NOT NULL DEFAULT 'local_device',
                reporting_target TEXT NOT NULL DEFAULT 'oxy',
                approval_scope TEXT NOT NULL DEFAULT 'none',
                assigned_executor TEXT NOT NULL DEFAULT 'local_device_executor',
                result_channel TEXT NOT NULL DEFAULT 'session',
                task_kind TEXT NOT NULL DEFAULT 'workflow_task',
                support_category TEXT,
                support_severity TEXT NOT NULL DEFAULT 'healthy',
                support_decision_reason TEXT NOT NULL DEFAULT '',
                support_recommended_fixes_json TEXT NOT NULL DEFAULT '[]',
                support_source_signal TEXT NOT NULL DEFAULT '',
                support_detected_at TEXT,
                support_last_decision_at TEXT,
                trigger_source TEXT NOT NULL DEFAULT 'manual',
                auto_fix_eligible INTEGER NOT NULL DEFAULT 0,
                auto_fix_attempted INTEGER NOT NULL DEFAULT 0,
                auto_fix_result TEXT NOT NULL DEFAULT '',
                external_ticket_system TEXT NOT NULL DEFAULT '',
                external_ticket_key TEXT NOT NULL DEFAULT '',
                external_ticket_url TEXT NOT NULL DEFAULT '',
                external_ticket_status TEXT NOT NULL DEFAULT '',
                external_ticket_created_at TEXT,
                risk_level TEXT NOT NULL DEFAULT 'read',
                next_suggested_action TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                workspace_root TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_steps (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                tool_id TEXT,
                risk_level TEXT NOT NULL,
                approval_required INTEGER NOT NULL DEFAULT 0,
                depends_on_step_id TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                payload_json TEXT NOT NULL DEFAULT '{}',
                rollback_note TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (depends_on_step_id) REFERENCES task_steps(id) ON DELETE SET NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                target TEXT NOT NULL DEFAULT '',
                tool_name TEXT NOT NULL DEFAULT '',
                risk_level TEXT NOT NULL DEFAULT 'read',
                approval_scope TEXT NOT NULL DEFAULT 'task',
                reason TEXT NOT NULL DEFAULT '',
                rollback_note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (step_id) REFERENCES task_steps(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (step_id) REFERENCES task_steps(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tool_runs (
                id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                input_json TEXT NOT NULL DEFAULT '{}',
                output_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS policy_events (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_id TEXT,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (step_id) REFERENCES task_steps(id) ON DELETE SET NULL
            )
        """)
        await _ensure_column(db, "tasks", "summary", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "risk_level", "TEXT NOT NULL DEFAULT 'read'")
        await _ensure_column(db, "tasks", "next_suggested_action", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "task_steps", "depends_on_step_id", "TEXT")
        await _ensure_column(db, "approvals", "label", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "approvals", "target", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "approvals", "tool_name", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "approvals", "risk_level", "TEXT NOT NULL DEFAULT 'read'")
        await _ensure_column(db, "approvals", "approval_scope", "TEXT NOT NULL DEFAULT 'task'")
        await _ensure_column(db, "approvals", "reason", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "approvals", "rollback_note", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "conversations", "channel_type", "TEXT NOT NULL DEFAULT 'desktop'")
        await _ensure_column(db, "conversations", "channel_user_id", "TEXT")
        await _ensure_column(db, "conversations", "channel_thread_id", "TEXT")
        await _ensure_column(db, "conversations", "session_status", "TEXT NOT NULL DEFAULT 'active'")
        await _ensure_column(db, "conversations", "last_task_id", "TEXT")
        await _ensure_column(db, "conversations", "last_executor", "TEXT")
        await _ensure_column(db, "conversations", "last_agent_state", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "task_class", "TEXT NOT NULL DEFAULT 'general_local_assistance'")
        await _ensure_column(db, "tasks", "execution_domain", "TEXT NOT NULL DEFAULT 'local_device'")
        await _ensure_column(db, "tasks", "reporting_target", "TEXT NOT NULL DEFAULT 'oxy'")
        await _ensure_column(db, "tasks", "approval_scope", "TEXT NOT NULL DEFAULT 'none'")
        await _ensure_column(db, "tasks", "assigned_executor", "TEXT NOT NULL DEFAULT 'local_device_executor'")
        await _ensure_column(db, "tasks", "result_channel", "TEXT NOT NULL DEFAULT 'session'")
        await _ensure_column(db, "tasks", "task_kind", "TEXT NOT NULL DEFAULT 'workflow_task'")
        await _ensure_column(db, "tasks", "support_category", "TEXT")
        await _ensure_column(db, "tasks", "support_severity", "TEXT NOT NULL DEFAULT 'healthy'")
        await _ensure_column(db, "tasks", "support_decision_reason", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "support_recommended_fixes_json", "TEXT NOT NULL DEFAULT '[]'")
        await _ensure_column(db, "tasks", "support_source_signal", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "support_detected_at", "TEXT")
        await _ensure_column(db, "tasks", "support_last_decision_at", "TEXT")
        await _ensure_column(db, "tasks", "trigger_source", "TEXT NOT NULL DEFAULT 'manual'")
        await _ensure_column(db, "tasks", "auto_fix_eligible", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "tasks", "auto_fix_attempted", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "tasks", "auto_fix_result", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "external_ticket_system", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "external_ticket_key", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "external_ticket_url", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "external_ticket_status", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "tasks", "external_ticket_created_at", "TEXT")
        await db.commit()


def get_db_path() -> str:
    return str(DB_PATH)


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str):
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        columns = await cur.fetchall()
    existing = {row[1] for row in columns}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
