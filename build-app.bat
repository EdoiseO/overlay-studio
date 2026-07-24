@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=larpdog-server\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Overlay Studio needs its Python environment.
  echo Run larpdog-server\install.bat once, then try again.
  pause
  exit /b 1
)

"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "Overlay Studio" ^
  --paths "larpdog-server" ^
  --add-data "studio;studio" ^
  overlay_studio.pyw
if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)

copy /y "dist\Overlay Studio.exe" "Overlay Studio.exe" >nul
if errorlevel 1 (
  echo.
  echo The app was built, but Overlay Studio.exe could not be replaced.
  echo Close Overlay Studio and run this build again.
  pause
  exit /b 1
)

echo.
echo Overlay Studio.exe is ready.
