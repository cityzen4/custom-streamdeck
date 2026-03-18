@echo off
if "%~1"=="hidden" goto :run

:: Run this script hidden via PowerShell to prevent the terminal from staying open
powershell -WindowStyle Hidden -Command "Start-Process cmd.exe -ArgumentList '/c \"%~f0\" hidden' -WindowStyle Hidden"
exit

:run
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "main.py"
