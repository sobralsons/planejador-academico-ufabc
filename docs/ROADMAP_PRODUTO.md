# Roadmap de Produto — Planejador Acadêmico UFABC

> **Fonte de verdade do planejamento macro.** Regras acadêmicas continuam sendo determinadas somente por fontes oficiais e revisão apropriada.

## Visão

Construir uma plataforma que ajude qualquer estudante de graduação da UFABC a entender sua situação acadêmica e tomar decisões de matrícula e trajetória com segurança, usando regras e dados oficiais e explicando fontes, incertezas e alternativas de cada resultado.

O produto não é apenas um gerador de grades. A pergunta central é:

> **Dado onde estou na graduação, o que posso fazer agora e quais consequências cada escolha pode ter?**

## Princípio de desenvolvimento

Toda execução deve manter rastreabilidade entre produto e código:

```text
VISÃO
  ↓
META DA RELEASE
  ↓
MAIOR RISCO / NECESSIDADE
  ↓
MENOR INCREMENTO SEGURO
  ↓
TESTE
  ↓
FEEDBACK
  ↓
REPRIORIZAÇÃO
```

Trabalho técnico sem relação clara com a meta da release não entra automaticamente no backlog corrente. Riscos de correção acadêmica, confiabilidade ou segurança têm precedência sobre o planejamento normal.

## Release ativa

**R0 — Fundação confiável**

Plano operacional: [releases/R0-fundacao-confiavel.md](releases/R0-fundacao-confiavel.md)

## Estratégia de releases

| Release | Meta de produto | Entrega principal | Critério de saída macro | Estado |
| --- | --- | --- | --- | --- |
| **R0 — Fundação confiável** | Eliminar bloqueadores conhecidos que podem transformar incerteza em certeza incorreta ou impedir evolução segura | Entradas acadêmicas fail-closed, evidências confiáveis, documentação coerente e contrato de migração para o modelo genérico | Todos os critérios de R0 aprovados | **ativa** |
| **R1 — Motor curricular genérico** | Fazer as regras declarativas governarem a integralização sem lógica específica por curso | Modelo genérico integrado ao fluxo real e validado em famílias curriculares distintas | Pilotos representativos produzem resultados revisados e testes diferenciais passam | planejada |
| **R2 — Cobertura acadêmica** | Determinar corretamente qual regra pode reger qualquer estudante ativo | Aplicabilidade resolvida, matrizes aplicáveis modeladas, testadas e revisadas | Cobertura exigida para publicação atinge o gate acadêmico | planejada |
| **R3 — Validação fechada** | Provar que estudantes reais conseguem usar o fluxo principal sem assistência do desenvolvedor | Progresso, matrícula, ajuste e trajetória em teste controlado | Casos acadêmicos e tarefas de UX atendem critérios definidos | planejada |
| **R4 — Produto público 1.0** | Disponibilizar o planejador com segurança para qualquer estudante no escopo validado | Web/PWA responsiva, API estável, autenticação e planejamento salvo | Gates acadêmico, segurança, privacidade, UX e operação aprovados | planejada |
| **R5 — Evolução** | Melhorar escala e inteligência sem perder explicabilidade | Automação de dados, otimização comparada e recursos avançados | Melhorias comprovadas por métricas e testes diferenciais | planejada |

## Gates permanentes

Uma funcionalidade não está pronta apenas porque funciona no caminho feliz.

### Correção acadêmica

- regra importante possui fonte e versão quando aplicável;
- ausência ou ambiguidade pode produzir estado indeterminado;
- equivalências, transições, compartilhamentos e limites não são inferidos sem evidência;
- alterações de regra têm casos válidos, inválidos, limites e regressão.

### Transparência

- resultado importante pode explicar de onde veio;
- heurística, estimativa e preferência do usuário não são apresentadas como regra oficial;
- busca parcial, truncamento ou informação incompleta aparecem explicitamente.

### Segurança e privacidade

- dados pessoais são minimizados;
- histórico bruto não é persistido por padrão;
- isolamento multiusuário é adversarialmente testado;
- credencial privilegiada não é usada onde o contexto do próprio usuário e RLS são suficientes.

### Publicação

A entrada pública permanece fail-closed. O roadmap não pode substituir o gate calculado pelo núcleo de cobertura nem a revisão humana exigida para matrizes.

## Métricas de produto

Contagem de testes e PRs é evidência de engenharia, não a meta final.

| Dimensão | Métrica desejada |
| --- | --- |
| Cobertura | todas as matrizes relevantes com aplicabilidade resolvida |
| Revisão | todas as matrizes publicáveis com revisão humana concluída |
| Proveniência | regras críticas com fonte/versionamento rastreáveis |
| Correção | nenhum erro crítico conhecido sem tratamento explícito |
| Incerteza | dado ausente ou ilegível nunca vira certeza silenciosamente |
| Segurança | nenhum acesso cruzado entre usuários nos cenários adversariais |
| Privacidade | nenhum histórico bruto persistido por padrão |
| Usabilidade | tarefas principais concluídas por estudantes sem ajuda indevida |
| Transparência | usuário consegue entender motivo, fonte e limites do resultado |
| Manutenção | adicionar ou revisar matriz não exige duplicar regra em interface |

## Ordem macro de arquitetura

A arquitetura-alvo continua:

```text
Web/PWA
   ↓
FastAPI
   ↓
núcleo acadêmico Python
   ↓
PostgreSQL / Supabase
```

Isso não define a ordem imediata de implementação. A interface pública final só deve avançar quando o contrato acadêmico estiver estável o suficiente para evitar codificar regras transitórias na UI.

Da mesma forma, OR-Tools/CP-SAT só entra após existir benchmark do solver atual e validação diferencial de validade, objetivos, conflitos, quinzenais, preferências e restrições.

## Como planejar uma sprint

Uma sprint deve terminar em um incremento verificável ligado à meta da release.

Evitar metas de atividade como:

- “trabalhar no parser”;
- “mexer no modelo curricular”;
- “melhorar a interface”.

Preferir metas verificáveis como:

- “nenhum campo quantitativo ilegível do histórico chega ao motor como zero conhecido”;
- “uma matriz representativa é integralmente avaliada pelo modelo genérico e coincide com casos revisados”;
- “um estudante consegue ajustar sua matrícula em teste fechado sem ajuda do desenvolvedor”.

## Mudança de release

Para encerrar uma release:

1. revisar todos os critérios de saída;
2. registrar evidências e limitações;
3. confirmar que débitos remanescentes não violam prioridades superiores;
4. atualizar este arquivo para apontar a próxima release ativa;
5. revisar o backlog à luz do feedback obtido.

Não promover uma release apenas porque “já fizemos bastante”.
