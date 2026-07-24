@echo off
setlocal
cd /d "%~dp0"

py -3 -m venv .venv
if errorlevel 1 pause & exit /b 1

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if not exist config.json (
  copy config.example.json config.json >nul
  echo Created config.json from config.example.json.
)

echo.
echo Install complete.
echo Open ..\Overlay Studio.bat to start the desktop app.
echo Use run.bat only when you want the standalone server.
pause
