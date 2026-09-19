@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente .venv nao encontrado.
  echo Execute primeiro preparar_ambiente_windows.bat.
  pause
  exit /b 1
)

echo Abrindo a interface interna de desenvolvimento no navegador...
".venv\Scripts\python.exe" -m streamlit run app_interno.py
pause
