#!/bin/zsh

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/local_data/server.pid"

if [ -f "$PID_FILE" ]; then
  SERVER_PID="$(cat "$PID_FILE")"
  SERVER_COMMAND="$(ps -p "$SERVER_PID" -o command= 2>/dev/null)"
  if kill -0 "$SERVER_PID" 2>/dev/null && [[ "$SERVER_COMMAND" == *"local_app.py"* ]]; then
    kill "$SERVER_PID"
    echo "原石金手指已停止，数据仍保存在 local_data 文件夹中。"
  else
    echo "原石金手指当前没有运行。"
  fi
  rm -f "$PID_FILE"
else
  echo "原石金手指当前没有运行。"
fi

read "?按回车退出。"
