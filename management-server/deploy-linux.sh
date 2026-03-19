#!/bin/bash
# Caret Management Server — Linux deployment script
# Run as root on the ISPConfig server:
#   wget https://raw.githubusercontent.com/.../deploy-linux.sh
#   chmod +x deploy-linux.sh && sudo ./deploy-linux.sh
#
# Required env vars (set before running):
#   CARET_TOKEN    — bearer token for API auth
#   CARET_DOMAIN   — domain name (e.g. caret.tws-partners.com)

set -e

INSTALL_DIR="/opt/caret-mgmt"
SERVICE_USER="www-data"
PORT=8100
TOKEN="${CARET_TOKEN:-change-me}"
DOMAIN="${CARET_DOMAIN:-caret.tws-partners.com}"

echo "=== Caret Management Server deployment ==="
echo "Install dir : $INSTALL_DIR"
echo "Domain      : $DOMAIN"
echo "Port        : $PORT"
echo ""

# 1. Install Python if needed
if ! command -v python3 &>/dev/null; then
  apt-get update -q && apt-get install -y python3 python3-pip python3-venv
fi

# 2. Create install dir and copy files
mkdir -p "$INSTALL_DIR"
cp server.py requirements.txt "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

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
cat > /etc/nginx/snippets/caret-mgmt.conf <<EOF
location /admin/ {
    proxy_pass         http://127.0.0.1:$PORT/;
    proxy_http_version 1.1;
    proxy_set_header   Host              \$host;
    proxy_set_header   X-Real-IP         \$remote_addr;
    proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto \$scheme;
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
