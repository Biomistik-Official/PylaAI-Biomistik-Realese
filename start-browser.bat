@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" PylaLauncher.py %*
) else (
    python PylaLauncher.py %*
)
if errorlevel 1 pause
