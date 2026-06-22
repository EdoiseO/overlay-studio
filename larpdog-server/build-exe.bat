@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else (
  set PY=py -3
)

%PY% -m pip install -r requirements.txt pyinstaller
%PY% -m PyInstaller larpdog-server.spec

echo.
echo Built dist\larpdog-server.exe
pause
