#!/bin/zsh

set -u

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=============================================="
echo "  原石金手指 · 临时分享"
echo "=============================================="
echo ""

if ! /usr/sbin/lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "本地网站尚未启动。"
  echo "请先双击“本地启动.command”，再重新打开本文件。"
  echo ""
  read "?按回车键关闭..."
  exit 1
fi

echo "正在生成外网访问网址，请稍候……"
echo "看到 https://xxxxx.lhr.life 或 https://xxxxx.localhost.run"
echo "这样的地址后，把它复制给需要登录的人即可。"
echo ""
echo "注意："
echo "1. 此窗口和本地网站必须保持运行。"
echo "2. 按 Control+C 即可停止外网分享。"
echo "3. 登录账号和密码请分开发送。"
echo ""

exec /usr/bin/ssh \
  -o StrictHostKeyChecking=accept-new \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R 80:127.0.0.1:3000 \
  nokey@localhost.run
