# Auditoria de publicação do portfólio

Revisão realizada antes da publicação do código-fonte no GitHub.

## Verificações concluídas

- suíte automatizada executada: **47 testes aprovados**;
- histórico acadêmico pessoal e planilhas de matrícula não incluídos;
- sessão autenticada do UFABC Next excluída;
- credenciais e arquivos `.env` protegidos pelo `.gitignore`;
- preferências pessoais e lista de professores bloqueados removidas da configuração pública;
- avaliações docentes reais substituídas por um arquivo vazio de exemplo;
- screenshots renomeados e organizados em `assets/`;
- dependências ajustadas para refletir os imports da aplicação;
- documentação atualizada para diferenciar recursos implementados de próximos passos.

## Conteúdo deliberadamente não publicado

- `entradas/` reais do usuário;
- comentários integrais coletados de serviços externos;
- sessão/token de autenticação local;
- arquivos-fonte oficiais volumosos usados apenas para regenerar bases curriculares.

## Observação

Os JSONs curriculares presentes no repositório são dados estruturados utilizados pela aplicação. As regras acadêmicas podem mudar; os usuários devem confirmar informações em fontes oficiais da UFABC.
