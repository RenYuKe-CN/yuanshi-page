#!/bin/zsh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_URL="${REPO_URL:-https://github.com/zmmidas/yuanshi.git}"
BRANCH="${BRANCH:-main}"
TMP_REPO="$(mktemp -d /private/tmp/yuanshi-github-upload.XXXXXX)"

echo "原石金手指 · 一键上传 GitHub"
echo "========================================"
echo "仓库：$REPO_URL"
echo "分支：$BRANCH"
echo "临时目录：$TMP_REPO"
echo

if ! command -v git >/dev/null 2>&1; then
  echo "未检测到 git。请先安装 Git 或 Xcode Command Line Tools。"
  read "?按回车退出..."
  exit 1
fi

cd "$PROJECT_DIR"

echo "1/5 复制干净源码到临时目录..."
rsync -a \
  --exclude='.git/' \
  --exclude='.next/' \
  --exclude='node_modules/' \
  --exclude='local_data/' \
  --exclude='outputs/' \
  --exclude='__pycache__/' \
  --exclude='.pnpm-store/' \
  --exclude='coverage/' \
  --exclude='dist/' \
  --exclude='.venv/' \
  --exclude='tmp/' \
  --exclude='.env' \
  --exclude='.env.production' \
  --exclude='*.pem' \
  --exclude='*.key' \
  --exclude='*.log' \
  --exclude='tsconfig.tsbuildinfo' \
  --exclude='服务器部署检查日志.txt' \
  --exclude='部署到服务器.command' \
  --exclude='使用私钥部署到服务器.command' \
  --exclude='检查并修复服务器.command' \
  --exclude='一键部署服务器并打开.command' \
  --include='public/brand/exchanges/' \
  --include='public/brand/exchanges/fx-protocol.png' \
  --include='public/brand/exchanges/fx100.png' \
  --exclude='public/brand/exchanges/*.png' \
  ./ "$TMP_REPO/"

cd "$TMP_REPO"

echo
echo "2/5 初始化 Git..."
git init
git branch -M "$BRANCH"
git config user.name "${GIT_AUTHOR_NAME:-midas}"
git config user.email "${GIT_AUTHOR_EMAIL:-midas@users.noreply.github.com}"

echo
echo "3/5 提交文件..."
git add .
git status --short | sed -n '1,220p'
git commit -m "Initial release of Yuanshi Gold Finger"

echo
echo "4/5 推送到 GitHub..."
git remote add origin "$REPO_URL"
git push -u origin "$BRANCH"

echo
echo "5/5 完成。"
echo "已上传到：$REPO_URL"
echo
echo "如果推送时提示需要密码：GitHub 现在不支持账号密码，请使用 Personal Access Token。"
echo "打开仓库查看：https://github.com/zmmidas/yuanshi"
echo
read "?按回车关闭窗口..."
