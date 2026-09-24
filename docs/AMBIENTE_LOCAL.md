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
git checkout develop
```

`develop` é a base estável de desenvolvimento. Ela contém o checkpoint integrado e validado da pilha atual, mas não é uma versão pública nem substitui a trava de cobertura acadêmica da `main`.

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
2. git checkout develop
3. git pull
4. git checkout -b tipo/nome-da-tarefa
5. alterar poucos arquivos
6. validar_windows.bat
7. revisar git diff
8. commit
9. push
10. PR para develop
```

Não trabalhar diretamente na `main` nem na `develop`. Para uma tarefa nova, atualize `develop`, crie uma branch curta a partir dela e abra PR de volta para `develop`. A `main` permanece reservada para integração/release autorizada.

## Próximas etapas de infraestrutura

A ordem planejada depois deste checkpoint é:

1. definir migration PostgreSQL/Supabase para rascunhos persistíveis;
2. implementar e testar RLS com usuários sintéticos;
3. conectar autenticação de desenvolvimento;
4. somente depois expor endpoints autenticados de persistência;
5. iniciar o frontend Next.js/PWA sobre contratos já testados;
6. manter histórico SIGAA temporário por padrão.

Banco, autenticação e frontend não devem ser introduzidos todos na mesma alteração.
