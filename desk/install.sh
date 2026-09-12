#!/usr/bin/env bash
# GENIUS Desk: one-shot server install (Ubuntu 22.04 / 24.04).
#
#   curl -fsSL <raw url of this file> | bash        (or: bash desk/install.sh)
#
# What it does:
#   1. installs python3 + venv + git
#   2. clones the repo to /opt/genius (or updates it)
#   3. creates a venv and installs the Hyperliquid SDK (needed only for live mode)
#   4. creates /etc/genius-desk/secrets.env, mode 600, with placeholders
#   5. installs a systemd service `genius-desk` that runs the hourly loop
#   6. installs the `genius-desk` command: status | kill | resume | once | logs
#
# It does NOT start trading. The service starts in SHADOW mode. Switching to
# live is a deliberate edit of desk/config.json ("mode": "live") after the
# wallet key is in the secrets file. See desk/README.md.
set -euo pipefail

REPO_URL="${GENIUS_REPO_URL:-}"          # set by the operator, e.g. https://github.com/<user>/<repo>.git
APP_DIR=/opt/genius
SECRETS=/etc/genius-desk/secrets.env
PY=python3

if [[ $(id -u) -ne 0 ]]; then echo "run as root (sudo bash desk/install.sh)"; exit 1; fi
if [[ -z "$REPO_URL" && ! -d "$APP_DIR/.git" ]]; then
  echo "set GENIUS_REPO_URL to the repo clone URL first, e.g."
  echo "  GENIUS_REPO_URL=https://x-access-token:<token>@github.com/<user>/<repo>.git bash desk/install.sh"
  exit 1
fi

echo "[1/6] packages"
apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip git >/dev/null

echo "[2/6] code → $APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then git -C "$APP_DIR" pull -q; else git clone -q "$REPO_URL" "$APP_DIR"; fi

echo "[3/6] python venv"
$PY -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/desk/requirements.txt" || echo "  (hyperliquid sdk install failed; shadow mode still works, retry before going live)"

echo "[4/6] secrets file"
mkdir -p "$(dirname "$SECRETS")"
if [[ ! -f "$SECRETS" ]]; then
  cat > "$SECRETS" <<'EOF'
# GENIUS Desk secrets. This file is mode 600 and read only by the service.
# Fill in by hand. Never commit. Never paste into chat.
DESK_AGENT_KEY=
DESK_ACCOUNT=
DESK_GIT_REMOTE=
DESK_TESTNET=0
EOF
fi
chmod 600 "$SECRETS"

echo "[5/6] systemd service"
cat > /etc/systemd/system/genius-desk.service <<EOF
[Unit]
Description=GENIUS Desk (hourly trading loop)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=DESK_SECRETS_FILE=$SECRETS
ExecStart=$APP_DIR/.venv/bin/python desk/run_desk.py --loop
Restart=always
RestartSec=30
StandardOutput=append:/var/log/genius-desk.log
StandardError=append:/var/log/genius-desk.log

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable genius-desk >/dev/null

echo "[6/6] genius-desk command"
cat > /usr/local/bin/genius-desk <<EOF
#!/usr/bin/env bash
# genius-desk status | once | kill | resume | logs | start | stop | restart | update
cd $APP_DIR
export DESK_SECRETS_FILE=$SECRETS
case "\${1:-status}" in
  status)  .venv/bin/python desk/run_desk.py --status ;;
  once)    .venv/bin/python desk/run_desk.py --once ;;
  kill)    .venv/bin/python desk/run_desk.py --kill ;;
  resume)  .venv/bin/python desk/run_desk.py --resume ;;
  logs)    tail -n \${2:-50} -f /var/log/genius-desk.log ;;
  start|stop|restart) systemctl \$1 genius-desk && systemctl --no-pager status genius-desk | head -5 ;;
  update)  git pull -q && .venv/bin/pip install -q -r desk/requirements.txt && systemctl restart genius-desk && echo updated ;;
  *) echo "usage: genius-desk status|once|kill|resume|logs|start|stop|restart|update" ;;
esac
EOF
chmod +x /usr/local/bin/genius-desk

echo
echo "installed. next:"
echo "  1. edit $SECRETS   (DESK_AGENT_KEY + DESK_ACCOUNT only when going live)"
echo "  2. genius-desk once        # one shadow cycle, prints status"
echo "  3. genius-desk start       # hourly loop in shadow mode"
echo "  4. genius-desk logs        # watch it"
echo "server IP (for your own records): $(curl -s ifconfig.me || hostname -I | awk '{print $1}')"
