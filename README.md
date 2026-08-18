# UFABC Academic Planner

Planejador acadêmico desenvolvido em **Python** para apoiar estudantes da Universidade Federal do ABC na montagem de grades, análise curricular e simulação de trajetórias de formação.

O projeto nasceu de um problema real: na UFABC, o sistema quadrimestral, as diferentes matrizes curriculares, as equivalências entre cursos e a variação das turmas ofertadas tornam o planejamento acadêmico um problema com muitas combinações possíveis.

A proposta é transformar essas informações em um processo estruturado de apoio à decisão, permitindo comparar alternativas em vez de simplesmente escolher a primeira combinação disponível.

> **Status do repositório:** esta versão pública está sendo preparada como portfólio. A documentação apresenta o projeto e suas funcionalidades, enquanto o código-fonte completo ainda precisa passar por uma revisão final para garantir que históricos, sessões autenticadas, dados pessoais e arquivos locais não sejam publicados por engano.

---

## O problema

Planejar um quadrimestre envolve considerar simultaneamente fatores como histórico acadêmico, matriz curricular, disciplinas concluídas e em andamento, obrigatórias e opções limitadas, conflitos de horário, campus, turno, carga desejada, disponibilidade de vagas e preferências pessoais.

Quando mais de uma formação é considerada, entram também equivalências, disciplinas compartilhadas, ordem dos diplomas e o impacto de cada escolha no tempo restante de graduação.

---

## O que a aplicação faz

Entre as funcionalidades já desenvolvidas estão:

- leitura e interpretação do histórico acadêmico;
- processamento das turmas ofertadas;
- identificação de disciplinas concluídas, em andamento e pendentes;
- acompanhamento da integralização curricular;
- geração automática de grades sem conflito;
- comparação de diferentes alternativas de matrícula;
- ranking de grades segundo objetivos diferentes;
- análise de carga acadêmica e distribuição dos horários;
- planejamento de curso único, mudança de curso e múltiplas formações;
- comparação entre matrizes e aproveitamento de disciplinas;
- estimativa de períodos de conclusão e identificação de gargalos;
- editor manual de grade;
- geração de relatórios;
- integração opcional com avaliações docentes.

---

## Busca e otimização

O planejador não apresenta apenas a primeira combinação encontrada. As soluções viáveis são comparadas por critérios diferentes, como:

- progressão curricular;
- compactação da grade;
- equilíbrio de carga;
- avanço em créditos;
- quantidade de janelas entre aulas;
- preferências acadêmicas;
- disponibilidade de vagas;
- componentes práticos;
- risco e avaliações docentes quando disponíveis.

A aplicação também possui mecanismos de validação da busca para indicar quando o conjunto de alternativas foi percorrido de forma completa ou quando algum limite técnico restringiu a análise.

---

## Planejamento de trajetória

Além da próxima matrícula, o sistema simula diferentes caminhos acadêmicos e permite comparar cenários de formação.

A projeção considera, entre outros pontos:

- créditos ainda necessários;
- disciplinas compartilhadas entre matrizes;
- aproveitamento curricular;
- ritmo de créditos por quadrimestre;
- componentes especiais, como estágio e trabalho de graduação;
- cenários otimista e prudente;
- possíveis gargalos de conclusão.

O objetivo não é substituir as regras oficiais da universidade, mas organizar as informações e tornar as consequências de cada escolha mais visíveis.

---

## Tecnologias

### Aplicação e dados

`Python` · `Streamlit` · `Pandas` · `NumPy` · `JSON` · `CSV` · `Excel`

### Processamento e integração

`OpenPyXL` · `PDFPlumber` · `Playwright` · processamento de PDFs

### Qualidade e desenvolvimento

`Pytest` · testes automatizados · `Git` · `GitHub`

> A lista acima descreve tecnologias utilizadas no projeto. O `requirements.txt` público ainda será revisado junto com a publicação do código-fonte para refletir exatamente as dependências necessárias à versão disponibilizada.

---

## Validação

O projeto possui uma suíte de testes voltada a regras acadêmicas e ao mecanismo de geração das grades. Entre os cenários já trabalhados estão conflitos e sobreposições de horário, componentes quinzenais, créditos e equivalências, diferentes currículos, trajetórias com mais de uma formação, ranking de alternativas e validação da busca.

Uma etapa importante antes da publicação integral do código é transformar esses testes em uma suíte totalmente reproduzível a partir de dados fictícios ou públicos.

---

## Privacidade e segurança

O planejador pode trabalhar com histórico acadêmico e, opcionalmente, com uma sessão autenticada para coleta de informações externas. Por isso, arquivos pessoais e credenciais **não devem fazer parte do repositório público**.

O `.gitignore` deste projeto já exclui, entre outros itens:

- arquivos enviados pelo usuário em `entradas/`;
- sessões autenticadas locais;
- arquivos `.env` e secrets;
- resultados locais com comentários completos;
- caches e ambientes virtuais.

Antes da publicação do código será feita também uma revisão do histórico Git, já que um `.gitignore` não remove informações que tenham sido commitadas anteriormente.

---

## Próximos passos do portfólio

1. Publicar uma versão do código sem dados pessoais ou credenciais.
2. Disponibilizar dados fictícios de demonstração.
3. Revisar e fixar as dependências da aplicação.
4. Tornar a suíte de testes reproduzível no repositório público.
5. Adicionar screenshots e/ou GIFs de demonstração com dados anonimizados.
6. Preparar uma versão executável ou deploy de demonstração.
7. Evoluir a arquitetura gradualmente para separar interface, regras de negócio e persistência de dados.

---

## Objetivo do projeto

Mais do que automatizar uma matrícula, o UFABC Academic Planner é um projeto para explorar **programação, tratamento de dados, modelagem de regras, busca combinatória, otimização multicritério, testes e desenvolvimento de aplicações** a partir de um problema real.

Ele também faz parte da minha evolução em desenvolvimento Python, dados e construção de soluções que transformam informações complexas em decisões mais claras.

---

### Aviso

Este é um projeto pessoal e independente. Não é uma ferramenta oficial da Universidade Federal do ABC e não substitui o SIGAA, os Projetos Pedagógicos dos Cursos ou orientações oficiais da UFABC.