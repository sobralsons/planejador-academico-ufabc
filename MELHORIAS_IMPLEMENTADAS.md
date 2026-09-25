> **DOCUMENTO HISTÓRICO — NÃO REPRESENTA O ESTADO ACADÊMICO ATUAL.** Este arquivo registra uma etapa anterior do protótipo. Contagens de testes e expressões como “validado” referem-se ao escopo técnico/estrutural daquele momento e não certificam suporte acadêmico público. Consulte [docs/ESTADO_ACADEMICO_ATUAL.md](docs/ESTADO_ACADEMICO_ATUAL.md).

# Registro histórico de melhorias implementadas

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

> **Correção de estado:** a coleta autenticada automática descrita abaixo pertence ao protótipo histórico e não faz parte do fluxo atual autorizado. O código atual não deve reativar login/coleta automática sem fonte autorizada e revisão específica de segurança e privacidade. A interface interna atual aceita apenas importação manual de JSON quando esse dado é fornecido legitimamente pelo usuário.

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
- manifesto estrutural e 51 testes automatizados.

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

## Atualização — combinação de avaliações e catálogo 2025–2026

- avaliação docente combinada: 60% avaliação geral + 40% avaliação da disciplina, quando ambas existem;
- visão geral e visão específica exibidas lado a lado no relatório;
- opção de usar somente a avaliação geral ao desligar a combinação na interface;
- recomendações atualizadas pelo Catálogo de Disciplinas UFABC 2025–2026;
- fallback textual para recomendações oficiais ainda não convertidas em códigos;
- 51 testes automatizados aprovados após as correções.


## Ajuste de matrícula — PDF oficial

- leitura direta do PDF de ajuste publicado pela UFABC;
- uso de vagas remanescentes para novas inclusões;
- identificação de turmas de alta demanda;
- separação entre a oferta inicial (Excel) e a oferta de ajuste (PDF);
- seleção da matrícula já deferida a partir do Excel inicial, inclusive para turmas ausentes no PDF de ajuste;
- uso do PDF apenas para disponibilidade de novas inclusões e diagnóstico;
- seleção manual das turmas já deferidas como base do ajuste;
- remoção e substituição de disciplinas com recálculo de conflitos e métricas;
- diagnóstico explícito de falta de vagas remanescentes;
- exibição da linha/curso de origem da oferta para conferência no SIGAA;
- alias oficial de Programação Estruturada entre códigos 2015 e 2023 preservando matrizes antigas;
- cache da leitura do PDF durante a sessão para evitar reprocessamento em cada rerun do Streamlit;
- 52 testes automatizados aprovados.


## Ajuste de matrícula — reconstrução da matrícula já deferida

- a lista de "Minha matrícula atual" agora lê todas as turmas do Excel inicial do campus/turno, sem filtrar pela matriz principal selecionada;
- componentes de outra engenharia, matriz, opção livre ou compartilhados continuam disponíveis para seleção;
- turmas já deferidas fora da matriz principal são mantidas temporariamente como componentes livres apenas para reconstrução da grade e verificação de conflitos;
- o código completo da turma aparece no início do seletor para facilitar a busca;
- validação real com NA1ESTM004-17SA, NC1ESMA002-23SA, NA1ESTO008-17SA, NA1ESTA019-17SA e NA1ESTM002-17SA;
- 54 testes automatizados aprovados.
