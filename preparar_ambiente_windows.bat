@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Verificando Python...
python --version
if errorlevel 1 (
  echo Python nao foi encontrado. Instale Python 3.12 e marque a opcao de adicionar ao PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [2/4] Criando ambiente virtual .venv...
  python -m venv .venv
  if errorlevel 1 (
    echo Nao foi possivel criar o ambiente virtual.
    pause
    exit /b 1
  )
) else (
  echo [2/4] Ambiente virtual .venv ja existe.
)

echo [3/4] Instalando dependencias locais...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements-local.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias.
  pause
  exit /b 1
)

if not exist ".env.local" (
  copy /Y ".env.example" ".env.local" >nul
  echo Criado .env.local a partir de .env.example.
)

echo [4/4] Verificando o ambiente...
".venv\Scripts\python.exe" scripts\verificar_ambiente_local.py
if errorlevel 1 (
  echo.
  echo O ambiente ainda precisa de correcao. Veja os erros acima.
  pause
  exit /b 1
)

echo.
echo Ambiente local preparado com sucesso.
echo Agora voce pode abrir esta pasta no VS Code.
pause
