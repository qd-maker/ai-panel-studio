#!/usr/bin/env bash
# 把当前提交部署到演示服务器。在 Git Bash 里运行：bash deploy/deploy.sh
#
# 首次部署前，服务器的 /root/panel/.env 要先准备好（LLM_MODE、DEEPSEEK_API_KEY、APP_PASSWORD 等，
# 见 backend/.env.example）。脚本不碰 .env，也不会打印它。
set -euo pipefail

HOST=root@38.65.94.68
DIR=/root/panel
KEY=/c/Users/qd/.ssh/speakloop_deploy
SSH=(ssh -i "$KEY" -o UserKnownHostsFile=/c/Users/qd/.ssh/known_hosts "$HOST")
cd "$(git rev-parse --show-toplevel)"

echo "== 1/4 本地测试"
(cd backend && .venv/Scripts/python -m pytest -q)

echo "== 2/4 上传 $(git rev-parse --short HEAD)"
"${SSH[@]}" "mkdir -p $DIR/data && test -f $DIR/.env || { echo '缺少 $DIR/.env，先按 backend/.env.example 准备'; exit 1; }"
git archive --format=tar HEAD backend frontend | "${SSH[@]}" "rm -rf $DIR/src && mkdir -p $DIR/src && tar -x -C $DIR/src"
"${SSH[@]}" "cat > $DIR/docker-compose.yml" < deploy/docker-compose.server.yml
"${SSH[@]}" "cat > $DIR/nginx.server.conf" < deploy/nginx.server.conf

echo "== 3/4 备份数据并重建"
"${SSH[@]}" "cd $DIR && (test -f data/app.db && cp data/app.db data/app.db.bak-\$(date +%Y%m%d-%H%M) || true) && docker compose up -d --build"

echo "== 4/4 健康检查"
for i in $(seq 1 30); do
  if "${SSH[@]}" "docker exec panel wget -qO- http://127.0.0.1/api/health" 2>/dev/null; then echo; echo "部署完成"; exit 0; fi
  sleep 2
done
echo "健康检查失败，查看日志：docker logs panel-api"; exit 1
