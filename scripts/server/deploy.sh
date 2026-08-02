#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-root}"
SSH_KEY="${SSH_KEY:-}"
REMOTE_DIR="${REMOTE_DIR:-/tmp/yuanshi-jinshouzhi-deploy}"
ARCHIVE="${ARCHIVE:-/tmp/yuanshi-jinshouzhi-upload.tgz}"

if [[ -z "$SERVER_HOST" ]]; then
  echo "缺少 SERVER_HOST。示例："
  echo "SERVER_HOST=124.156.138.166 SSH_KEY=~/Downloads/yuanshi.pem bash scripts/server/deploy.sh"
  exit 1
fi

SSH_ARGS=(-o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_KEY" ]]; then
  chmod 600 "$SSH_KEY" 2>/dev/null || true
  SSH_ARGS=(-i "$SSH_KEY" "${SSH_ARGS[@]}")
fi

cd "$PROJECT_DIR"

echo "1/5 测试 SSH：${SERVER_USER}@${SERVER_HOST}"
ssh "${SSH_ARGS[@]}" "${SERVER_USER}@${SERVER_HOST}" "echo SSH_OK"

echo "2/5 打包项目"
tar \
  --exclude ".git" \
  --exclude ".env" \
  --exclude "local_data" \
  --exclude "node_modules" \
  --exclude ".next" \
  --exclude "__pycache__" \
  --exclude "outputs" \
  -czf "$ARCHIVE" .

echo "3/5 上传项目"
ssh "${SSH_ARGS[@]}" "${SERVER_USER}@${SERVER_HOST}" "rm -rf '${REMOTE_DIR}' && mkdir -p '${REMOTE_DIR}'"
scp "${SSH_ARGS[@]}" "$ARCHIVE" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR}/app.tgz"

echo "4/5 远程安装/更新"
ssh "${SSH_ARGS[@]}" "${SERVER_USER}@${SERVER_HOST}" "cd '${REMOTE_DIR}' && tar -xzf app.tgz && sudo bash scripts/server/manage.sh update"

echo "5/5 检查状态"
ssh "${SSH_ARGS[@]}" "${SERVER_USER}@${SERVER_HOST}" "bash /opt/yuanshi-jinshouzhi/scripts/server/manage.sh status"

echo
echo "部署完成："
echo "http://${SERVER_HOST}:3000/login"
echo
echo "如果外网打不开，请在云服务器安全组放行 TCP 3000。"
