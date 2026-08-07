# UFABC Academic Planner

Planejador acadêmico desenvolvido em Python e Streamlit para auxiliar estudantes da Universidade Federal do ABC na montagem de grades, análise curricular e simulação de diferentes trajetórias de formação.

O projeto surgiu de um problema real da minha própria rotina acadêmica. Na UFABC, o sistema quadrimestral, a possibilidade de cursar diferentes formações, as equivalências entre matrizes e a variação das disciplinas ofertadas tornam o planejamento acadêmico um problema com muitas combinações possíveis.

A proposta foi transformar esse processo em uma aplicação capaz de organizar os dados, avaliar diferentes cenários e apoiar a tomada de decisão.

![Visão geral do UFABC Academic Planner](assets/overview.png)

---

## O problema

Planejar um quadrimestre não envolve apenas escolher disciplinas disponíveis.

É necessário considerar simultaneamente fatores como:

- histórico acadêmico
- matriz curricular
- disciplinas já concluídas e em andamento
- obrigatórias, opções limitadas e créditos livres
- conflitos de horário
- aulas semanais e quinzenais
- campus e turno
- carga acadêmica desejada
- quantidade de vagas
- preferências pessoais
- recomendações acadêmicas
- diferentes possibilidades de formação

Quando mais de um curso é considerado, o problema se torna ainda maior por envolver equivalências, disciplinas compartilhadas, ordem de conclusão dos diplomas e impacto de cada escolha no tempo restante de graduação.

---

## A solução

O UFABC Academic Planner processa informações acadêmicas e gera diferentes cenários de planejamento.

A aplicação permite analisar desde a próxima matrícula até uma trajetória acadêmica completa.

Entre as principais funcionalidades estão:

- leitura do histórico acadêmico
- processamento das turmas ofertadas
- identificação de disciplinas concluídas e pendentes
- acompanhamento da integralização curricular
- geração automática de grades sem conflito
- comparação de diferentes alternativas de matrícula
- classificação das grades segundo diferentes objetivos
- análise de carga acadêmica e horários
- planejamento de formação única, dupla ou múltipla
- comparação entre matrizes curriculares
- identificação de disciplinas compartilhadas
- estimativa de datas de conclusão
- análise de gargalos acadêmicos
- editor manual de grade
- geração de relatórios
- integração opcional com avaliações docentes

---

## Planejamento de trajetória

Além da matrícula do próximo quadrimestre, o sistema permite simular diferentes caminhos acadêmicos.

É possível comparar mudança de curso, formação simultânea ou sequencial e diferentes prioridades entre diplomas.

A projeção apresenta informações como:

- previsão mínima de conclusão
- previsão prudente
- créditos ainda necessários
- créditos únicos da trajetória
- aproveitamento entre matrizes
- gargalos para cada formação

![Análise de trajetória acadêmica](assets/trajectory-analysis.png)

---

## Geração e avaliação das grades

O sistema analisa as disciplinas e turmas disponíveis e constrói combinações compatíveis com os critérios definidos pelo usuário.

Durante a busca são considerados fatores como:

- conflitos de horário
- carga de créditos
- prioridade curricular
- disponibilidade de vagas
- atividades práticas
- intervalos entre aulas
- preferências acadêmicas
- progresso dentro da matriz

As alternativas podem ser avaliadas com objetivos diferentes, permitindo encontrar, por exemplo, uma grade mais compacta, uma maior progressão curricular ou uma carga mais equilibrada.

![Alternativas de matrícula](assets/ranking-objectives.png)

---

## Busca e otimização

O programa não apresenta apenas a primeira combinação encontrada.

As diferentes possibilidades de matrícula são analisadas e classificadas para permitir a comparação entre soluções viáveis.

A aplicação também informa a cobertura da busca realizada, incluindo quantidade de disciplinas analisadas, combinações avaliadas, grades únicas encontradas e cobertura da fronteira de Pareto.

![Validação da busca](assets/search-validation.png)

---

## Visualização da grade

As alternativas selecionadas são convertidas em uma grade semanal para facilitar a análise dos horários e da distribuição das disciplinas ao longo da semana.

![Grade semanal](assets/schedule.png)

---

## Tecnologias utilizadas

### Desenvolvimento

- Python
- Streamlit
- Pandas
- OpenPyXL
- PDFPlumber

### Dados e integração

- JSON
- CSV
- Excel
- processamento de PDFs
- Playwright

### Qualidade

- Pytest
- testes automatizados
- validação de regras acadêmicas
- testes de integração

### Outros

- HTML
- Git
- GitHub

---

## Estrutura do projeto

```text
ufabc-academic-planner/
│
├── app.py
├── main.py
├── requirements.txt
│
├── planejador/
│   ├── academico.py
│   ├── analise.py
│   ├── avaliacoes_docentes.py
│   ├── configuracao.py
│   ├── curriculo.py
│   ├── historico.py
│   ├── modelos.py
│   ├── multicurso.py
│   ├── ofertas.py
│   ├── planejador.py
│   ├── relatorio.py
│   ├── trajetorias.py
│   └── utils.py
│
├── tests/
├── config/
├── dados/
├── dados_fontes/
├── ferramentas/
├── entradas/
├── saidas/
└── assets/
