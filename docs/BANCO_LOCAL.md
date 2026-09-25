# Banco local e Supabase

Esta etapa cria somente a migration versionada do primeiro dado persistível: rascunhos de planejamento.

## Estado atual

A migration está em:

`supabase/migrations/20260924193000_create_planejamentos_salvos.sql`

Ela cria:

- `planejamentos_salvos`;
- `planejamento_componentes`;
- vínculo do proprietário com `auth.users(id)`;
- RLS para SELECT, INSERT, UPDATE e DELETE;
- ausência de permissão para `anon`;
- índices nas colunas usadas pelas políticas.

Histórico SIGAA, notas, docentes, RA, nome, e-mail, arquivos e tokens continuam fora do schema.

## Validação atual

Os testes Python verificam o contrato estrutural da migration, mas isso **não substitui executar o SQL em PostgreSQL/Supabase**.

Antes de conectar qualquer projeto remoto, a próxima etapa deve:

1. instalar/configurar Supabase CLI e o runtime local exigido por ela;
2. aplicar as migrations em banco local descartável;
3. testar dois usuários sintéticos e acesso anônimo;
4. provar SELECT/INSERT/UPDATE/DELETE próprios;
5. provar bloqueio de acesso cruzado;
6. só depois considerar ligação com um projeto Supabase de desenvolvimento.

Nenhum banco remoto deve ser tratado como validado apenas porque o arquivo SQL existe.
