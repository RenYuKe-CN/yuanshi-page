#!/bin/zsh

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未检测到 Python 3，无法启动本地版。"
  read "?按回车退出。"
  exit 1
fi

if curl -fsS http://127.0.0.1:3000/health 2>/dev/null | grep -qx "OK"; then
  echo "原石金手指已在运行：http://localhost:3000"
  open http://localhost:3000
  exit 0
fi

mkdir -p local_data
nohup python3 "$PROJECT_DIR/local_app.py" > "$PROJECT_DIR/local_data/server.log" 2>&1 &
echo $! > "$PROJECT_DIR/local_data/server.pid"

for i in {1..30}; do
  if curl -fsS http://127.0.0.1:3000/health 2>/dev/null | grep -qx "OK"; then
    echo
    echo "原石金手指已启动：http://localhost:3000"
    if [ -f "$PROJECT_DIR/local_data/admin.txt" ]; then
      echo
      cat "$PROJECT_DIR/local_data/admin.txt"
    fi
    echo
    open http://localhost:3000
    read "?按回车关闭窗口（网站会继续运行）。"
    exit 0
  fi
  sleep 1
done

echo "启动失败，错误信息："
tail -n 50 "$PROJECT_DIR/local_data/server.log"
read "?按回车退出。"
exit 1
