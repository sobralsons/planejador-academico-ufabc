# Contrato de integração do motor curricular genérico

**Estado:** contrato da R0 — ainda não ativa o motor genérico no fluxo público  
**Escopo:** fronteira entre histórico/regras acadêmicas e consumidores de integralização, planejamento e trajetória

Este documento define como o modelo curricular genérico pode entrar no fluxo real sem criar duas fontes de verdade, transformar ausência em certeza ou perder proveniência. Ele descreve contratos já existentes no núcleo e as condições obrigatórias para uma futura integração.

## 1. Princípio de autoridade

Enquanto uma matriz/piloto não tiver migração explicitamente validada, o caminho legado continua sendo o comportamento do produto para aquele escopo.

O motor genérico pode ser executado em **modo sombra** para comparação, mas seu resultado não deve alterar integralização, solver, ranking, trajetória ou interface.

Quando um escopo for migrado:

- a escolha de autoridade deve ser explícita;
- o mesmo fato acadêmico não pode ser decidido pelo legado e pelo genérico em paralelo com regra de desempate implícita;
- divergência entre os motores deve ser tratada como evidência de revisão, não resolvida escolhendo automaticamente o resultado mais favorável;
- um resultado genérico `indeterminado` ou bloqueado não pode cair silenciosamente para uma conclusão positiva do legado.

A primeira migração real só deve ocorrer depois do teste diferencial previsto na R0.

## 2. Entrada do modelo de regras

A unidade de regras é `ModeloRequisitosCurriculares` em `planejador/requisitos_curriculares.py`.

A integração deve informar explicitamente:

- `curso_id`;
- `matriz_id`;
- requisitos quantitativos e sua unidade;
- grupos, condicionais, sequências, contribuições e compartilhamentos quando aplicáveis;
- regras de aplicabilidade quando a matriz depender do vínculo/contexto;
- referências de curso-base quando existirem;
- fontes da regra por `FonteRegra` e/ou `fontes_gerais`.

### Proveniência das regras

`FonteRegra` é a forma estruturada de registrar título, URL oficial, referência e trecho curto para auditoria.

No caminho público, regra acadêmica relevante sem proveniência suficiente não deve ser promovida apenas porque o objeto Python aceita fontes vazias para testes sintéticos e desenvolvimento.

O adaptador de integração não pode inventar equivalências, categorias, tags ou aplicabilidade por nome/similaridade.

## 3. Entrada do histórico

O histórico entra inicialmente como `SituacaoAcademica`, produzido pela consolidação do parser.

A fronteira obrigatória para o motor genérico é:

`converter_historico_consolidado_em_evidencias(...)`

O resultado completo é `ResultadoConversaoHistorico`. O consumidor **não deve descartar** suas `pendencias` e `conflitos` e usar apenas `resultado.conjunto` como se a conversão fosse integralmente confiável.

O resultado contém:

- `ConjuntoEvidencias`;
- pendências de reconhecimento;
- conflitos quantitativos;
- unidades solicitadas como completas;
- unidades efetivamente completas após os bloqueios encontrados.

### Unidades completas

`ConjuntoEvidencias.unidades_completas` é uma afirmação positiva: significa que, para aquela dimensão, o conjunto de dados conhecido é suficiente para concluir também sobre ausência/pendência.

Nunca marcar uma unidade como completa apenas porque existem algumas evidências dessa unidade.

A conversão atual diferencia:

- `creditos`;
- `componentes`;
- `horas_carga_horaria`;
- `horas_extensao`.

A unidade genérica `horas` não deve ser preenchida automaticamente a partir do histórico.

## 4. Proveniência das evidências

A integração deve preservar os campos de `EvidenciaAcademica`:

- `id` estável;
- `codigos`;
- `origens`;
- `recursos_componentes`;
- `quantidades`;
- `observacoes`.

`recursos_componentes` existe para impedir dupla contagem de representações equivalentes da mesma conclusão.

Reconhecimento por equivalência não autoriza transferir automaticamente créditos ou cargas do componente de origem para o destino.

Metadados de categoria/tipo/tag devem vir de classificação validada para a matriz analisada; não devem ser inferidos do nome ou da categoria textual do SIGAA.

## 5. Alocação antes da avaliação

A avaliação curricular não consome diretamente uma lista de componentes; ela consome medições após alocação.

A fronteira é:

`avaliar_modelo_com_evidencias(modelo, conjunto, decisoes, ...)`

Antes da avaliação, `alocar_evidencias`:

- aloca automaticamente apenas destinos não ambíguos;
- registra `PendenciaAlocacao` quando uma evidência pode atender destinos concorrentes;
- exige `DecisaoAlocacao` explícita para resolver ambiguidade;
- só reutiliza a mesma quantidade em dois requisitos quando existe `RegraCompartilhamento` explícita;
- preserva a origem de cada `AlocacaoRealizada`;
- produz bloqueios quando uma restrição obrigatória não foi comprovada.

Se `ResultadoAlocacao.pronta_para_avaliacao` for falso, `AvaliacaoComEvidencias.avaliacao` é `None`. A camada de integração deve tratar isso como **bloqueado/indeterminado**, nunca como cumprido.

## 6. Estados acadêmicos

O avaliador usa `EstadoAplicabilidade` e `EstadoAvaliacao`.

### Aplicabilidade

- `aplicavel`: a matriz/regra pode ser avaliada no contexto fornecido;
- `nao_aplicavel`: não significa cumprida nem pendente;
- `indeterminada`: faltam dados para decidir se o modelo se aplica.

Aplicabilidade indeterminada bloqueia conclusão acadêmica positiva.

### Avaliação

- `cumprido`: existe evidência suficiente para provar o mínimo exigido;
- `pendente`: os dados relevantes estão completos e a quantidade comprovada está abaixo do mínimo;
- `indeterminado`: faltam dados/medição ou a quantidade conhecida abaixo do mínimo não permite provar pendência.

Regra central:

> **dados incompletos podem provar cumprimento quando a evidência conhecida, por si só, já satisfaz o mínimo; dados incompletos nunca podem provar pendência.**

Isso corresponde à semântica de `MedicaoRequisito.dados_completos` no avaliador atual.

## 7. Contexto que não pode ser inferido

Quando o modelo utilizar esses elementos, a integração deve fornecê-los explicitamente:

- atributos usados em aplicabilidade/condicionais;
- `sequencias_confirmadas`;
- `cursos_base_concluidos`;
- decisões de alocação acadêmica.

Ausência desses dados deve permanecer `None`/indeterminada conforme o contrato do avaliador. Não converter ausência em `False`, zero, pendência ou conclusão.

## 8. Saída mínima para consumidores

Um consumidor de integralização/planejamento só pode usar o resultado genérico se conseguir preservar, no mínimo:

- `curso_id` e `matriz_id`;
- estado de aplicabilidade;
- estado global da avaliação;
- resultados por regra com motivos e unidade;
- alocações realizadas;
- pendências de alocação;
- pendências/conflitos da conversão do histórico;
- proveniência das regras e evidências;
- indicação de unidades completas/incompletas.

Reduzir o resultado a um simples conjunto de “disciplinas cumpridas” perde informação necessária para fail-closed e não é um adaptador aceitável.

## 9. Mapeamento para o legado

Durante a migração, o adaptador deve respeitar estas regras:

| Resultado genérico | Uso permitido no legado |
| --- | --- |
| aplicabilidade `nao_aplicavel` | não avaliar a matriz nesse contexto |
| aplicabilidade `indeterminada` | bloquear conclusão; pedir/obter dado faltante |
| avaliação `cumprido` | pode alimentar conclusão somente dentro do escopo explicitamente migrado |
| avaliação `pendente` | pode alimentar pendência somente quando a completude necessária está comprovada |
| avaliação `indeterminado` | não converter em pendência nem cumprimento |
| avaliação `None` por bloqueio de alocação | tratar como bloqueado/indeterminado |
| divergência legado × genérico em modo sombra | registrar e revisar; não escolher automaticamente |

A migração não deve combinar créditos/resultados dos dois motores para “completar” um ao outro sem regra acadêmica explícita.

## 10. Critério de corte para um piloto

Um piloto só pode passar do modo sombra para autoridade real quando:

1. modelo da matriz/piloto possui fontes e versão identificáveis;
2. aplicabilidade do caso está resolvida;
3. conversão do histórico preserva pendências e conflitos;
4. unidades usadas para afirmar pendência têm completude comprovada;
5. ambiguidades de alocação têm tratamento explícito;
6. existe teste diferencial legado × genérico com casos concordantes e divergentes explicados;
7. casos adversariais de ausência, equivalência, dupla contagem e estado indeterminado estão cobertos;
8. revisão acadêmica humana necessária ao escopo foi registrada;
9. o consumidor não possui fallback silencioso para o legado em caso de indeterminação.

## 11. Fora deste contrato

Este documento não:

- declara nenhuma matriz validada;
- altera integralização, solver, ranking ou trajetória;
- define novas equivalências ou regras acadêmicas;
- autoriza cadastro em massa de cursos;
- autoriza publicação;
- substitui fontes oficiais ou revisão humana.

O próximo incremento da R0 deve ser um teste diferencial pequeno entre legado e genérico usando fixtures sintéticas/anonimizadas e divergências explicitamente classificadas.
