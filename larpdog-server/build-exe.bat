@echo off
setlocal
cd /d "%~dp0"

if exist "..\.venv\Scripts\python.exe" (
  set PY=..\.venv\Scripts\python.exe
) else if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else (
  set PY=py -3
)

%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 pause & exit /b 1
%PY% -m PyInstaller overlay-studio-server.spec
if errorlevel 1 pause & exit /b 1

echo.
echo Built dist\overlay-studio-server.exe
pause
