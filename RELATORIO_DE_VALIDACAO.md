> **DOCUMENTO HISTÓRICO — NÃO REPRESENTA O ESTADO ACADÊMICO ATUAL.** Este arquivo registra uma etapa anterior do protótipo. Contagens de testes e expressões como “validado” referem-se ao escopo técnico/estrutural daquele momento e não certificam suporte acadêmico público. Consulte [docs/ESTADO_ACADEMICO_ATUAL.md](docs/ESTADO_ACADEMICO_ATUAL.md).

# Relatório de validação — Planejador Multicurso UFABC

## Resultado da suíte

**51 testes automatizados aprovados.**

A execução é feita por:

```text
validar_windows.bat
```

O atalho instala as dependências e executa `python -m pytest -q`, cobrindo também os testes funcionais escritos fora de classes `unittest`.

## Matrizes verificadas estruturalmente naquele estágio

O arquivo `dados/validacao_curriculos.json` fixa, por currículo:

- quantidade de componentes obrigatórios e de opção limitada;
- soma dos créditos cadastrados;
- SHA-256 da lista ordenada de códigos;
- fontes documentais utilizadas.

Currículos verificados:

1. BC&T 2015;
2. Engenharia de Materiais 2017;
3. BCC 2017;
4. BCC 2023;
5. BCD 2023;
6. Engenharia de Informação 2017;
7. Engenharia de Informação 2023.

## Cobertura dos testes

- leitura e normalização de códigos;
- T-P-I e T-P-E-I;
- horários adjacentes, sobrepostos e quinzenais;
- janelas internas versus extremidades livres;
- histórico, conceitos, reprovações e recuperações;
- equivalências 2017/2023;
- código canônico de Programação Estruturada no BCC 2023;
- código canônico e alias do TCC do BCD;
- totais oficiais versus créditos usados na projeção da EI 2023;
- PGC/TCC/TG e suas durações mínimas;
- estágio em andamento por currículo;
- curso-base impedindo conclusão do curso específico antes do BC&T;
- créditos de disciplina equivalente sem dupla contagem como livre;
- ranking curricular e projeção otimista;
- busca exaustiva mesmo quando o limite de retenção é atingido;
- aviso correto quando candidatas são truncadas;
- avaliações docentes e preferência flexível;
- editor de grade e diagnóstico de conflitos;
- relatório multicurso e cartões de formatura;
- curso único, mudança, dupla e tríplice formação;
- créditos únicos, sobreposição curricular e roteiro por diploma;
- estratégias simultânea, híbrida e sequencial;
- relatório completo de trajetória e visualização embutida;
- extração do código de disciplina a partir do código de turma do PDF de ajuste;
- bloqueio de novas inclusões quando a turma possui 0 vagas remanescentes;
- sugestão de alternativas do ajuste somente quando há vagas remanescentes.

## Testes integrados com histórico e oferta reais

Todas as sete matrizes foram usadas como currículo principal, mantendo a mesma oferta e o mesmo histórico. Em todas as execuções foram geradas pelo menos três grades.

| Currículo principal | Candidatas analisadas | Conjuntos únicos | Cobertura global | Pareto |
|---|---:|---:|---|---|
| Materiais 2017 | 13/13 | 198 | completa | completa |
| BCC 2017 | 14/14 | 432 | completa | completa |
| BCC 2023 | 15/15 | 531 | completa | completa |
| BCD 2023 | 10/10 | 24 | completa | completa |
| EI 2017 | 16/16 | 898 | completa | completa |
| EI 2023 | 20/20 | 2.324 | completa | parcial por retenção |
| BC&T 2015 | 20/52 no teste conservador | 1.110 | limitada por candidatas | completa no subconjunto |

Na EI 2023, o limite de retenção não interrompeu a enumeração: o ranking padrão permaneceu exato, enquanto somente o Pareto foi calculado sobre 1.200 grades retidas.

O BC&T possui uma lista de opção limitada muito ampla. O certificado identifica corretamente quando o limite de candidatas reduz a garantia global. A interface permite aumentar esse limite.

## Correções detectadas pelos testes

- o estágio do currículo principal agora respeita `estagios_status[curso]`, em vez de sempre usar o campo legado;
- equivalências na grade não são somadas novamente como créditos livres;
- o limite do pool deixou de encerrar a busca antecipadamente;
- rankings padrão e perfis são calculados sobre todas as combinações válidas das candidatas analisadas;
- a previsão de um curso específico não pode anteceder a previsão do BC&T.

## Validação da interface

O código da interface foi compilado e verificado por testes estáticos que confirmam a presença do Laboratório de Trajetórias, mudança de curso, dupla e tríplice formação, cartões de previsão, visualização do relatório completo, certificado da busca e ausência de widgets duplicados. O motor, os relatórios HTML/TXT/JSON e as sete execuções integradas foram executados de ponta a ponta no ambiente de testes.

A abertura do Streamlit no navegador depende da instalação das dependências no computador do usuário, realizada automaticamente por `executar_windows.bat`.

## Limites acadêmicos

A validação histórica confirmou coerência técnica com os pacotes estruturados naquele estágio. Ela não constitui validação acadêmica vigente nem substitui a conferência oficial de:

- integralização no SIGAA;
- equivalências excepcionais;
- lista de OL aplicável a cada vínculo;
- extensão e atividades complementares;
- deferimento de estágio e trabalho final;
- vagas e oferta futura.

## Atualização — avaliações docentes e recomendações do catálogo 2025–2026

- A avaliação geral do docente passou a ser a base do ranking.
- Quando existe avaliação da disciplina específica, as duas fontes são combinadas em 60% geral + 40% disciplina.
- O relatório exibe separadamente o resultado geral e o resultado específico para permitir conferência.
- Amostras pequenas continuam tendo impacto reduzido antes da combinação.
- As recomendações acadêmicas foram atualizadas a partir do Catálogo de Disciplinas UFABC 2025–2026.
- Recomendações textuais que não puderem ser convertidas automaticamente em código continuam visíveis no relatório em vez de aparecerem como inexistentes.
- Caso de regressão incluído: MCTB008-17 — Cálculo de Probabilidade reconhece Funções de Várias Variáveis, Introdução à Probabilidade e à Estatística e Matemática Discreta.

Resultado da suíte após a atualização: **51 testes automatizados aprovados**.


## Atualização — ajuste de matrícula 2026.3

O fluxo de ajuste foi validado com o PDF oficial de turmas do ajuste de 2026.3. O parser reconhece a estrutura de curso, código de turma, turma, teoria, prática, campus, turno, T-P-E-I, vagas totais, vagas remanescentes, alta demanda e docentes.

No modo de ajuste, a enumeração automática considera apenas turmas com vagas remanescentes positivas para novas inclusões. Turmas com zero vagas continuam disponíveis na seleção da matrícula atual, pois o aluno pode já estar deferido nelas e desejar mantê-las ou soltá-las.

A integração ponta a ponta foi executada com histórico, currículo de Engenharia de Materiais 2017 e o PDF de ajuste, sem erros de parsing. Também foi validada a leitura de Programação Estruturada com o código antigo ofertado no PDF e sua associação à matriz 2023 quando aplicável.

Resultado final da suíte: **51 testes automatizados aprovados**.


## Correção — matrícula atual independente da matriz principal

Foi identificado que a leitura do Excel usado para reconstruir a matrícula já deferida ainda aplicava o filtro da matriz principal. Isso ocultava componentes válidos que o estudante já havia obtido na matrícula comum quando esses componentes pertenciam a outra engenharia, outra matriz ou não constavam no currículo principal.

A leitura da matrícula atual passou a percorrer todas as turmas do Excel no campus e turno selecionados, sem filtro curricular. Para o editor, componentes externos à matriz principal recebem uma representação temporária como livre, somente para preservar créditos, horários, docentes e conflitos da matrícula real; essa classificação temporária não altera a matriz acadêmica oficial.

Validação com a oferta oficial 2026.3 confirmou a presença das cinco turmas informadas pelo usuário: NA1ESTM004-17SA, NC1ESMA002-23SA, NA1ESTO008-17SA, NA1ESTA019-17SA e NA1ESTM002-17SA. A grade conjunta foi reconstruída com 18 créditos e sem conflito de horário.

Resultado final da suíte: **54 testes automatizados aprovados**.
