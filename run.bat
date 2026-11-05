@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\pythonw.exe" (
    echo [Voxa] .venv not found. Run setup.bat first.
    pause
    exit /b 1
)
start "" "%ROOT%.venv\Scripts\pythonw.exe" "%ROOT%app\main.py"
