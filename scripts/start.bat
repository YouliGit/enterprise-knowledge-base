@echo off
chcp 65001 >nul
title AI 企业知识库 - Docker 一键启动
echo ==================================================
echo  AI Agentic RAG 企业知识库平台 - 一键启动
echo  （项目完全在 Docker 中运行）
echo ==================================================
echo.

cd /d "%~dp0.."

echo [1/3] 检查 Docker Desktop 是否运行...
docker info >nul 2>&1
if errorlevel 1 (
    echo  [错误] Docker 未运行，请先启动 Docker Desktop（点右下角鲸鱼图标）。
    echo  提示：若 WSL2 未安装完成，先去 Docker Desktop 设置里完成安装。
    pause
    exit /b 1
)
echo   Docker 运行正常。

echo [2/3] 构建并启动全部服务（首次需拉取镜像，较大，走国内源可加速）...
docker compose up -d --build
if errorlevel 1 (
    echo  [错误] 构建/启动失败，请检查上方日志。
    pause
    exit /b 1
)

echo [3/3] 等待所有服务就绪...
timeout /t 8 /nobreak >nul
docker compose ps

echo.
echo ==================================================
echo  构建完成！访问地址：
echo    前端控制台    http://localhost:8080
echo    后端接口文档  http://localhost:9090/docs
echo    默认账号     admin / admin
echo ==================================================
echo  注意：AI 问答需先在「AI模型配置」填入百炼 API Key
echo        （付费项，见根目录《未完成清单.txt》）
echo.
pause