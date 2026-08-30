# Integração com o UFABC Next

## Fluxo automático

1. Abra o planejador com `executar_windows.bat`.
2. Envie o histórico e a planilha de ofertas.
3. Abra a aba **5. Avaliações UFABC Next**.
4. Clique em **Atualizar avaliações dos docentes das ofertas**.
5. Faça login institucional na janela do Edge.
6. Deixe a página Reviews aberta e aguarde.
7. O arquivo `dados/avaliacoes_docentes.json` será atualizado.
8. Gere o planejamento normalmente.

## Como a avaliação afeta a grade

O sistema associa cada oferta pelo par:

```text
nome normalizado do professor + código-base da disciplina
```

Exemplo:

```text
DOCENTE EXEMPLO + DISC001
```

A avaliação geral do professor é sempre usada como base. Quando existe avaliação específica da disciplina, o sistema combina as duas fontes com peso de 60% para a avaliação geral e 40% para a disciplina específica. Se a opção de combinação estiver desativada, somente a avaliação geral é usada.

O efeito é reduzido quando a amostra é pequena e multiplicado pela importância escolhida na interface.

## Segurança

- a senha não é lida pelo planejador;
- o token fica apenas na memória durante a coleta;
- a sessão local fica em `dados/sessao_ufabc_next/`;
- comentários completos ficam somente no arquivo local identificado como `NAO_COMPARTILHAR`;
- o relatório principal utiliza apenas métricas agregadas.

## Arquivos

- `dados/avaliacoes_docentes.json`: dados agregados usados pelo planejador;
- `dados/consultas_ufabc_next.csv`: pares professor–disciplina a consultar;
- `saidas/relatorio_avaliacoes_docentes.html`: relatório visual específico;
- `saidas/avaliacoes_docentes_local_com_comentarios_NAO_COMPARTILHAR.json`: comentários completos, uso local;
- `dados/sessao_ufabc_next/`: sessão autenticada, nunca compartilhar.

> A versão pública distribui `avaliacoes_docentes.json` vazio e mantém a integração desabilitada por padrão.
