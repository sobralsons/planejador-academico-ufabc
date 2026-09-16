# Etapa 1 — núcleo revisado, setembro de 2026

Referência: ZIP `planejador_academico_ufabc_ui_simplificada_2026_09(1).zip`, SHA-256 `e719bff08b5407784ce6f2b9dfcb63d9f54c171ea76a5a6c4c5383638595e3b5`.

## Alterações

- Consolidação da interface simplificada e das correções de matrícula inicial/ajuste do ZIP.
- Reconhecimentos guardam as origens no histórico; fontes já aproveitadas na matriz não geram livres adicionais. A aplicação de regras simples, compostas e convalidações estabiliza independentemente da ordem, respeitando a direção cadastrada.
- O chamador deve fornecer somente regras aplicáveis à versão curricular analisada. O esquema atual ainda não representa vigência e decisões discricionárias: sua validação é parte da etapa 2.
- Nomes iguais não autorizam equivalência. Tarefas futuras com códigos diferentes permanecem separadas; a alocação otimizada de equivalências dirigidas entre diplomas será tratada no modelo curricular da etapa 2.
- Histórico com linha incompleta é rejeitado com localização do problema. As três leituras de oferta validam cada campo e trecho de horário; turmas parcialmente interpretadas são rejeitadas com avisos, também exibidos no resultado da interface.
- Disciplinas exigidas são preservadas no corte de candidatas. Cada perfil compara todas as combinações de turmas visitadas, independentemente dos demais perfis. É possível que perfis diferentes recomendem a mesma grade.
- Pareto possui limites explícitos de retenção e apresentação, separados da completude do cálculo. A contagem de grades concretas passou a registrar cada escolha uma única vez.
- Extensão/atividades complementares pendentes e tarefas além do horizonte impedem marcar conclusão na trajetória. Datas sem suporte são apresentadas como indeterminadas, inclusive nos relatórios.
- Uploads, configuração, avaliações importadas e saídas da interface são temporários e separados por sessão. Não foram implementados contas, autorização de servidor ou políticas de retenção de um produto em nuvem.
- Defaults de docentes vazios; projeção conservadora; nenhum estágio presumido em andamento. BC&T 2015, campus, turno e período são exemplos selecionáveis, não detecção do vínculo. O aluno deve confirmar suas escolhas.
- A coleta autenticada foi removida da interface e do repositório. O módulo aceita somente uma base agregada importada de fonte autorizada; nenhuma avaliação real é distribuída no projeto.

## Validação

73 testes aprovados: 54 cenários herdados, dez regressões da auditoria e nove verificações complementares. Duas expectativas antigas foram atualizadas com mudança explícita de contrato: sobreposição agora exige o mesmo código na fixture; um Pareto completo pode existir mesmo quando o pool padrão foi limitado, se uma alternativa domina a outra.

A interface também foi executada com o ambiente de testes do Streamlit: carregou sem exceções, exibiu os cinco controles de upload esperados e não expôs ações de coleta autenticada.

A verificação complementar cobre ciclos e equivalências compostas, os três leitores de ofertas, isolamento/limpeza de sessões, propagação de conclusão indeterminada até o HTML, comparação dos perfis com enumeração independente em 12 instâncias pequenas e orquestração com saídas privadas. Nessa última, somente a extração de histórico é simulada.

Com Python 3.12, instalar `requirements-test.txt` e executar `python -m pytest -q`. As dependências diretas estão fixadas nas versões verificadas; este arquivo não é um lock completo das dependências transitivas.

Também foi verificada a sintaxe do app, CLI, motor e ferramentas. A interface não foi validada em navegador; esta etapa não certifica UX, acessibilidade, carga, integralização oficial ou prontidão para produção pública.

## Próxima etapa

Modelar requisitos, reconhecimento e alocação de créditos com fonte, versão e revisão humana. Priorizar BC&T e Ciência de Dados, escolhendo as matrizes e os vínculos aplicáveis antes de declarar suporte. Validar com casos institucionais revisados; depois expor o núcleo por API e construir a experiência web.
