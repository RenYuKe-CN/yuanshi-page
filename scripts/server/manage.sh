#!/usr/bin/env bash

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/yuanshi-jinshouzhi}"
APP_USER="${APP_USER:-yuanshi-ip}"
SERVICE_NAME="${SERVICE_NAME:-yuanshi-jinshouzhi}"
APP_PORT="${APP_PORT:-3000}"

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "请使用 root 或 sudo 执行：sudo $0 $*"
    exit 1
  fi
}

install_deps() {
  apt-get update
  apt-get install -y python3 python3-pil rsync curl
}

ensure_user() {
  if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
  fi
}

write_service() {
  cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=YuanShi JinShouZhi Web Risk Terminal
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/python3 ${APP_DIR}/local_app.py
Restart=always
RestartSec=3
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=HOST=0.0.0.0
Environment=PORT=${APP_PORT}
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${APP_DIR}/local_data
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
}

open_firewall() {
  if command -v ufw >/dev/null 2>&1; then
    ufw allow "${APP_PORT}/tcp" >/dev/null 2>&1 || true
  fi
}

install_app() {
  need_root "$@"
  if [[ ! -f "local_app.py" ]]; then
    echo "请在项目根目录执行本脚本。"
    exit 1
  fi
  install_deps
  ensure_user
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  install -d -m 0755 "$APP_DIR"
  rsync -a --delete \
    --exclude ".git/" \
    --exclude ".env" \
    --exclude "local_data/" \
    --exclude "node_modules/" \
    --exclude ".next/" \
    --exclude "outputs/" \
    --exclude "__pycache__/" \
    ./ "$APP_DIR/"
  install -d -o "$APP_USER" -g "$APP_USER" -m 0700 "$APP_DIR/local_data"
  chown -R root:root "$APP_DIR"
  chown -R "$APP_USER:$APP_USER" "$APP_DIR/local_data"
  chmod 0755 "$APP_DIR/local_app.py"
  write_service
  open_firewall
  systemctl enable --now "$SERVICE_NAME"
  echo "安装完成：http://服务器IP:${APP_PORT}"
  if [[ -f "$APP_DIR/local_data/admin.txt" ]]; then
    echo
    cat "$APP_DIR/local_data/admin.txt"
  fi
}

update_app() {
  need_root "$@"
  install_app "$@"
}

start_app() {
  need_root "$@"
  systemctl start "$SERVICE_NAME"
  systemctl --no-pager --full status "$SERVICE_NAME" || true
}

stop_app() {
  need_root "$@"
  systemctl stop "$SERVICE_NAME"
  echo "已停止：$SERVICE_NAME"
}

restart_app() {
  need_root "$@"
  systemctl restart "$SERVICE_NAME"
  systemctl --no-pager --full status "$SERVICE_NAME" || true
}

status_app() {
  systemctl --no-pager --full status "$SERVICE_NAME" || true
  echo
  if command -v ss >/dev/null 2>&1; then
    ss -lntp | grep ":${APP_PORT}" || true
  fi
  echo
  curl -sS -I --max-time 8 "http://127.0.0.1:${APP_PORT}/login" || true
}

logs_app() {
  journalctl -u "$SERVICE_NAME" -f
}

case "${1:-help}" in
  install) install_app "$@" ;;
  update) update_app "$@" ;;
  start) start_app "$@" ;;
  stop) stop_app "$@" ;;
  restart) restart_app "$@" ;;
  status) status_app "$@" ;;
  logs) logs_app "$@" ;;
  *)
    cat <<EOF
原石金手指服务器管理脚本

用法：
  sudo bash scripts/server/manage.sh install   # 首次安装
  sudo bash scripts/server/manage.sh update    # 更新代码并重启
  sudo bash scripts/server/manage.sh start     # 启动
  sudo bash scripts/server/manage.sh stop      # 停止
  sudo bash scripts/server/manage.sh restart   # 重启
  bash scripts/server/manage.sh status         # 查看状态
  bash scripts/server/manage.sh logs           # 查看实时日志

可选环境变量：
  APP_DIR=/opt/yuanshi-jinshouzhi
  APP_USER=yuanshi-ip
  SERVICE_NAME=yuanshi-jinshouzhi
  APP_PORT=3000
EOF
    ;;
esac
