# Portfolio Audit — UFABC Academic Planner

Auditoria realizada em agosto de 2026 com foco em transformar o repositório em um projeto público mais forte para portfólio técnico.

## Estado encontrado

Na branch `main`, o repositório público contém atualmente:

- `README.md`;
- `.gitignore`;
- `requirements.txt`.

O README anterior descrevia uma estrutura completa de código (`app.py`, `main.py`, pacote `planejador/`, testes e assets), mas esses arquivos ainda não estavam presentes no repositório público. Também havia referências a imagens em `assets/` que não existiam na branch pública.

## Pontos positivos

O projeto já tem um problema real e tecnicamente interessante, interface desenvolvida, múltiplos critérios de planejamento, análise de trajetória, validação de busca e preocupação com testes e privacidade.

O `.gitignore` também já cobre entradas do usuário, sessão autenticada, secrets, ambientes virtuais, caches e resultados locais sensíveis.

## Principais riscos antes de publicar o código

1. Histórico acadêmico real ou arquivos enviados pelo usuário.
2. Sessões autenticadas e tokens do UFABC Next.
3. Comentários completos ou outros dados pessoais coletados localmente.
4. Credenciais em arquivos `.env`, `secrets.toml` ou configurações locais.
5. Arquivos sensíveis que tenham sido commitados anteriormente: `.gitignore` não limpa o histórico Git.
6. Dependências públicas divergentes das importações reais do projeto.
7. README afirmando que arquivos ou funcionalidades estão reproduzíveis quando ainda não estão presentes na versão pública.

## Checklist recomendado para a publicação do código

- [ ] Copiar o código para uma pasta limpa, sem arquivos de entrada reais.
- [ ] Rodar busca por tokens, senhas, e-mails, nomes e caminhos locais.
- [ ] Substituir históricos e ofertas reais por dados fictícios de demonstração.
- [ ] Verificar o histórico Git antes de tornar qualquer dado sensível público.
- [ ] Revisar `requirements.txt` a partir das importações reais.
- [ ] Confirmar que a aplicação inicia em um ambiente virtual novo.
- [ ] Rodar toda a suíte de testes.
- [ ] Garantir que testes não dependam de dados pessoais.
- [ ] Publicar screenshots anonimizados.
- [ ] Adicionar instruções reproduzíveis de execução.

## Evolução sugerida do projeto

### v1 — Publicação segura

Código atual + dados fictícios + testes reproduzíveis + documentação.

### v2 — Refatoração Python

Separar de forma mais explícita interface, domínio/regras acadêmicas, processamento de dados e geração de relatórios.

### v3 — Persistência

Introduzir banco relacional, começando por SQLite ou PostgreSQL conforme a necessidade do projeto.

### v4 — API

Criar uma camada de API com FastAPI para desacoplar a interface das regras de negócio.

### v5 — Engenharia de software

Adicionar testes de integração, lint/type checking, CI com GitHub Actions e containerização com Docker.

### v6 — Produto demonstrável

Deploy de demonstração, dados fictícios prontos para uso e documentação de arquitetura.

## Objetivo de posicionamento

O repositório deve demonstrar principalmente capacidade em:

- Python;
- tratamento e modelagem de dados;
- construção de regras de negócio;
- otimização e busca combinatória;
- desenvolvimento de aplicações;
- testes e validação;
- organização de software;
- resolução de um problema real.

Tecnologias futuras, como FastAPI, PostgreSQL e Docker, devem aparecer como parte da evolução somente quando estiverem de fato implementadas.