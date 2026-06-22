@echo off
setlocal
cd /d "%~dp0"

if not exist config.json (
  copy config.example.json config.json >nul
  echo Created config.json from config.example.json.
  echo Add your Spotify client_id and client_secret before first Spotify use.
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py --config config.json
) else (
  py -3 main.py --config config.json
)

if errorlevel 1 pause
