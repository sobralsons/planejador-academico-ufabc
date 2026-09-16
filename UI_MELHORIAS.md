# Melhorias de interface — versão 2026.09

Esta versão mantém a lógica acadêmica do planejador e moderniza a camada de apresentação.

## Componentes adicionados

- **streamlit-shadcn-ui**: cards de métricas com aparência consistente de produto.
- **streamlit-aggrid**: tabelas exploráveis com ordenação, filtros e redimensionamento de colunas.
- **streamlit-sortables**: drag-and-drop para ordenar as formações adicionais quando houver três formações no plano.

## Compatibilidade

Os três componentes possuem fallback para recursos nativos do Streamlit. Assim, uma falha de carregamento da camada visual não altera a lógica de cálculo do planejador.

## Alterações visuais

- cabeçalho mais compacto e com identidade visual consistente;
- tabs estilizadas como etapas de um fluxo;
- sidebar, inputs, botões, métricas e expanders harmonizados;
- tabelas de cenários, avaliações docentes e ajuste de matrícula com filtros;
- cards de contexto na trajetória;
- destaque visual do modo de ajuste de matrícula.

## Observação

A versão 1.x do `streamlit-shadcn-ui` exige Python 3.10+ e Streamlit 1.60+.
