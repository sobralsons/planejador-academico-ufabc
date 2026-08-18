@echo off
cd /d "%~dp0"
echo Instalando dependencias de validacao...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Nao foi possivel instalar as dependencias.
  pause
  exit /b 1
)
echo.
echo Executando a suite completa de testes...
python -m pytest -q
if errorlevel 1 (
  echo.
  echo Um ou mais testes falharam. Nao use o resultado antes de revisar o erro.
  pause
  exit /b 1
)
echo.
echo Todos os testes foram aprovados.
pause
