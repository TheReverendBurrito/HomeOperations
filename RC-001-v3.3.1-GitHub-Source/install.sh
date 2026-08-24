#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="rc001"
INSTALL_DIR="/opt/rc001"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
WATCHDOG_SERVICE_FILE="/etc/systemd/system/${APP_NAME}-watchdog.service"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-${USER}}"
RUN_GROUP="$(id -gn "$RUN_USER")"
BACKUP_ROOT="/opt/rc001-install-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${STAMP}"
NEEDS_CONFIGURATION=0

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo: sudo ./install.sh" >&2
  exit 1
fi

if [[ ! -f "${SOURCE_DIR}/app.py" || ! -f "${SOURCE_DIR}/VERSION.json" ]]; then
  echo "Installer must be run from the extracted RC-001 release directory." >&2
  exit 1
fi

command -v python3 >/dev/null || { echo "python3 is required." >&2; exit 1; }

mkdir -p "$BACKUP_ROOT"
if [[ -d "$INSTALL_DIR" ]]; then
  mkdir -p "$BACKUP_DIR"
  cp -a "$INSTALL_DIR/." "$BACKUP_DIR/"
  echo "Existing installation backed up to $BACKUP_DIR"
fi

PRESERVE_DIR="$(mktemp -d)"
cleanup() { rm -rf "$PRESERVE_DIR"; }
trap cleanup EXIT

[[ -f "$INSTALL_DIR/.env" ]] && cp -a "$INSTALL_DIR/.env" "$PRESERVE_DIR/.env"
[[ -d "$INSTALL_DIR/data" ]] && cp -a "$INSTALL_DIR/data" "$PRESERVE_DIR/data"

systemctl stop "${APP_NAME}-watchdog" 2>/dev/null || true
systemctl stop "$APP_NAME" 2>/dev/null || true
mkdir -p "$INSTALL_DIR"
find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 ! -name '.env' ! -name 'data' -exec rm -rf {} +

cp -a "$SOURCE_DIR/." "$INSTALL_DIR/"
rm -f "$INSTALL_DIR/.env"
rm -rf "$INSTALL_DIR/.venv" "$INSTALL_DIR/data"

[[ -f "$PRESERVE_DIR/.env" ]] && cp -a "$PRESERVE_DIR/.env" "$INSTALL_DIR/.env"
[[ -d "$PRESERVE_DIR/data" ]] && cp -a "$PRESERVE_DIR/data" "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/data"

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  chmod 600 "$INSTALL_DIR/.env"
  NEEDS_CONFIGURATION=1
fi

python3 - <<'PY'
import flask, dotenv, requests
print("System Python dependencies verified.")
PY

cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=RC-001 Home Operations Center
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/app.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

cat > "$WATCHDOG_SERVICE_FILE" <<SERVICE
[Unit]
Description=RC-001 Independent Service Watchdog
After=network-online.target rc001.service
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/rc001_watchdog.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

chown -R "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env"
chmod +x "$INSTALL_DIR/install.sh"

if [[ "$NEEDS_CONFIGURATION" -eq 1 ]]; then
  echo
  echo "Created $INSTALL_DIR/.env from the sanitized example."
  echo "Configure URLs, credentials, entities, and location in that file, then run this installer again."
  exit 2
fi

systemctl daemon-reload
systemctl enable "$APP_NAME"
systemctl restart "$APP_NAME"
systemctl enable "${APP_NAME}-watchdog"
systemctl restart "${APP_NAME}-watchdog"

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:5050/api/build >/dev/null 2>&1; then
    echo "RC-001 is online."
    break
  fi
  sleep 1
done

if ! systemctl is-active --quiet "$APP_NAME"; then
  echo "RC-001 failed to start. Recent service log:" >&2
  journalctl -u "$APP_NAME" -n 60 --no-pager >&2
  if [[ -d "$BACKUP_DIR" ]]; then
    echo "Restoring previous installation from $BACKUP_DIR" >&2
    systemctl stop "$APP_NAME" || true
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    cp -a "$BACKUP_DIR/." "$INSTALL_DIR/"
    chown -R "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR"
    systemctl restart "$APP_NAME" || true
  fi
  exit 1
fi

/usr/bin/python3 "$INSTALL_DIR/selftest.py" --skip-connectivity || {
  echo "Installation completed, but the offline self-test reported a failure." >&2
  exit 1
}

echo
echo "Installed RC-001 to $INSTALL_DIR"
echo "Service: systemctl status rc001 --no-pager"
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5050"
