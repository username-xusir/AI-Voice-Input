@echo off
setlocal
set "ROOT=%~dp0"
set PYTHONIOENCODING=utf-8
if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo [Voxa] .venv not found. Run setup.bat first.
    pause
    exit /b 1
)
"%ROOT%.venv\Scripts\python.exe" "%ROOT%app\main.py"
pause
