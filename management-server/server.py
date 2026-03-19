"""Caret Management Server — central fleet dashboard.

Receives checkins from Caret clients, stores in SQLite, exposes REST API
and a simple HTML fleet dashboard.

Run:
    pip install fastapi uvicorn
    python server.py

Environment:
    CARET_MANAGEMENT_TOKEN   — bearer token clients must send (leave blank to disable auth)
    CARET_SERVER_PORT        — port to listen on (default 8100)
    CARET_DB_PATH            — SQLite file path (default ./fleet.db)
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TOKEN = os.environ.get("CARET_MANAGEMENT_TOKEN", "").strip()
DB_PATH = Path(os.environ.get("CARET_DB_PATH", "fleet.db"))
PORT = int(os.environ.get("CARET_SERVER_PORT", "8100"))

app = FastAPI(title="Caret Management Server", version="1.0.0")
_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def _init_db() -> None:
    with _db() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                hostname        TEXT PRIMARY KEY,
                caret_version   TEXT,
                last_seen       TEXT,
                cpu_pct         REAL,
                mem_used_pct    REAL,
                disk_used_pct   REAL,
                open_incidents  INTEGER DEFAULT 0,
                compliance_issues INTEGER DEFAULT 0,
                extra           TEXT
            );
            CREATE TABLE IF NOT EXISTS checkins (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname    TEXT,
                ts          TEXT,
                payload     TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_checkins_host ON checkins(hostname);
        """)


@contextmanager
def _db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _check_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if not TOKEN:
        return  # auth disabled
    if creds is None or creds.credentials != TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _device_status(last_seen_iso: str) -> str:
    try:
        last = datetime.fromisoformat(last_seen_iso)
        age = datetime.now(timezone.utc) - last
        if age < timedelta(minutes=3):
            return "online"
        if age < timedelta(minutes=15):
            return "stale"
        return "offline"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------
@app.post("/v1/devices/checkin", dependencies=[Depends(_check_auth)])
async def checkin(request: Request) -> dict:
    body: dict[str, Any] = await request.json()
    hostname = body.get("hostname", "unknown")
    ts = body.get("timestamp") or datetime.now(timezone.utc).isoformat()
    health = body.get("health", {})
    cpu = float(health.get("cpu_pct", 0))
    mem = float(health.get("mem_used_pct", 0))
    disk = float(health.get("disk_used_pct", 0))
    incidents = int(body.get("open_incidents", 0))
    compliance = int(body.get("compliance_issues", 0))
    version = body.get("caret_version", "")

    with _db() as con:
        con.execute("""
            INSERT INTO devices (hostname, caret_version, last_seen, cpu_pct, mem_used_pct,
                                 disk_used_pct, open_incidents, compliance_issues, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(hostname) DO UPDATE SET
                caret_version=excluded.caret_version,
                last_seen=excluded.last_seen,
                cpu_pct=excluded.cpu_pct,
                mem_used_pct=excluded.mem_used_pct,
                disk_used_pct=excluded.disk_used_pct,
                open_incidents=excluded.open_incidents,
                compliance_issues=excluded.compliance_issues,
                extra=excluded.extra
        """, (hostname, version, ts, cpu, mem, disk, incidents, compliance, json.dumps(body)))
        con.execute(
            "INSERT INTO checkins (hostname, ts, payload) VALUES (?, ?, ?)",
            (hostname, ts, json.dumps(body)),
        )
    return {"ok": True}


@app.get("/v1/devices", dependencies=[Depends(_check_auth)])
def list_devices() -> list[dict]:
    with _db() as con:
        rows = con.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["status"] = _device_status(d["last_seen"])
        d.pop("extra", None)
        result.append(d)
    return result


@app.get("/v1/devices/{hostname}", dependencies=[Depends(_check_auth)])
def device_detail(hostname: str) -> dict:
    with _db() as con:
        row = con.execute("SELECT * FROM devices WHERE hostname=?", (hostname,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Device not found")
        recent = con.execute(
            "SELECT ts, payload FROM checkins WHERE hostname=? ORDER BY ts DESC LIMIT 20",
            (hostname,),
        ).fetchall()
    d = dict(row)
    d["status"] = _device_status(d["last_seen"])
    d["recent_checkins"] = [{"ts": r["ts"], **json.loads(r["payload"])} for r in recent]
    return d


@app.get("/v1/fleet/summary", dependencies=[Depends(_check_auth)])
def fleet_summary() -> dict:
    with _db() as con:
        rows = con.execute("SELECT * FROM devices").fetchall()
    devices = [dict(r) for r in rows]
    statuses = [_device_status(d["last_seen"]) for d in devices]
    return {
        "total": len(devices),
        "online": statuses.count("online"),
        "stale": statuses.count("stale"),
        "offline": statuses.count("offline"),
        "with_incidents": sum(1 for d in devices if d["open_incidents"] > 0),
        "with_compliance_issues": sum(1 for d in devices if d["compliance_issues"] > 0),
        "avg_cpu_pct": round(sum(d["cpu_pct"] for d in devices) / len(devices), 1) if devices else 0,
        "avg_mem_pct": round(sum(d["mem_used_pct"] for d in devices) / len(devices), 1) if devices else 0,
    }


# ---------------------------------------------------------------------------
# Routes — Dashboard HTML
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Caret Fleet Dashboard</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a;
    --text: #e2e8f0; --muted: #64748b;
    --green: #22c55e; --amber: #f59e0b; --red: #ef4444; --purple: #8b5cf6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; font-size: 14px; }
  header { padding: 16px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; font-weight: 600; }
  .logo { width: 28px; height: 28px; }
  #summary { display: flex; gap: 12px; padding: 20px 24px; flex-wrap: wrap; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
          padding: 14px 20px; min-width: 120px; }
  .stat-val { font-size: 28px; font-weight: 700; line-height: 1; }
  .stat-label { color: var(--muted); font-size: 12px; margin-top: 4px; }
  .online { color: var(--green); } .stale { color: var(--amber); } .offline { color: var(--red); }
  .warn { color: var(--amber); }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 10px 16px; color: var(--muted); font-weight: 500;
       font-size: 11px; text-transform: uppercase; border-bottom: 1px solid var(--border); }
  td { padding: 10px 16px; border-bottom: 1px solid var(--border); }
  tr:hover td { background: var(--surface); cursor: pointer; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
  .badge-online { background: #14532d; color: var(--green); }
  .badge-stale  { background: #451a03; color: var(--amber); }
  .badge-offline{ background: #450a0a; color: var(--red); }
  .bar-wrap { width: 80px; height: 6px; background: var(--border); border-radius: 3px; display:inline-block; vertical-align: middle; }
  .bar { height: 100%; border-radius: 3px; }
  #devices-wrap { padding: 0 24px 24px; }
  #last-updated { color: var(--muted); font-size: 11px; padding: 0 24px 8px; }
  .section-title { font-size: 13px; font-weight: 600; color: var(--muted); padding: 0 24px 12px; }
</style>
</head>
<body>
<header>
  <svg class="logo" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#a855f7"/><stop offset="100%" stop-color="#6366f1"/>
    </linearGradient></defs>
    <polygon points="50,5 95,27.5 95,72.5 50,95 5,72.5 5,27.5" fill="url(#g)" opacity="0.15"/>
    <polygon points="50,5 95,27.5 95,72.5 50,95 5,72.5 5,27.5" fill="none" stroke="url(#g)" stroke-width="3"/>
    <polygon points="50,20 80,35 80,65 50,80 20,65 20,35" fill="url(#g)" opacity="0.3"/>
    <circle cx="50" cy="50" r="12" fill="url(#g)"/>
  </svg>
  <h1>Caret Fleet Dashboard</h1>
  <span id="summary-badge" style="margin-left:auto; color: var(--muted); font-size:12px;"></span>
</header>

<div id="summary"></div>
<div id="last-updated"></div>
<div class="section-title">DEVICES</div>
<div id="devices-wrap">
  <table id="devices-table">
    <thead><tr>
      <th>Hostname</th><th>Status</th><th>Version</th>
      <th>CPU</th><th>Memory</th><th>Disk</th>
      <th>Incidents</th><th>Compliance</th><th>Last Seen</th>
    </tr></thead>
    <tbody id="devices-body"><tr><td colspan="9" style="color:var(--muted); text-align:center; padding:32px">Loading…</td></tr></tbody>
  </table>
</div>

<script>
const TOKEN = localStorage.getItem('caret_mgmt_token') || '';

async function api(path) {
  const headers = TOKEN ? { Authorization: 'Bearer ' + TOKEN } : {};
  const res = await fetch(path, { headers });
  if (res.status === 401) {
    const t = prompt('Management server token:');
    if (t) { localStorage.setItem('caret_mgmt_token', t); location.reload(); }
    return null;
  }
  return res.json();
}

function bar(pct, warn=70, crit=90) {
  const color = pct >= crit ? '#ef4444' : pct >= warn ? '#f59e0b' : '#22c55e';
  return `<span class="bar-wrap"><span class="bar" style="width:${Math.min(pct,100)}%;background:${color}"></span></span> ${pct.toFixed(0)}%`;
}

function relTime(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60) return diff + 's ago';
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
  return Math.floor(diff/86400) + 'd ago';
}

async function refresh() {
  const [summary, devices] = await Promise.all([api('/v1/fleet/summary'), api('/v1/devices')]);
  if (!summary || !devices) return;

  document.getElementById('summary').innerHTML = `
    <div class="stat"><div class="stat-val">${summary.total}</div><div class="stat-label">Total devices</div></div>
    <div class="stat"><div class="stat-val online">${summary.online}</div><div class="stat-label">Online</div></div>
    <div class="stat"><div class="stat-val stale">${summary.stale}</div><div class="stat-label">Stale (&gt;3m)</div></div>
    <div class="stat"><div class="stat-val offline">${summary.offline}</div><div class="stat-label">Offline</div></div>
    <div class="stat"><div class="stat-val warn">${summary.with_incidents}</div><div class="stat-label">Open incidents</div></div>
    <div class="stat"><div class="stat-val warn">${summary.with_compliance_issues}</div><div class="stat-label">Compliance issues</div></div>
    <div class="stat"><div class="stat-val">${summary.avg_cpu_pct}%</div><div class="stat-label">Avg CPU</div></div>
    <div class="stat"><div class="stat-val">${summary.avg_mem_pct}%</div><div class="stat-label">Avg Memory</div></div>
  `;

  document.getElementById('last-updated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();

  const tbody = document.getElementById('devices-body');
  if (!devices.length) {
    tbody.innerHTML = '<tr><td colspan="9" style="color:var(--muted);text-align:center;padding:32px">No devices checked in yet.</td></tr>';
    return;
  }
  tbody.innerHTML = devices.map(d => `
    <tr onclick="location.href='/v1/devices/${encodeURIComponent(d.hostname)}'">
      <td><strong>${d.hostname}</strong></td>
      <td><span class="badge badge-${d.status}">${d.status}</span></td>
      <td style="color:var(--muted)">${d.caret_version || '—'}</td>
      <td>${bar(d.cpu_pct)}</td>
      <td>${bar(d.mem_used_pct)}</td>
      <td>${bar(d.disk_used_pct)}</td>
      <td style="color:${d.open_incidents > 0 ? 'var(--amber)' : 'var(--green)'}">${d.open_incidents}</td>
      <td style="color:${d.compliance_issues > 0 ? 'var(--amber)' : 'var(--green)'}">${d.compliance_issues}</td>
      <td style="color:var(--muted)">${relTime(d.last_seen)}</td>
    </tr>
  `).join('');
}

refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    _init_db()
    print(f"Caret Management Server starting on port {PORT}")
    print(f"Dashboard: http://localhost:{PORT}/")
    print(f"Auth: {'enabled' if TOKEN else 'DISABLED — set CARET_MANAGEMENT_TOKEN'}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
