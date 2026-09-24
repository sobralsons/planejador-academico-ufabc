> **Desenvolvimento atual:** o produto público continua bloqueado até a validação acadêmica completa. Para trabalhar no PC, use o fluxo local documentado em [docs/AMBIENTE_LOCAL.md](docs/AMBIENTE_LOCAL.md).

# Planejador Acadêmico e de Trajetórias — UFABC

Aplicação local para planejar **a trajetória completa** e a matrícula de cada quadrimestre. O sistema lê o histórico, compara matrizes curriculares, estima datas de conclusão, identifica disciplinas compartilhadas e monta grades sem conflito.

## O que mudou nesta versão

A página inicial agora funciona como um **Laboratório de Trajetórias**. Antes de pensar nos horários, você pode responder:

- quero continuar no meu curso atual;
- quero avaliar uma mudança de curso;
- quero concluir dois cursos;
- quero planejar três formações;
- ainda não decidi e quero comparar alternativas.

Você informa:

1. curso atual;
2. primeira formação prioritária;
3. até duas formações adicionais;
4. estratégia simultânea, híbrida ou sequencial;
5. período inicial, ritmo futuro e margem prudente;
6. cenário otimista ou conservador das disciplinas em andamento.

Com apenas o histórico, o programa já calcula uma análise preliminar. Depois que uma grade é gerada, a trajetória é recalculada considerando as matérias escolhidas para o próximo quadrimestre.

## Interface 2026.09

A camada visual foi modernizada sem alterar os algoritmos acadêmicos. A nova interface usa componentes adicionais com fallback para o Streamlit nativo:

- **Shadcn UI** para cards de métricas e hierarquia visual;
- **AgGrid** para tabelas exploráveis com filtros, ordenação e redimensionamento de colunas;
- **Streamlit Sortables** para ordenar por drag-and-drop as formações adicionais em planos com três diplomas;
- novo tema visual, tabs em formato de fluxo, sidebar refinada e melhor organização do modo de ajuste.

A lógica de trajetória, geração de grades, avaliações docentes e ajuste de matrícula permanece independente dessa camada visual.

## Currículos incluídos

- BC&T 2015;
- Engenharia de Materiais 2017;
- Bacharelado em Ciência da Computação 2017;
- Bacharelado em Ciência da Computação 2023;
- Bacharelado em Ciência de Dados 2023;
- Engenharia de Informação 2017;
- Engenharia de Informação 2023.

## Em quanto tempo posso me formar?

Para cada formação escolhida, a interface mostra:

- data se o curso fosse cursado isoladamente;
- data dentro do plano conjunto;
- faixa prudente;
- percentual estimado já integralizado;
- créditos regulares pendentes;
- gargalos de recomendações, trabalho final, estágio, extensão e atividades complementares.

Para duas ou três formações, o programa calcula ainda:

- créditos que seriam necessários somando os cursos separadamente;
- créditos **únicos** estimados depois de descontar sobreposições;
- economia de créditos por aproveitamento simultâneo;
- disciplinas obrigatórias compartilhadas;
- opções limitadas/livres que podem atender mais de uma matriz;
- previsão de quando cada diploma tende a ser concluído;
- previsão de quando todas as formações estarão concluídas;
- roteiro aproximado por quadrimestre.

## Como o cálculo conjunto funciona

1. O histórico é reclassificado em cada matriz com suas equivalências oficiais.
2. As obrigatórias ainda pendentes são unificadas por disciplina equivalente/nome curricular.
3. Uma disciplina obrigatória em um curso pode preencher opção limitada ou livre em outro.
4. Para as cotas flexíveis restantes, uma heurística de cobertura escolhe disciplinas válidas no maior número de cursos possível.
5. O prazo respeita o maior entre:
   - carga regular única restante;
   - cadeias de recomendações;
   - duração do trabalho final;
   - estágio obrigatório;
   - conclusão do curso de ingresso.
6. A estratégia escolhida altera a ordem aproximada:
   - **simultânea:** prioriza matérias que avançam vários cursos;
   - **híbrida:** faz primeiro as compartilhadas e depois concentra na prioridade principal;
   - **sequencial:** tenta concluir a primeira formação antes da seguinte.

A projeção não inventa ofertas futuras. O roteiro é acadêmico e deve ser recalculado em cada matrícula com a planilha real de turmas.

## Relatório completo da trajetória

A aba **Minha trajetória** permite:

- visualizar o relatório dentro da própria interface;
- baixar `saidas/relatorio_trajetoria_academica.html`;
- comparar cenários de continuar, mudar ou acumular diplomas;
- consultar a confiança e todas as premissas do cálculo.

O relatório multicurso anterior continua disponível, mas o novo relatório de trajetória é mais completo e orientado à decisão.

## Planejamento de matrícula

O sistema mantém:

- cinco grades padrão, com mínimo de três quando viável;
- perfis de progressão, grade compacta, carga equilibrada e menor risco;
- professores e avaliações agregadas importadas de fonte autorizada;
- aulas semanais e quinzenais;
- T-P-E-I, práticas, janelas e permanência;
- recomendações do PPC;
- editor para remover e substituir disciplinas;
- certificado de cobertura e exatidão da busca.

## Ajuste de matrícula

Quando a UFABC publica o PDF oficial de **Ajuste de Matrículas**, o planejador passa a trabalhar com **duas fontes ao mesmo tempo**: a planilha Excel da matrícula inicial para reconstruir as turmas já deferidas e o PDF do ajuste para consultar vagas remanescentes e novas possibilidades.

No modo de ajuste, o sistema:

- lê diretamente o PDF oficial de turmas;
- reconhece horários, docentes, T-P-E-I, campus, turno e código da turma;
- usa **vagas remanescentes** como disponibilidade para novas inclusões;
- usa a planilha da matrícula inicial para listar as turmas em que o aluno já está matriculado, mesmo quando elas não aparecem mais no PDF de ajuste;
- mantém o PDF de ajuste separado para avaliar somente as novas inclusões possíveis;
- identifica a marcação de **alta demanda**;
- informa a qual linha/curso do PDF a oferta está vinculada;
- permite selecionar a matrícula atual como ponto de partida;
- permite soltar uma ou várias disciplinas e recalcular a grade;
- sugere somente novas turmas compatíveis que ainda possuem vagas remanescentes;
- explica quando uma alternativa não pode ser incluída por falta de vaga, conflito ou regra acadêmica.

Fluxo recomendado:

1. envie o histórico normalmente;
2. envie a planilha Excel de **Turmas ofertadas — matrícula inicial**;
3. envie o PDF no campo **Turmas para ajuste de matrícula**;
4. gere o planejamento;
5. abra a aba **Ajustar matrícula**;
6. marque exatamente as turmas em que você está matriculado — essa lista vem do Excel inicial;
7. clique em **Usar esta matrícula como base do ajuste**;
8. remova as disciplinas que pretende soltar e compare as substituições disponíveis no PDF de ajuste.

As vagas do PDF são uma fotografia do momento de publicação. O deferimento final e a disponibilidade real devem ser confirmados no SIGAA.

## Desenvolvimento local

O fluxo recomendado deixou de ser “extrair ZIP”. Clone o repositório no PC, trabalhe em uma pasta Git local e use um ambiente virtual Python.

No Windows:

1. clone o repositório;
2. faça checkout da branch `develop`, conforme [docs/AMBIENTE_LOCAL.md](docs/AMBIENTE_LOCAL.md);
3. execute `preparar_ambiente_windows.bat`;
4. abra a pasta no VS Code;
5. use `executar_windows.bat` para o protótipo interno ou `executar_api_windows.bat` para a API local.

O conteúdo real de `documentos-fonte/`, `.env.local` e entradas acadêmicas pessoais é local e não deve ser enviado ao GitHub.

## Validação

Execute `validar_windows.bat`.

A suíte atual valida:

- matrizes, equivalências e transições;
- consolidação do histórico;
- cálculo individual de formatura;
- sobreposição de obrigatórias;
- cobertura conjunta de opção limitada e livre;
- estratégias simultânea, híbrida e sequencial;
- roteiro e marcos de diploma;
- geração do relatório completo;
- busca de grades, conflitos, docentes e editor.

## Privacidade e limites

O processamento é local. Não compartilhe:

- `entradas/`;
- arquivos locais com comentários integrais.

A coleta autenticada do UFABC Next não faz parte do produto. Avaliações docentes só podem ser importadas quando houver uma fonte autorizada e dados agregados adequados para uso público.

As datas são estimativas de apoio à decisão. Confirme integralização, transições, extensão, estágio, trabalho final e situações excepcionais com o SIGAA e as coordenações.
