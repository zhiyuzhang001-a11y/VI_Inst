@echo off
setlocal
cd /d "%~dp0"

echo [VI_Inst] Preparing the Python environment...

py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PY_LAUNCH=py -3.13"
) else (
    py -3 -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo Python 3.11 or newer was not found.
        echo Install 64-bit Python 3.13 from https://www.python.org/downloads/windows/
        echo Then run this file again.
        pause
        exit /b 1
    )
    set "PY_LAUNCH=py -3"
)

if not exist ".venv\Scripts\python.exe" (
    %PY_LAUNCH% -m venv .venv
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

if not exist "config.local.toml" copy /y "config.toml" "config.local.toml" >nul

echo.
echo [VI_Inst] Installation completed. Running the safe environment check...
".venv\Scripts\python.exe" check_environment.py
echo.
echo You can now double-click run_windows.bat.
pause
exit /b 0

:failed
echo.
echo Installation failed. Review the error above and README.md.
pause
exit /b 1
