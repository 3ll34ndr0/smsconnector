#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/goip-sms"
SERVICE="goip-sms-in"

echo "==> Installing GoIP SMS inbound gateway"

# 1. Copy files
mkdir -p "$INSTALL_DIR"
cp goip_sms_in.py requirements.txt "$INSTALL_DIR/"

# 2. Install Python dependencies
python3 -m pip install --quiet -r "$INSTALL_DIR/requirements.txt"

# 3. Install and enable systemd service
cp goip-sms-in.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now "$SERVICE"

echo "==> Done. Service status:"
systemctl status "$SERVICE" --no-pager
