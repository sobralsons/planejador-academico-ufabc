# Estado acadêmico atual

**Última consolidação documental:** 25/09/2026  
**Estado de publicação:** bloqueado

Este arquivo é a referência de leitura rápida para o estado acadêmico atual do projeto. Os dados estruturados continuam sendo a fonte de verdade; este documento não substitui os JSONs, testes nem a revisão humana.

## O que está comprovado hoje

- `dados/inventario_cursos.json` contém **35 cursos** e **93 PPCs** inventariados.
- No inventário usado pela trava de publicação, as **93 matrizes** continuam com aplicabilidade `a_confirmar`.
- Nesse mesmo inventário, modelagem, testes acadêmicos e revisão humana ainda não foram aprovados para nenhuma matriz.
- `dados/vigencia_ppcs_2026-09-16.json` contém uma **avaliação preliminar**, datada de 16/09/2026, com **57 matrizes candidatas** e **36 pendentes**.
- “Candidata” significa hipótese de trabalho para investigação; **não significa vigência definitivamente comprovada nem suporte acadêmico do produto**.
- `dados/registro_curriculos.json` contém **7 pacotes curriculares legados estruturados** no motor atual. Eles servem a desenvolvimento, regressão e comparação, mas não constituem certificação de integralização oficial.
- A trava em `planejador/cobertura.py` permanece fail-closed: enquanto levantamento, aplicabilidade, modelagem, testes e revisão humana não estiverem concluídos, a liberação pública não é permitida.

## O que não pode ser afirmado

No estado atual, o projeto não deve declarar que:

- suporta qualquer estudante da UFABC;
- suporta todos os cursos ou todas as matrizes;
- alguma das 93 matrizes está academicamente validada para uso público;
- os 7 currículos legados representam cobertura acadêmica suficiente;
- uma estimativa de trajetória ou formatura é garantia;
- testes estruturais antigos substituem revisão acadêmica humana;
- uma classificação preliminar de vigência é decisão definitiva.

## Como interpretar documentos antigos

Arquivos como `RELATORIO_DE_VALIDACAO.md`, `VALIDACAO_MULTICURSO.md`, `VALIDACAO_TRAJETORIAS.md` e `MELHORIAS_IMPLEMENTADAS.md` registram etapas históricas do protótipo.

Nesses arquivos, expressões como “validado”, “validação acadêmica”, “versão validada” e contagens antigas de testes devem ser lidas apenas no escopo técnico/estrutural descrito naquela época. Elas **não representam o critério atual de suporte público**.

Em caso de divergência:

1. prevalecem os dados estruturados atuais;
2. prevalece a trava de publicação;
3. prevalecem fontes oficiais e revisão humana;
4. documentos históricos ficam apenas como rastreabilidade.

## UFABC Next e dados autenticados

Descrições antigas de coleta autenticada automática do UFABC Next são históricas e não autorizam reativação desse fluxo.

O estado atual não disponibiliza coleta autenticada automática. Qualquer integração futura desse tipo exige fonte autorizada, revisão específica de segurança/privacidade e não pode introduzir credenciais, sessão ou dados pessoais no repositório.

## Critério para mudar este documento

Só atualizar uma contagem ou declarar uma matriz suportada quando o artefato correspondente também tiver sido atualizado e o estado estiver protegido por testes. Revisão documental isolada não promove matriz, não cria equivalência e não altera regra acadêmica.
