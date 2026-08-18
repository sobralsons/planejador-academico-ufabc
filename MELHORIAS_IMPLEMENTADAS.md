# Melhorias implementadas — versão validada

- Certificado de busca completa ou limitada.
- Configuração efetiva salva no resumo JSON.
- Aprovações projetadas podem valer como recomendações cumpridas no modo otimista.
- Termodinâmica Estatística passa a competir normalmente quando Termodinâmica de Materiais está presumida aprovada.
- Recomendações anteriores aparecem em cada cartão de disciplina, com status.
- Métrica de progressão separa:
  - vínculos de recomendação atendidos;
  - pendências futuras impactadas;
  - disciplinas totalmente destravadas.
- Estimativa de quadrimestres e período provável de conclusão por grade.
- Indicadores de gargalos de créditos, TG, estágio e cadeia curricular.
- Análise acadêmica com aprovações, reprovações, conceitos e coeficientes.
- Gráficos de taxa de aprovação, distribuição de conceitos e evolução por período.
- Interface com controle do ritmo futuro, margem de formatura e comportamento da projeção otimista.
- Resumo JSON ampliado com configurações, validação, análise e projeções.
- 17 testes automatizados.

- Previsão de formatura corrigida para tratar estágio e TG como atividades paralelas à carga regular.
- Seletor de situação do estágio: não iniciado, em andamento projetado ou concluído/validado.
- Auditoria separando créditos confirmados no histórico e créditos reconhecidos no cenário projetado.
- Detalhamento da previsão: carga regular, créditos de TG, créditos de estágio e gargalo determinante.

## Integração UFABC Next

- coleta automática por Playwright após login institucional;
- consulta direta à API usando a sessão local do navegador;
- avaliação geral e por disciplina;
- análise local dos comentários;
- separação entre qualidade pedagógica e risco acadêmico;
- regressão de peso para amostras pequenas;
- ajuste configurável no ranking;
- relatório por disciplina e resumo geral dos docentes utilizados;
- importação manual de JSON como alternativa;
- limpeza da sessão autenticada pela interface;
- nenhum bloqueio automático por avaliação.

## Editor interativo de grade

- Seleção de uma das grades padrão como base.
- Remoção de várias disciplinas.
- Recalculo em tempo real das métricas.
- Sugestões ordenadas de turmas compatíveis.
- Diagnóstico das disciplinas incompatíveis.
- Histórico de desfazer e restauração da base.
- Exportação da grade personalizada em HTML e JSON.


## Expansão multicurso

- BC&T 2015, BCC 2017/2023, BCD 2023 e EI 2017/2023;
- comparação de tempo de formação por curso;
- equivalências e tabelas de transição;
- total oficial separado de extensão e atividades;
- curso-base na previsão;
- certificado de ranking exato e Pareto parcial/completo;
- configurações avançadas da busca;
- manifesto estrutural e 44 testes automatizados.

# Laboratório de Trajetórias

- painel inicial para continuar, mudar, fazer dois ou três cursos;
- ordem de prioridade dos diplomas;
- estratégias simultânea, híbrida e sequencial;
- análise preliminar usando somente o histórico;
- recálculo após a escolha da grade do próximo quadrimestre;
- créditos únicos e economia por sobreposição;
- obrigatórias compartilhadas e aproveitamento entre categorias;
- escolha estratégica de OL/livres comuns;
- data estimada de cada diploma e de todas as formações;
- comparador de cenários “e se eu mudar?”;
- roteiro acadêmico aproximado por quadrimestre;
- indicador transparente de confiança;
- relatório completo visualizado dentro da própria interface.
