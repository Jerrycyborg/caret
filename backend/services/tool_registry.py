from __future__ import annotations

import asyncio
import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
BUILD_COMMAND_PREFIXES = {"npm", "pnpm", "cargo", "python", "python3", "docker"}
SHELL_COMMAND_PREFIXES = {"rg", "ls", "cat", "sed", "head", "tail", "pwd", "find", "git", "stat", "wc"}


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    description: str
    risk_level: str
    approval_required: bool
    executor_type: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    rollback_hint: str


def tool_registry() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            id="file.read",
            description="Read a UTF-8 file from the workspace.",
            risk_level="read",
            approval_required=False,
            executor_type="python",
            input_schema={"path": "relative/path"},
            output_schema={"path": "relative/path", "content": "text"},
            rollback_hint="No rollback needed for reads.",
        ),
        ToolDefinition(
            id="file.write",
            description="Write UTF-8 text to a workspace file.",
            risk_level="write",
            approval_required=True,
            executor_type="python",
            input_schema={"path": "relative/path", "content": "text"},
            output_schema={"path": "relative/path", "bytes_written": 0},
            rollback_hint="Restore the previous file contents from version control or backup.",
        ),
        ToolDefinition(
            id="shell.run",
            description="Run a bounded local diagnostic command without shell interpolation.",
            risk_level="write",
            approval_required=True,
            executor_type="subprocess",
            input_schema={"command": "rg TODO src", "cwd": "optional/relative/path"},
            output_schema=_execution_schema(),
            rollback_hint="Review command effects manually. This executor is intentionally bounded.",
        ),
        ToolDefinition(
            id="build.run",
            description="Run an allowlisted local build command.",
            risk_level="write",
            approval_required=True,
            executor_type="subprocess",
            input_schema={"command": "npm run build", "cwd": "optional/relative/path"},
            output_schema=_execution_schema(),
            rollback_hint="Revert generated artifacts or working tree changes if needed.",
        ),
        ToolDefinition(
            id="git.status",
            description="Read repository status.",
            risk_level="read",
            approval_required=False,
            executor_type="subprocess",
            input_schema={"cwd": "optional/relative/path"},
            output_schema=_execution_schema(),
            rollback_hint="No rollback needed for reads.",
        ),
        ToolDefinition(
            id="git.diff",
            description="Read repository diff statistics.",
            risk_level="read",
            approval_required=False,
            executor_type="subprocess",
            input_schema={"cwd": "optional/relative/path"},
            output_schema=_execution_schema(),
            rollback_hint="No rollback needed for reads.",
        ),
        ToolDefinition(
            id="project.search",
            description="Search the workspace with ripgrep.",
            risk_level="read",
            approval_required=False,
            executor_type="subprocess",
            input_schema={"query": "text", "cwd": "optional/relative/path"},
            output_schema=_execution_schema(),
            rollback_hint="No rollback needed for reads.",
        ),
        ToolDefinition(
            id="project.tree",
            description="List a compact workspace tree.",
            risk_level="read",
            approval_required=False,
            executor_type="python",
            input_schema={"path": "optional/relative/path", "max_entries": 50},
            output_schema={"status": "ok|failed", "artifacts": {"entries": []}},
            rollback_hint="No rollback needed for reads.",
        ),
        ToolDefinition(
            id="project.read_many",
            description="Read multiple UTF-8 workspace files.",
            risk_level="read",
            approval_required=False,
            executor_type="python",
            input_schema={"paths": ["relative/path"]},
            output_schema={"status": "ok|failed", "artifacts": {"files": []}},
            rollback_hint="No rollback needed for reads.",
        ),
        ToolDefinition(
            id="git.log",
            description="Read recent git history.",
            risk_level="read",
            approval_required=False,
            executor_type="subprocess",
            input_schema={"cwd": "optional/relative/path"},
            output_schema=_execution_schema(),
            rollback_hint="No rollback needed for reads.",
        ),
        ToolDefinition(
            id="git.show",
            description="Read a compact git show for HEAD.",
            risk_level="read",
            approval_required=False,
            executor_type="subprocess",
            input_schema={"cwd": "optional/relative/path"},
            output_schema=_execution_schema(),
            rollback_hint="No rollback needed for reads.",
        ),
    ]


def get_tool_definition(tool_id: str) -> ToolDefinition:
    for tool in tool_registry():
        if tool.id == tool_id:
            return tool
    raise ValueError(f"Unknown tool '{tool_id}'")


def resolve_workspace_path(path: str) -> Path:
    candidate = (WORKSPACE_ROOT / path).resolve()
    if not str(candidate).startswith(str(WORKSPACE_ROOT)):
        raise ValueError("Path escapes the workspace root.")
    return candidate


def resolve_cwd(cwd: str | None) -> Path:
    return WORKSPACE_ROOT if not cwd else resolve_workspace_path(cwd)


async def execute_tool(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_id == "file.read":
        path = resolve_workspace_path(str(payload.get("path", "")))
        return _result(
            stdout=path.read_text(encoding="utf-8"),
            artifacts={"path": str(path.relative_to(WORKSPACE_ROOT))},
            user_message=f"Read {path.relative_to(WORKSPACE_ROOT)}.",
        )
    if tool_id == "file.write":
        path = resolve_workspace_path(str(payload.get("path", "")))
        content = str(payload.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return _result(
            artifacts={
                "path": str(path.relative_to(WORKSPACE_ROOT)),
                "bytes_written": len(content.encode("utf-8")),
            },
            user_message=f"Wrote {path.relative_to(WORKSPACE_ROOT)}.",
        )
    if tool_id == "git.status":
        return await _run_exec(["git", "status", "--short", "--branch"], resolve_cwd(payload.get("cwd")))
    if tool_id == "git.diff":
        return await _run_exec(["git", "diff", "--stat"], resolve_cwd(payload.get("cwd")))
    if tool_id == "git.log":
        return await _run_exec(["git", "log", "--oneline", "-5"], resolve_cwd(payload.get("cwd")))
    if tool_id == "git.show":
        return await _run_exec(["git", "show", "--stat", "--oneline", "--summary", "HEAD"], resolve_cwd(payload.get("cwd")))
    if tool_id == "project.search":
        query = str(payload.get("query", "")).strip()
        if not query:
            raise ValueError("Search query cannot be empty.")
        return await _run_exec(["rg", "--line-number", "--smart-case", query], resolve_cwd(payload.get("cwd")))
    if tool_id == "project.tree":
        root = resolve_workspace_path(str(payload.get("path", ".")))
        max_entries = int(payload.get("max_entries", 50))
        entries = []
        for path in sorted(root.rglob("*")):
            if len(entries) >= max_entries:
                break
            rel = path.relative_to(WORKSPACE_ROOT)
            if any(part.startswith(".git") or part == "node_modules" for part in rel.parts):
                continue
            entries.append({"path": str(rel), "type": "dir" if path.is_dir() else "file"})
        return _result(
            artifacts={"entries": entries},
            user_message=f"Listed {len(entries)} workspace entries.",
        )
    if tool_id == "project.read_many":
        raw_paths = payload.get("paths", [])
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValueError("paths must be a non-empty list.")
        files = []
        for raw_path in raw_paths[:5]:
            path = resolve_workspace_path(str(raw_path))
            if not path.exists() or path.is_dir():
                continue
            files.append(
                {
                    "path": str(path.relative_to(WORKSPACE_ROOT)),
                    "content": path.read_text(encoding="utf-8"),
                }
            )
        return _result(
            artifacts={"files": files},
            user_message=f"Read {len(files)} files.",
        )
    if tool_id == "shell.run":
        command = _parse_command(str(payload.get("command", "")))
        if command[0] not in SHELL_COMMAND_PREFIXES:
            raise ValueError("shell.run only supports bounded diagnostic commands.")
        return await _run_exec(command, resolve_cwd(payload.get("cwd")))
    if tool_id == "build.run":
        command = _parse_command(str(payload.get("command", "")))
        if command[0] not in BUILD_COMMAND_PREFIXES:
            raise ValueError("build.run only supports npm, pnpm, cargo, python, python3, or docker.")
        return await _run_exec(command, resolve_cwd(payload.get("cwd")))
    raise ValueError(f"Unknown tool '{tool_id}'")


def registry_payload() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.id,
            "description": tool.description,
            "risk_level": tool.risk_level,
            "approval_required": tool.approval_required,
            "executor_type": tool.executor_type,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "rollback_hint": tool.rollback_hint,
        }
        for tool in tool_registry()
    ]


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _parse_command(command: str) -> list[str]:
    parts = shlex.split(command)
    if not parts:
        raise ValueError("Command cannot be empty.")
    return parts


async def _run_exec(args: list[str], cwd: Path) -> dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return _result(
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        exit_code=process.returncode,
        artifacts={"command": args, "cwd": str(cwd.relative_to(WORKSPACE_ROOT))},
        user_message=f"Command finished with exit code {process.returncode}.",
    )


def _result(
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    artifacts: dict[str, Any] | None = None,
    user_message: str = "",
) -> dict[str, Any]:
    return {
        "status": "ok" if exit_code == 0 else "failed",
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "artifacts": artifacts or {},
        "user_message": user_message,
    }


def _execution_schema() -> dict[str, Any]:
    return {
        "status": "ok|failed",
        "stdout": "text",
        "stderr": "text",
        "exit_code": 0,
        "artifacts": {},
        "user_message": "text",
    }
