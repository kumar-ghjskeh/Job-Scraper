@echo off
title Ashborne Silicon - Starting...

:: Kill any stale processes on our ports
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

:: Start backend
start "Ashborne Silicon - Backend" /MIN cmd /c "cd /d "%~dp0backend" && py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1"

:: Start frontend dev server
start "Ashborne Silicon - Frontend" /MIN cmd /c "cd /d "%~dp0frontend" && npm run dev 2>&1"

:: Wait for both servers to be ready
echo Waiting for servers to start...
:WAIT_BACKEND
timeout /t 1 /nobreak >nul
netstat -ano 2>nul | findstr ":8000 " | findstr LISTENING >nul
if errorlevel 1 goto WAIT_BACKEND

:WAIT_FRONTEND
timeout /t 1 /nobreak >nul
netstat -ano 2>nul | findstr ":5173 " | findstr LISTENING >nul
if errorlevel 1 goto WAIT_FRONTEND

:: Open in Edge as an app (same style as the original shortcut)
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:5173 --profile-directory=Default

exit
