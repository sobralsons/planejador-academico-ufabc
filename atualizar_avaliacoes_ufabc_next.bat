@echo off
cd /d "%~dp0"
echo Instalando/atualizando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 goto erro

echo Preparando a lista de docentes e disciplinas das ofertas atuais...
python ferramentas\preparar_consultas_ufabc_next.py --config config\config.json
if errorlevel 1 goto erro

echo Abrindo o Edge para atualizar as avaliacoes do UFABC Next...
python ferramentas\coletar_avaliacoes_ufabc_next.py --config config\ufabc_next.json --consultas dados\consultas_ufabc_next.csv --saida-json dados\avaliacoes_docentes.json --saida-html saidas\relatorio_avaliacoes_docentes.html --saida-local saidas\avaliacoes_docentes_local_com_comentarios_NAO_COMPARTILHAR.json --sessao dados\sessao_ufabc_next
if errorlevel 1 goto erro

if exist "saidas\relatorio_avaliacoes_docentes.html" start "" "saidas\relatorio_avaliacoes_docentes.html"
echo.
echo Avaliacoes atualizadas. Volte ao planejador e gere o planejamento novamente.
pause
exit /b 0

:erro
echo.
echo Nao foi possivel atualizar as avaliacoes. Revise a mensagem acima.
pause
exit /b 1
