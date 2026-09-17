# Contrato dos lotes de auditoria de aplicabilidade

Estes arquivos registram análise documental preliminar. Não são regras executáveis
de integralização nem certificam suporte acadêmico. O inventário operacional e
a avaliação de vigência continuam separados; revisão humana permanece obrigatória.

## Versões reconhecidas

| Campo | Versão 1 (lotes 1–7) | Versão 2 (lotes 8–11) |
| --- | --- | --- |
| Data da análise | `analisado_em` | `avaliado_em` |
| Decisões | `matrizes` | `auditoria` |
| Catálogo de fontes | `fontes_oficiais` | `fontes` |
| Resultado por matriz | `status_resultante` | `resultado` |
| PPCs, entrada em vigor, integralização e cálculo temporal | objetos | textos |
| Transição e exceções | listas | textos |
| Decisão publicável | campo da matriz | campo em `revisao_humana` |

Ambas identificam curso, ano da matriz e fontes por ID. IDs usados nas decisões
devem existir no catálogo do mesmo lote. Os testes comuns verificam versão,
tipos, referências, domínio oficial das URLs e o caráter preliminar dos registros.
Eles não leem documentos remotos nem comprovam a interpretação das fontes.

A versão 2 formaliza o formato textual já adotado a partir do lote 8; não adiciona
capacidade ao motor curricular. Consumidores devem selecionar explicitamente a
versão. Uma mudança incompatível requer nova versão e testes, sem inferir o
formato pelo número do lote. Novos lotes devem usar a versão 2 ou documentar
uma evolução explícita. Não é necessário reescrever lotes antigos.

## História e retificações

O resultado de um lote é histórico, não necessariamente o estado global atual.
Promoções posteriores devem indicar a matriz, fontes e sincronização no arquivo
de vigência e no mapa de famílias. Matemática 2017 permanece pendente no estado
global até uma sincronização específica; esta correção não a promove.

Erros factuais exigem retificação identificável, mesmo em registros históricos.
No lote 8, `retificacao_documental` registra data, afirmação anterior incorreta,
correção e fontes. A minuta de Biotecnologia de maio de 2023 contém um prazo
que não consta do documento final aprovado pelo Ato CG nº 34/2023. O prazo da
minuta não deve ser apresentado como norma aprovada. A candidatura posterior
do lote 9, apoiada no documento de 2025, não foi revertida.

Minutas podem ser preservadas como contexto, identificadas como tal, mas não
substituem o ato ou documento final. Ausência de prazo não prova vigência
irrestrita; listagem de fonte oficial e testes passando não substituem revisão
acadêmico-normativa humana.
