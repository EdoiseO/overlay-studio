@echo off
setlocal
cd /d "%~dp0"

if exist "Overlay Studio.exe" (
  start "" "Overlay Studio.exe"
  exit /b 0
)

set "OVERLAY_STUDIO_PYTHONW=larpdog-server\.venv\Scripts\pythonw.exe"
if not exist "%OVERLAY_STUDIO_PYTHONW%" (
  echo Overlay Studio needs its Python environment. Run larpdog-server\install.bat once.
  pause
  exit /b 1
)

start "" "%OVERLAY_STUDIO_PYTHONW%" "%~dp0overlay_studio.pyw"
