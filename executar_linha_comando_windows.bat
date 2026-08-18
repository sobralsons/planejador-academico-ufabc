@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
python main.py --config config/config.json
if exist "saidas\relatorio_planejamento.html" start "" "saidas\relatorio_planejamento.html"
pause
