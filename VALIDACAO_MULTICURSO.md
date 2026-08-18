# Validação técnica e acadêmica da expansão multicurso

## Arquitetura

O motor de horários é independente da matriz. Cada currículo é um pacote JSON com:

- metadados de integralização;
- disciplinas e categorias;
- quadrimestre recomendado;
- recomendações pedagógicas;
- tipo de componente;
- equivalências e transições.

O registro central fica em `dados/registro_curriculos.json`.

## Créditos modernos

Para BCC 2023, BCD 2023 e EI 2023, o sistema separa:

- créditos de disciplinas e componentes integralizadores usados no ritmo;
- carga oficial total;
- extensão;
- atividades complementares.

Essa separação evita contar a extensão duas vezes quando ela está incorporada a disciplinas.

## Formação específica e BC&T

Os cursos específicos cadastrados apontam para `bct_2015` como curso-base desta versão. A previsão final usa o maior prazo entre o currículo específico e o BC&T, sem somar os créditos dos dois cursos, pois há amplo aproveitamento simultâneo.

## Busca

A enumeração percorre todos os ramos do conjunto analisado. Para cada conjunto de disciplinas, conserva a melhor combinação de turmas.

- o limite de candidatas pode restringir o universo;
- o limite de retenção não interrompe a busca;
- Top 5, perfis e reservas são selecionados no conjunto completo analisado;
- Pareto usa o conjunto completo ou o subconjunto retido, conforme o tamanho.

## Reprodutibilidade

O resumo JSON registra:

- configuração efetiva;
- cobertura e certificado da busca;
- auditoria de cada curso;
- estimativa por grade;
- comparação multicurso;
- grade com maior sobreposição;
- avaliações docentes utilizadas.
