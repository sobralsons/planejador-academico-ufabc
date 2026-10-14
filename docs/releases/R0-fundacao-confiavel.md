# R0 — Fundação confiável

**Estado:** concluída em 2026-10-14
**Tracker:** #27  
**Primeira história:** #28 — campos quantitativos inválidos do histórico  
**Objetivo:** eliminar bloqueadores conhecidos para que o núcleo atual seja uma base confiável para a modelagem curricular universal.

Esta release não busca ampliar funcionalidades. Ela reduz risco antes da migração do motor acadêmico para o modelo curricular genérico.

## Meta da release

> **Informação acadêmica ausente, inválida ou incompleta não pode virar certeza silenciosamente, e o próximo motor precisa ter um contrato seguro de integração com o legado.**

## Por que esta release existe

O projeto já possui inventário amplo, modelo genérico de requisitos, solver, trajetórias, API e fundações de persistência. Porém, ainda há riscos de prioridade superior:

- o parser de histórico possui conversão quantitativa que pode transformar valor ausente ou inválido em `0`;
- evidências derivadas precisam continuar falhando fechado quando a prova é incompleta;
- documentos históricos podem sugerir um grau de validação diferente do critério atual;
- o modelo curricular genérico ainda não governa sozinho integralização, planejamento e solver.

Antes de ampliar cobertura ou construir a interface pública final, esses riscos devem ser tratados.

## Backlog ordenado da R0

| Ordem | Incremento | Necessidade/risco | Evidência esperada |
| ---: | --- | --- | --- |
| 1 | Concluir revisão da fundação de persistência autenticada | Evitar que uma fundação técnica pendente fique implícita | PR separado revisado, CI e E2E documentados antes de integração |
| 2 | Endurecer campos quantitativos do histórico (#28) | Impedir que desconhecido/inválido seja interpretado como zero conhecido | parser rejeita ou representa ausência explicitamente; regressões específicas |
| 3 | Auditar consumidores de derivações incompletas | Impedir conclusão acadêmica baseada em prova truncada | casos adversariais falham fechado até a fronteira de uso |
| 4 | Harmonizar documentação de estado atual | Evitar que relatórios históricos sejam lidos como certificação vigente | documentos antigos identificados como históricos e fonte atual explícita |
| 5 | Definir contrato de integração do modelo curricular genérico | Evitar duas fontes de verdade acadêmica sem fronteira definida | ADR/contrato pequeno com entradas, saídas, estados indeterminados e proveniência |
| 6 | Criar teste diferencial legado × genérico | Permitir migração sem confiar apenas em testes isolados | fixtures representativas com divergências explicadas |
| 7 | Selecionar pilotos de famílias distintas | Provar generalidade antes de cadastrar matrizes em massa | conjunto mínimo cobre regras estruturalmente diferentes |
| 8 | Integrar a primeira família ao fluxo real | Produzir primeiro incremento da R1 sem reescrita ampla | uma família usa o modelo genérico em caminho real com regressão |

A ordem pode mudar apenas quando surgir risco de prioridade superior ou uma dependência técnica comprovada.

## Critérios de saída

A R0 só termina quando:

- [x] campo quantitativo inválido/ausente do histórico não é convertido silenciosamente em zero conhecido;
- [x] derivações incompletas não podem sustentar conclusão em consumidor relevante sem sinalização fail-closed;
- [x] documentação vigente não contradiz o estado real de cobertura e validação;
- [x] contrato de integração do modelo curricular genérico está documentado;
- [x] existe pelo menos um teste diferencial entre caminho legado e genérico;
- [x] pilotos de famílias curriculares distintas estão definidos por risco/capacidade, não por conveniência;
- [x] testes relacionados e suíte de regressão apropriada estão verdes;
- [x] limitações remanescentes estão registradas e não representam risco crítico conhecido para iniciar a R1.

## Fora de escopo

Não pertencem à R0, salvo se necessários para corrigir risco superior:

- migração da UI pública para Next.js;
- app nativo;
- substituição do solver por OR-Tools/CP-SAT;
- cadastro em massa de matrizes copiando regras;
- persistência de histórico acadêmico bruto;
- coleta autenticada do UFABC Next;
- liberação pública.

## Protocolo para cada incremento

Antes de implementar, registrar na issue ou PR:

**PROBLEMA → CAUSA → IMPACTO → SOLUÇÃO MÍNIMA → TESTE → REGRESSÃO → PRÓXIMO PASSO**

Perguntas obrigatórias:

1. qual critério de saída da R0 isto aproxima?
2. qual erro ou incerteza será impossível depois da mudança?
3. qual teste demonstra isso?
4. o incremento introduz regra acadêmica nova? Se sim, qual fonte oficial a sustenta?

## Definição de pronto de um item

Um item da R0 está pronto quando:

- comportamento novo ou corrigido é explícito;
- teste específico protege o caso;
- suíte relacionada passa;
- impacto acadêmico e limitações são relatados;
- documentação é atualizada somente quando o contrato mudou;
- não foi introduzida regra de curso na interface.

## Registro de evidências

Atualizar esta seção apenas após validações reais.

| Data | Item | Evidência | Estado |
| --- | --- | --- | --- |
| 2026-09-25 | Estrutura de planejamento de produto | PR #29: roadmap, regras de governança e release R0 | concluído |
| 2026-09-25 | Fundação de persistência autenticada | PR #26: integração local, testes de autorização e documentação de E2E | concluído |
| 2026-09-25 | Quantidades inválidas do histórico | PR #30: parser fail-closed e regressões | concluído |
| 2026-09-25 | Derivações incompletas | PR #31: consumidores legados bloqueiam conclusão sem prova completa | concluído |
| 2026-09-25 | Estado acadêmico documentado | PR #32 e `docs/ESTADO_ACADEMICO_ATUAL.md` | concluído |
| 2026-09-25 | Contrato do motor genérico | PR #33 e `docs/CONTRATO_INTEGRACAO_MOTOR_CURRICULAR.md` | concluído |
| 2026-09-25 | Teste diferencial | PR #34: casos concordantes e divergências explicadas | concluído |
| 2026-09-26 | Pilotos por risco e capacidade | PR #35 e `dados/pilotos_integracao_r0.json` | concluído |
| 2026-10-14 | Primeira família no fluxo real | PR #36: BC&T 2015 em modo sombra, legado como autoridade | concluído |
| 2026-10-14 | Correções acadêmicas impeditivas | PRs #37 e #38: TCC BCC 2023 e créditos de Pesquisa Operacional no BCD 2023 | concluído |
| 2026-10-14 | Regressão final | Python 3.12: compileall aprovado; 515 testes locais passaram; CI dos PRs #36, #37 e #38 passou | concluído |

## Limitações transferidas para a R1

- O motor genérico ainda não é autoridade no fluxo público.
- O BC&T 2015 opera somente em modo sombra e exige confirmações explícitas.
- As fontes legadas ainda não fornecem proveniência estruturada suficiente para promover o piloto.
- Nenhuma das 93 matrizes inventariadas possui revisão humana integral ou suporte público aprovado.
- A entrada pública continua bloqueada pelo gate de cobertura.

Essas limitações não reabrem os riscos tratados pela R0. A R1 deve reduzi-las sem liberar matriz, curso ou resultado antes dos gates acadêmicos.

## Próxima release

A release seguinte é **R1 — Motor curricular genérico**. O plano operacional está em [R1-motor-curricular-generico.md](R1-motor-curricular-generico.md).
