@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente .venv nao encontrado.
  echo Execute primeiro preparar_ambiente_windows.bat.
  pause
  exit /b 1
)

echo Verificando ambiente local...
".venv\Scripts\python.exe" scripts\verificar_ambiente_local.py
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo Verificando sintaxe...
".venv\Scripts\python.exe" -m compileall -q app.py app_interno.py main.py planejador ferramentas api persistencia scripts
if errorlevel 1 (
  echo Falha de sintaxe.
  pause
  exit /b 1
)

echo.
echo Executando a suite completa de testes...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
  echo.
  echo Um ou mais testes falharam. Nao use o resultado antes de revisar o erro.
  pause
  exit /b 1
)

echo.
echo Validacao local aprovada.
pause
