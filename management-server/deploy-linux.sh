#!/bin/bash
# Caret Management Server — Linux deployment script
# Run as root on the ISPConfig server:
#   wget https://raw.githubusercontent.com/.../deploy-linux.sh
#   chmod +x deploy-linux.sh && sudo ./deploy-linux.sh
#
# Required env vars (set before running, or pass inline):
#   CARET_TOKEN    — bearer token for API auth
#   CARET_DOMAIN   — domain name (e.g. caret.tws-partners.com)
#
# Options:
#   --port PORT    — port to listen on (default 8100)
#   --uninstall    — remove the service and files
#   --keep-db      — with --uninstall: preserve fleet.db (copies to /tmp/caret-fleet.db)
#   --yes          — skip confirmation prompts (non-interactive / CI use)

set -e

# ── Defaults ──────────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/caret-mgmt"
SERVICE_USER="www-data"
PORT=8100
TOKEN="${CARET_TOKEN:-change-me}"
DOMAIN="${CARET_DOMAIN:-caret.tws-partners.com}"
UNINSTALL=false
KEEP_DB=false
YES=false

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"; shift 2 ;;
    --uninstall)
      UNINSTALL=true; shift ;;
    --keep-db)
      KEEP_DB=true; shift ;;
    --yes)
      YES=true; shift ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--port PORT] [--uninstall [--keep-db]] [--yes]" >&2
      exit 1 ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
confirm() {
  # confirm "message" — skipped if --yes or non-interactive
  if $YES || [[ ! -t 0 ]]; then return 0; fi
  read -rp "$1 [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

# ── Uninstall path ────────────────────────────────────────────────────────────
if $UNINSTALL; then
  echo "=== Caret Management Server — UNINSTALL ==="

  if systemctl is-active --quiet caret-mgmt 2>/dev/null; then
    echo "Stopping caret-mgmt service..."
    systemctl stop caret-mgmt
  fi
  if systemctl is-enabled --quiet caret-mgmt 2>/dev/null; then
    systemctl disable caret-mgmt
  fi

  UNIT_FILE="/etc/systemd/system/caret-mgmt.service"
  if [[ -f "$UNIT_FILE" ]]; then
    rm -f "$UNIT_FILE"
    systemctl daemon-reload
    echo "Removed $UNIT_FILE"
  fi

  NGINX_SNIPPET="/etc/nginx/snippets/caret-mgmt.conf"
  if [[ -f "$NGINX_SNIPPET" ]]; then
    rm -f "$NGINX_SNIPPET"
    echo "Removed $NGINX_SNIPPET"
    echo "  ⚠  Remember to remove 'include $NGINX_SNIPPET;' from your ISPConfig vhost Nginx Directives."
  fi

  if $KEEP_DB && [[ -f "$INSTALL_DIR/fleet.db" ]]; then
    cp "$INSTALL_DIR/fleet.db" /tmp/caret-fleet.db
    echo "fleet.db preserved at /tmp/caret-fleet.db"
  fi

  if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    echo "Removed $INSTALL_DIR"
  fi

  echo ""
  echo "=== Uninstall complete ==="
  echo "System packages (python3, python3-venv) were NOT removed."
  exit 0
fi

# ── Install / upgrade path ────────────────────────────────────────────────────
echo "=== Caret Management Server deployment ==="
echo "Install dir : $INSTALL_DIR"
echo "Domain      : $DOMAIN"
echo "Port        : $PORT"
echo ""

# Port breadcrumb check — warn if previously deployed on a different port
BREADCRUMB="$INSTALL_DIR/.port"
if [[ -f "$BREADCRUMB" ]]; then
  DEPLOYED_PORT=$(cat "$BREADCRUMB")
  if [[ "$DEPLOYED_PORT" != "$PORT" ]]; then
    echo "⚠  Warning: existing install was deployed on port $DEPLOYED_PORT but --port $PORT was requested."
    echo "   The nginx snippet and systemd unit will be updated to port $PORT."
    confirm "Continue?" || { echo "Aborted."; exit 1; }
  fi
fi

# Stop existing service so it doesn't hold the port during the conflict check
if systemctl is-active --quiet caret-mgmt 2>/dev/null; then
  echo "Stopping existing caret-mgmt service for upgrade..."
  systemctl stop caret-mgmt
fi

# Port conflict check
if ss -tlnp | grep -q ":${PORT} "; then
  echo "" >&2
  echo "ERROR: Port $PORT is already in use:" >&2
  ss -tlnp | grep ":${PORT} " >&2
  echo "" >&2
  echo "Options:" >&2
  echo "  • Choose a different port:  sudo ./deploy-linux.sh --port 8101" >&2
  echo "  • Free the port manually, then re-run." >&2
  exit 1
fi

# 1. Python dependency check / install
NEED_PYTHON=false
NEED_VENV=false
command -v python3 &>/dev/null || NEED_PYTHON=true
python3 -c "import venv" &>/dev/null || NEED_VENV=true

if $NEED_PYTHON || $NEED_VENV; then
  PKGS=""
  $NEED_PYTHON && PKGS="python3 python3-pip"
  $NEED_VENV   && PKGS="$PKGS python3-venv"
  PKGS="${PKGS# }"
  echo "The following system packages will be installed: $PKGS"
  if confirm "Install now?"; then
    apt-get update -q && apt-get install -y $PKGS
  else
    echo "Aborted — required packages not available." >&2
    exit 1
  fi
fi

# 2. Create install dir and copy files
mkdir -p "$INSTALL_DIR"
cp server.py requirements.txt "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Write port breadcrumb
echo "$PORT" > "$BREADCRUMB"

# 3. Create virtualenv and install deps
sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/venv"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

# 4. Write systemd service
cat > /etc/systemd/system/caret-mgmt.service <<EOF
[Unit]
Description=Caret Management Server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn server:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=5
Environment=CARET_MANAGEMENT_TOKEN=$TOKEN
Environment=CARET_ROOT_PATH=/admin
Environment=CARET_DB_PATH=$INSTALL_DIR/fleet.db
Environment=CARET_SERVER_PORT=$PORT

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable caret-mgmt
systemctl restart caret-mgmt

echo ""
echo "Service status:"
systemctl status caret-mgmt --no-pager

# 5. Write Nginx location snippet
# The checkin endpoint is listed BEFORE /admin/ so nginx matches it first
# (more-specific location blocks must precede less-specific ones in ISPConfig
# Nginx Directives, which are injected into a single server block).
cat > /etc/nginx/snippets/caret-mgmt.conf <<EOF
# Device checkins — must come before /admin/ to match first
# Accessible from all corporate devices; no IP restriction
location /admin/v1/devices/checkin {
    proxy_pass         http://127.0.0.1:${PORT}/v1/devices/checkin;
    proxy_http_version 1.1;
    proxy_set_header   Host              \$host;
    proxy_set_header   X-Real-IP         \$remote_addr;
    proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto \$scheme;
    proxy_read_timeout 30s;
}

# Fleet dashboard + API — restrict to office/VPN IPs if desired
location /admin/ {
    proxy_pass         http://127.0.0.1:${PORT}/;
    proxy_http_version 1.1;
    proxy_set_header   Host              \$host;
    proxy_set_header   X-Real-IP         \$remote_addr;
    proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto \$scheme;
    proxy_read_timeout 30s;

    # Optional: restrict dashboard to office/VPN IP ranges
    # allow 10.0.0.0/8;
    # allow 192.168.0.0/16;
    # deny all;
}

location = /admin { return 301 /admin/; }
EOF

echo ""
echo "=== Done ==="
echo "Add this to your ISPConfig vhost Nginx Directives:"
echo "    include /etc/nginx/snippets/caret-mgmt.conf;"
echo ""
echo "Then reload Nginx: systemctl reload nginx"
echo ""
echo "Dashboard: https://$DOMAIN/admin/"
echo "Token    : $TOKEN"
