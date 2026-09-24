@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente .venv nao encontrado.
  echo Execute primeiro preparar_ambiente_windows.bat.
  pause
  exit /b 1
)

echo Iniciando API local em http://127.0.0.1:8000
echo A API ainda e de desenvolvimento e nao deve ser exposta publicamente.
".venv\Scripts\python.exe" -m uvicorn api.app:app --host 127.0.0.1 --port 8000
pause
