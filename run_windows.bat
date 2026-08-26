@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call setup_windows.bat
    if errorlevel 1 exit /b 1
)

start "VI_Inst" ".venv\Scripts\pythonw.exe" launcher.py
