@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
where uv >nul 2>nul
if errorlevel 1 (
    echo [Voxa] uv not found. Install uv first: https://docs.astral.sh/uv/
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo [Voxa] Creating Python 3.12 virtual environment...
    uv venv .venv --python 3.12 || goto :error
)
echo [Voxa] Installing dependencies. First run is about 1-2 GB...
uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt || goto :error
echo.
echo [Voxa] Done. Double-click run.bat to start.
pause
exit /b 0
:error
echo.
echo [Voxa] Install failed. Send the error above.
pause
exit /b 1
