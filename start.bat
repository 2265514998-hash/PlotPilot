@echo off
chcp 65001 >nul
title PlotPilot 墨枢

echo ========================================
echo   PlotPilot 墨枢 — AI 小说创作平台
echo ========================================
echo.

rem Activate venv if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [√] 已激活虚拟环境
)

rem Start backend
echo [>>] 启动后端 API 服务 (8005)...
start "PlotPilot-API" ".venv\Scripts\python.exe" -m uvicorn interfaces.main:app --host 0.0.0.0 --port 8005

rem Start frontend if Node is available
where node >nul 2>&1
if %errorlevel% equ 0 (
    echo [>>] 启动前端开发服务器 (3000)...
    cd frontend
    start "PlotPilot-UI" npx vite --host 0.0.0.0 --port 3000
    cd ..
) else (
    echo [!] Node.js 未安装，跳过前端启动
)

echo.
echo ========================================
echo   后端 API : http://127.0.0.1:8005/docs
echo   前端界面 : http://127.0.0.1:3000
echo ========================================
echo.
echo 按任意键退出此窗口...
pause >nul
