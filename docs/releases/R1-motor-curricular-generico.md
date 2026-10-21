# R1 — Motor curricular genérico

**Estado:** ativa
**Tracker:** #40
**Objetivo:** fazer regras curriculares declarativas governarem a integralização no escopo dos pilotos, sem antecipar cobertura pública.

## Meta da release

> O motor genérico deve produzir resultados explicáveis e revisados para famílias curriculares distintas antes de substituir qualquer decisão do caminho legado.

## Ponto de partida

A R0 entregou o contrato de integração, o teste diferencial, a seleção de pilotos e o BC&T 2015 em modo sombra. O caminho legado continua como autoridade. A entrada pública permanece bloqueada pelo gate de cobertura.

## Backlog inicial

| Ordem | Incremento | Evidência esperada |
| ---: | --- | --- |
| 1 | Estruturar a proveniência das regras usadas pelo piloto BC&T 2015 | cada requisito comparado aponta para fonte, versão, matriz e estado de revisão |
| 2 | Montar casos acadêmicos revisáveis para o BC&T 2015 | fixtures sintéticas cobrem cumprimento, pendência, equivalência, dado ausente e divergência |
| 3 | Classificar e resolver divergências legado × genérico do BC&T 2015 | cada divergência tem causa, decisão e regressão |
| 4 | Integrar o BCD 2023 como segunda família em modo sombra | o mesmo contrato executa sem lógica acadêmica na interface e sem liberar suporte |
| 5 | Exercitar uma família com grupos ou requisitos diferentes dos bacharelados interdisciplinares | o modelo representa a diferença sem regra específica por curso no avaliador |
| 6 | Definir o corte de autoridade por piloto | promoção exige fonte, revisão humana, casos adversariais e equivalência diferencial |
| 7 | Migrar o menor consumidor elegível do legado para o resultado genérico | comportamento anterior permanece coberto e o rollback é explícito |

Riscos de correção acadêmica, segurança ou privacidade podem interromper essa ordem.

## Critérios de saída

A R1 termina quando:

- [ ] pelo menos duas famílias curriculares estruturalmente distintas executam pelo contrato genérico no fluxo real;
- [ ] regras críticas dos pilotos possuem fonte, versão, matriz e estado de revisão rastreáveis;
- [ ] casos revisados cobrem caminhos válidos, inválidos, limites, dados ausentes e equivalências relevantes;
- [ ] divergências legado × genérico estão explicadas e protegidas por regressão;
- [ ] nenhum consumidor promovido transforma resultado indeterminado em certeza;
- [ ] a autoridade do motor genérico está limitada a escopos explicitamente aprovados;
- [ ] testes relacionados e suíte de regressão apropriada estão verdes;
- [ ] limitações restantes estão registradas e não autorizam publicação universal.

## Fora de escopo

- validar em massa as 93 matrizes inventariadas;
- liberar a entrada pública;
- substituir o solver atual;
- migrar a interface final para outra tecnologia;
- persistir histórico acadêmico bruto;
- inferir equivalências, transições ou aplicabilidade sem fonte oficial.

## Primeiro incremento

Estruturar a proveniência das regras do BC&T 2015 usadas pelo modo sombra. O incremento deve reutilizar o contrato existente, manter o legado como autoridade e falhar fechado quando a fonte ou o estado de revisão forem insuficientes.

## Preparação da migração do primeiro consumidor

O corte de autoridade está definido em `planejador/autoridade_curricular.py`.
O modo sombra dos pilotos BC&T 2015 e BCD 2023 expõe `corte_autoridade`, com
identificador do piloto, autoridade elegível e bloqueios. O runner interno
`scripts/comparar_bct_sombra.py` inclui esse diagnóstico no JSON.

O diagnóstico usa a proveniência estruturada revisada e a aplicabilidade do caso.
Os outros sete critérios permanecem bloqueados por falta de evidência de aprovação
registrada para o escopo. Marcar uma fonte como revisada não aprova a revisão
acadêmica integral do piloto. Concordância em um histórico isolado não aprova a
equivalência diferencial. O diagnóstico não altera a autoridade efetiva do modo
sombra nem libera publicação.

Antes de executar o item 7, registrar as evidências dos critérios restantes para
um escopo explícito e identificar o consumidor cuja migração elas autorizam.

## Próxima release

Após os critérios de saída, a candidata é **R2 — Cobertura acadêmica**. A promoção exige nova auditoria e atualização do roadmap.
