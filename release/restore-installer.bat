@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore-installer.ps1"
exit /b %errorlevel%
