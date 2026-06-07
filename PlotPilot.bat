@echo off
chcp 65001 >nul
title PlotPilot
cd /d "%~dp0"

echo ======================================
echo   PlotPilot ^(墨枢^) 启动中...
echo ======================================

rem clean any leftover processes on our ports
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":8005" ^| find "LISTENING"') do taskkill /f /pid %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":3000" ^| find "LISTENING"') do taskkill /f /pid %%a 2>nul

timeout /t 1 /nobreak >nul

rem launch backend in its own minimised window
start "PlotPilot-API" /min ".venv\Scripts\python.exe" -m uvicorn interfaces.main:app --host 0.0.0.0 --port 8005

echo   后端启动中 (8005)...

rem launch frontend in its own minimised window
cd frontend
start "PlotPilot-UI" /min cmd /c "npx vite --host 0.0.0.0 --port 3000"
cd ..

echo   前端启动中 (3000)...

rem wait until both are responsive, max 30 seconds
set /a TRIES=0
:waitloop
timeout /t 1 /nobreak >nul
set /a TRIES+=1

powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri http://127.0.0.1:8005/health -UseBasicParsing -TimeoutSec 2).StatusCode } catch { 0 }" 2>nul | find "200" >nul
set BACKEND_OK=%errorlevel%

powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri http://127.0.0.1:3000 -UseBasicParsing -TimeoutSec 2).StatusCode } catch { 0 }" 2>nul | find "200" >nul
set FRONTEND_OK=%errorlevel%

if %BACKEND_OK% neq 0 goto waitloop
if %FRONTEND_OK% neq 0 goto waitloop

rem all ready — open browser
start http://127.0.0.1:3000

echo.
echo ======================================
echo   PlotPilot 已就绪!
echo   http://127.0.0.1:3000
echo   按任意键关闭全部服务
echo ======================================
pause >nul

rem cleanup
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":8005" ^| find "LISTENING"') do taskkill /f /t /pid %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":3000" ^| find "LISTENING"') do taskkill /f /t /pid %%a 2>nul
echo PlotPilot 已关闭.
timeout /t 2 /nobreak >nul
