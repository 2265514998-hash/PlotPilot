@echo off
cd /d "D:\PlotPilot"
title PlotPilot

echo ======================================
echo   PlotPilot
echo ======================================

rem clean ports
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":8005" ^| find "LISTENING"') do taskkill /f /pid %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":3000" ^| find "LISTENING"') do taskkill /f /pid %%a 2>nul
timeout /t 1 /nobreak >nul

rem start backend
start "PlotPilot-API" /min .venv\Scripts\python.exe -m uvicorn interfaces.main:app --host 0.0.0.0 --port 8005

rem start frontend
cd frontend
start "PlotPilot-UI" /min cmd /c "npx vite --host 0.0.0.0 --port 3000"
cd ..

echo Starting services...
echo.

rem wait and open browser
timeout /t 6 /nobreak >nul
start http://127.0.0.1:3000

echo ======================================
echo   Ready - http://127.0.0.1:3000
echo   Close this window to stop
echo ======================================
pause >nul

rem cleanup
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":8005" ^| find "LISTENING"') do taskkill /f /t /pid %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| find ":3000" ^| find "LISTENING"') do taskkill /f /t /pid %%a 2>nul
