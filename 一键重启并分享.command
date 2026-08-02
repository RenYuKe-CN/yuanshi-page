#!/bin/zsh

set -u

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=============================================="
echo "  原石金手指 · 一键重启并分享"
echo "=============================================="
echo ""

mkdir -p local_data

PID_FILE="$PROJECT_DIR/local_data/server.pid"

if [ -f "$PID_FILE" ]; then
  SERVER_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "正在停止旧的网站进程：$SERVER_PID"
    kill "$SERVER_PID" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

OLD_PORT_PID="$(/usr/sbin/lsof -tiTCP:3000 -sTCP:LISTEN 2>/dev/null | head -n 1)"
if [ -n "$OLD_PORT_PID" ]; then
  OLD_COMMAND="$(ps -p "$OLD_PORT_PID" -o command= 2>/dev/null || true)"
  if [[ "$OLD_COMMAND" == *"local_app.py"* ]]; then
    echo "正在清理占用 3000 端口的旧服务：$OLD_PORT_PID"
    kill "$OLD_PORT_PID" 2>/dev/null || true
    sleep 1
  fi
fi

echo "正在启动本地网站……"
nohup python3 "$PROJECT_DIR/local_app.py" > "$PROJECT_DIR/local_data/server.log" 2>&1 &
echo $! > "$PID_FILE"

for i in {1..30}; do
  if curl -fsS http://127.0.0.1:3000/health 2>/dev/null | grep -qx "OK"; then
    echo ""
    echo "本地网站已启动：http://localhost:3000"
    if [ -f "$PROJECT_DIR/local_data/admin.txt" ]; then
      echo ""
      echo "管理员信息："
      cat "$PROJECT_DIR/local_data/admin.txt"
    fi
    echo ""
    break
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:3000/health 2>/dev/null | grep -qx "OK"; then
  echo "启动失败，错误信息："
  tail -n 80 "$PROJECT_DIR/local_data/server.log"
  echo ""
  read "?按回车键关闭..."
  exit 1
fi

echo "正在生成外网访问网址，请稍候……"
echo "看到 https://xxxxx.lhr.life 或 https://xxxxx.localhost.run 后，把它发给别人即可。"
echo ""
echo "注意：这个窗口必须保持打开；关闭窗口后，外网链接会失效。"
echo ""

exec /usr/bin/ssh \
  -o StrictHostKeyChecking=accept-new \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R 80:127.0.0.1:3000 \
  nokey@localhost.run
