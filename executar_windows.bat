@echo off
cd /d "%~dp0"
echo Instalando/atualizando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Nao foi possivel instalar as dependencias.
  pause
  exit /b 1
)
echo Abrindo a interface no navegador...
python -m streamlit run app.py
pause
