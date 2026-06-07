@echo off
cd /d "D:\PlotPilot"
title PlotPilot

echo Starting PlotPilot...

rem start backend with PYTHONPATH set
set PYTHONPATH=D:\PlotPilot
set PLOTPILOT_SKIP_PROCESS_CLEANUP=1
start "PlotPilot-Backend" /min .venv\Scripts\python.exe -m uvicorn interfaces.main:app --host 0.0.0.0 --port 8005

rem wait for backend to be ready (max 30 seconds)
echo Waiting for backend...
set /a n=0
:wait
timeout /t 2 /nobreak >nul
set /a n+=1
powershell -NoProfile -Command "try {$r=Invoke-WebRequest http://127.0.0.1:8005/health -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}}catch{exit 1}" >nul 2>&1
if %errorlevel% neq 0 (
  if %n% lss 15 goto wait
)

rem launch native desktop app
start "" "D:\PlotPilot\frontend\src-tauri\target\release\plotpilot.exe"

echo.
echo PlotPilot launched!
timeout /t 2 /nobreak >nul
