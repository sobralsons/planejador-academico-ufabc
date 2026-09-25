@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente .venv nao encontrado.
  echo Execute primeiro preparar_ambiente_windows.bat.
  pause
  exit /b 1
)

echo Iniciando API local.
echo A API ainda e de desenvolvimento e nao deve ser exposta publicamente.
".venv\Scripts\python.exe" -m scripts.executar_api_local
pause
