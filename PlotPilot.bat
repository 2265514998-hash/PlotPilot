@echo off
chcp 65001 >nul
title PlotPilot 墨枢

cd /d "%~dp0"

echo ======================================
echo   PlotPilot 墨枢
echo ======================================

rem Kill everything on this port first
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8005.*LISTENING" 2^>nul') do taskkill /F /PID %%p 2>nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do taskkill /F /PID %%p 2>nul

rem Start backend
echo [..] 启动后端服务...
start /B "PlotPilot-Backend" ".venv\Scripts\python.exe" -m uvicorn interfaces.main:app --host 0.0.0.0 --port 8005 >nul 2>&1
set BACKEND_PID=%errorlevel%

rem Wait for backend to be ready
:wait_backend
timeout /t 2 /nobreak >nul
curl -s -o nul http://127.0.0.1:8005/health 2>nul
if errorlevel 1 goto wait_backend

rem Start frontend
echo [..] 启动前端界面...
cd frontend
start "PlotPilot-Frontend" /B npx vite --host 0.0.0.0 --port 3000 >nul 2>&1
cd ..

rem Wait for frontend
:wait_frontend
timeout /t 2 /nobreak >nul
curl -s -o nul http://127.0.0.1:3000 2>nul
if errorlevel 1 goto wait_frontend

rem Open browser
echo [✓] 正在打开浏览器...
start http://127.0.0.1:3000

echo.
echo 后端: http://127.0.0.1:8005/docs
echo 前端: http://127.0.0.1:3000
echo.
echo ════════════════════════════════════════
echo  按任意键关闭 PlotPilot（全部服务）
echo ════════════════════════════════════════
echo.
pause >nul

rem Cleanup — kill both on exit
echo.
echo [..] 正在关闭所有服务...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8005.*LISTENING" 2^>nul') do taskkill /F /T /PID %%p 2>nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do taskkill /F /T /PID %%p 2>nul

echo [✓] PlotPilot 已关闭。
timeout /t 2 /nobreak >nul
