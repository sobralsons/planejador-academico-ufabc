@echo off
cd /d "%~dp0"
if exist "saidas\relatorio_planejamento.html" (
  start "" "saidas\relatorio_planejamento.html"
) else (
  echo O relatorio ainda nao foi gerado. Execute executar_windows.bat primeiro.
  pause
)
