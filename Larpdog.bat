@echo off
setlocal
cd /d "%~dp0"

if exist "Larpdog Control.exe" (
  start "" "Larpdog Control.exe"
  exit /b 0
)

set "LARPDOG_PYTHONW=larpdog-server\.venv\Scripts\pythonw.exe"
if not exist "%LARPDOG_PYTHONW%" (
  echo Larpdog needs its Python environment. Run larpdog-server\install.bat once.
  pause
  exit /b 1
)

start "" "%LARPDOG_PYTHONW%" "%~dp0larpdog_control.pyw"
