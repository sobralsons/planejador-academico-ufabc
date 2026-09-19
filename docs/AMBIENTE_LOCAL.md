# Ambiente de desenvolvimento local

Este é o fluxo recomendado para desenvolver o Planejador Acadêmico UFABC no PC. O GitHub continua sendo a fonte de verdade do código; arquivos pessoais, documentos-fonte locais e segredos ficam fora do Git.

## Pré-requisitos no Windows

Instale:

- Git;
- Python 3.12;
- Visual Studio Code;
- extensão Python da Microsoft no VS Code.

Não é necessário instalar PostgreSQL, Supabase CLI, Node.js ou Docker nesta etapa.

## Primeira configuração

Abra o PowerShell ou o terminal do VS Code e escolha uma pasta de projetos. Clone o repositório:

```powershell
git clone https://github.com/sobralsons/planejador-academico-ufabc.git
cd planejador-academico-ufabc
git checkout product/local-development-checkpoint
```

Enquanto a pilha atual de PRs ainda estiver em revisão, essa branch representa o checkpoint de desenvolvimento mais recente. Ela não é uma versão pública.

Depois, execute:

```text
preparar_ambiente_windows.bat
```

O script:

1. cria `.venv`;
2. instala `requirements-local.txt`;
3. cria `.env.local` a partir de `.env.example`, caso ainda não exista;
4. valida Python, Git, dependências e proteções do `.gitignore`.

Abra a pasta no VS Code:

```powershell
code .
```

Se o comando `code` não estiver disponível, use **File > Open Folder** no VS Code.

## Arquivos locais que nunca devem ir para o GitHub

- `.env.local`;
- conteúdo de `documentos-fonte/`, exceto o README;
- históricos reais em `entradas/`;
- credenciais, tokens e sessões;
- saídas privadas identificáveis.

Antes de qualquer commit, confira:

```powershell
git status
```

Nunca use `git add .` sem revisar o que será adicionado.

## Validar o projeto

Execute:

```text
validar_windows.bat
```

A validação local deve compilar o núcleo, API, persistência e scripts, e executar a suíte completa de testes.

Pelo terminal, o equivalente é:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app.py app_interno.py main.py planejador ferramentas api persistencia scripts
.\.venv\Scripts\python.exe -m pytest -q
```

## Rodar os componentes atuais

### API FastAPI

Execute:

```text
executar_api_windows.bat
```

Ela inicia somente em `127.0.0.1:8000`. A API atual é de desenvolvimento, trabalha com cenários sintéticos e não deve ser exposta à internet.

### Protótipo Streamlit interno

Execute:

```text
executar_windows.bat
```

O Streamlit continua sendo ferramenta interna de desenvolvimento/validação. `app.py` permanece como entrada pública fail-closed.

## Documentos oficiais

Use `documentos-fonte/` como acervo local. O conteúdo não é versionado no Git. A estrutura sugerida e as regras estão em `documentos-fonte/README.md`.

No futuro, quando o armazenamento remoto de fontes for criado, o repositório continuará guardando metadados e rastreabilidade; PDFs não serão colocados diretamente no PostgreSQL.

## Variáveis de ambiente

`.env.example` contém apenas nomes de variáveis e valores inofensivos. `.env.local` é a cópia privada do seu PC.

Os campos de Supabase/PostgreSQL ficam vazios até a etapa do banco. Nunca copie uma service role key para código frontend, documentação, commit ou mensagem de erro.

## Fluxo diário recomendado

```text
1. git status
2. git pull
3. criar/usar branch da tarefa
4. alterar poucos arquivos
5. validar_windows.bat
6. revisar git diff
7. commit
8. push
9. PR
```

Não trabalhar diretamente na `main`. Durante o desenvolvimento atual, também não usar a `main` como referência funcional mais recente sem verificar a pilha de PRs.

## Próximas etapas de infraestrutura

A ordem planejada depois deste checkpoint é:

1. consolidar a base de desenvolvimento local;
2. definir migration PostgreSQL/Supabase para rascunhos persistíveis;
3. implementar e testar RLS com usuários sintéticos;
4. conectar autenticação de desenvolvimento;
5. somente depois expor endpoints autenticados de persistência;
6. iniciar o frontend Next.js/PWA sobre contratos já testados;
7. manter histórico SIGAA temporário por padrão.

Banco, autenticação e frontend não devem ser introduzidos todos na mesma alteração.
