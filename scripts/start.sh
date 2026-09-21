#!/usr/bin/env bash
# AI 企业知识库 - Docker 一键启动（Linux/macOS/Git Bash）
set -e
cd "$(dirname "$0")/.."

echo "[1/3] 检查 Docker..."
docker info >/dev/null 2>&1 || { echo "Docker 未运行，请先启动 Docker Desktop"; exit 1; }

echo "[2/3] 构建并启动..."
docker compose up -d --build

echo "[3/3] 等待就绪..."
sleep 8
docker compose ps

echo "=================================================="
echo " 前端控制台    http://localhost:8080"
echo " 后端接口文档  http://localhost:9090/docs"
echo " 默认账号     admin / admin"
echo "=================================================="