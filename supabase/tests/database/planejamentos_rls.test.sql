begin;

select plan(30);

insert into auth.users (id, email)
values
  ('11111111-1111-1111-1111-111111111111', 'rls-a@example.invalid'),
  ('22222222-2222-2222-2222-222222222222', 'rls-b@example.invalid');

-- Sem grant para anon: a requisição deve parar antes das policies.
set local role anon;

select throws_ok(
  $$select * from public.planejamentos_salvos$$,
  '42501',
  null,
  'anon nao le planejamentos'
);

select throws_ok(
  $$insert into public.planejamentos_salvos
      (planejamento_id, proprietario_id, curso_id, matriz_id, versao_regras, titulo)
    values
      ('anon', '11111111-1111-1111-1111-111111111111', 'curso', '2023', 'v1', 'Anon')$$,
  '42501',
  null,
  'anon nao cria planejamentos'
);

select throws_ok(
  $$update public.planejamentos_salvos set titulo = 'Anon'$$,
  '42501',
  null,
  'anon nao atualiza planejamentos'
);

select throws_ok(
  $$delete from public.planejamentos_salvos$$,
  '42501',
  null,
  'anon nao exclui planejamentos'
);

select throws_ok(
  $$select * from public.planejamento_componentes$$,
  '42501',
  null,
  'anon nao le componentes'
);

select throws_ok(
  $$insert into public.planejamento_componentes
      (planejamento_id, proprietario_id, codigo_componente, posicao)
    values
      ('anon', '11111111-1111-1111-1111-111111111111', 'TESTE-1', 1)$$,
  '42501',
  null,
  'anon nao cria componentes'
);

-- Usuario A: CRUD permitido apenas sobre os proprios dados.
set local role authenticated;
set local request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';

select results_eq(
  $$insert into public.planejamentos_salvos
      (planejamento_id, proprietario_id, curso_id, matriz_id, versao_regras, titulo)
    values
      ('plano-a', '11111111-1111-1111-1111-111111111111', 'curso', '2023', 'v1', 'Plano A')
    returning planejamento_id$$,
  array['plano-a'::text],
  'usuario A cria o proprio planejamento'
);

select results_eq(
  $$insert into public.planejamento_componentes
      (planejamento_id, proprietario_id, codigo_componente, posicao)
    values
      ('plano-a', '11111111-1111-1111-1111-111111111111', 'MCTA001-17', 1)
    returning codigo_componente$$,
  array['MCTA001-17'::text],
  'usuario A cria componente no proprio planejamento'
);

select results_eq(
  $$select titulo
      from public.planejamentos_salvos
     where planejamento_id = 'plano-a'$$,
  array['Plano A'::text],
  'usuario A le o proprio planejamento'
);

select results_eq(
  $$select codigo_componente
      from public.planejamento_componentes
     where planejamento_id = 'plano-a'$$,
  array['MCTA001-17'::text],
  'usuario A le o proprio componente'
);

select results_eq(
  $$update public.planejamentos_salvos
       set titulo = 'Plano A atualizado'
     where planejamento_id = 'plano-a'
     returning titulo$$,
  array['Plano A atualizado'::text],
  'usuario A atualiza o proprio planejamento'
);

select results_eq(
  $$update public.planejamento_componentes
       set posicao = 2
     where planejamento_id = 'plano-a'
       and codigo_componente = 'MCTA001-17'
     returning posicao$$,
  array[2::smallint],
  'usuario A atualiza o proprio componente'
);

select throws_ok(
  $$update public.planejamentos_salvos
       set proprietario_id = '22222222-2222-2222-2222-222222222222'
     where planejamento_id = 'plano-a'$$,
  '42501',
  null,
  'usuario A nao transfere planejamento para outro proprietario'
);

select results_eq(
  $$select proprietario_id::text
      from public.planejamentos_salvos
     where planejamento_id = 'plano-a'$$,
  array['11111111-1111-1111-1111-111111111111'::text],
  'transferencia negada preserva proprietario do planejamento'
);

select throws_ok(
  $$update public.planejamento_componentes
       set proprietario_id = '22222222-2222-2222-2222-222222222222'
     where planejamento_id = 'plano-a'
       and codigo_componente = 'MCTA001-17'$$,
  '42501',
  null,
  'usuario A nao transfere componente para outro proprietario'
);

select results_eq(
  $$select proprietario_id::text
      from public.planejamento_componentes
     where planejamento_id = 'plano-a'
       and codigo_componente = 'MCTA001-17'$$,
  array['11111111-1111-1111-1111-111111111111'::text],
  'transferencia negada preserva proprietario do componente'
);

select results_eq(
  $$insert into public.planejamentos_salvos
      (planejamento_id, proprietario_id, curso_id, matriz_id, versao_regras, titulo)
    values
      ('id-compartilhado', '11111111-1111-1111-1111-111111111111', 'curso', '2023', 'v1', 'Mesmo ID A')
    returning planejamento_id$$,
  array['id-compartilhado'::text],
  'usuario A pode usar id local ao proprio escopo'
);

-- Usuario B: mesmo id pode existir, mas os dados de A continuam invisiveis.
set local request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';

select results_eq(
  $$insert into public.planejamentos_salvos
      (planejamento_id, proprietario_id, curso_id, matriz_id, versao_regras, titulo)
    values
      ('id-compartilhado', '22222222-2222-2222-2222-222222222222', 'curso', '2023', 'v1', 'Mesmo ID B')
    returning planejamento_id$$,
  array['id-compartilhado'::text],
  'usuario B pode reutilizar id sem colidir com usuario A'
);

select results_eq(
  $$select titulo
      from public.planejamentos_salvos
     where planejamento_id = 'id-compartilhado'$$,
  array['Mesmo ID B'::text],
  'usuario B ve somente sua linha com id compartilhado'
);

select is_empty(
  $$select planejamento_id
      from public.planejamentos_salvos
     where planejamento_id = 'plano-a'$$,
  'usuario B nao le planejamento de A'
);

select is_empty(
  $$select codigo_componente
      from public.planejamento_componentes
     where planejamento_id = 'plano-a'$$,
  'usuario B nao le componente de A'
);

select throws_ok(
  $$insert into public.planejamentos_salvos
      (planejamento_id, proprietario_id, curso_id, matriz_id, versao_regras, titulo)
    values
      ('ataque', '11111111-1111-1111-1111-111111111111', 'curso', '2023', 'v1', 'Ataque')$$,
  '42501',
  null,
  'usuario B nao cria planejamento para A'
);

select is_empty(
  $$update public.planejamentos_salvos
       set titulo = 'Alterado por B'
     where planejamento_id = 'plano-a'
     returning titulo$$,
  'usuario B nao atualiza planejamento de A'
);

select is_empty(
  $$delete from public.planejamentos_salvos
     where planejamento_id = 'plano-a'
     returning planejamento_id$$,
  'usuario B nao exclui planejamento de A'
);

select is_empty(
  $$update public.planejamento_componentes
       set posicao = 3
     where planejamento_id = 'plano-a'
       and codigo_componente = 'MCTA001-17'
     returning posicao$$,
  'usuario B nao atualiza componente de A'
);

select is_empty(
  $$delete from public.planejamento_componentes
     where planejamento_id = 'plano-a'
       and codigo_componente = 'MCTA001-17'
     returning codigo_componente$$,
  'usuario B nao exclui componente de A'
);

-- Volta a A para provar que as operacoes negadas nao alteraram os dados.
set local request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';

select results_eq(
  $$select titulo
      from public.planejamentos_salvos
     where planejamento_id = 'plano-a'$$,
  array['Plano A atualizado'::text],
  'update negado de B deixou planejamento de A intacto'
);

select results_eq(
  $$select posicao
      from public.planejamento_componentes
     where planejamento_id = 'plano-a'
       and codigo_componente = 'MCTA001-17'$$,
  array[2::smallint],
  'operacoes negadas de B deixaram componente de A intacto'
);

select results_eq(
  $$delete from public.planejamentos_salvos
     where planejamento_id = 'plano-a'
     returning planejamento_id$$,
  array['plano-a'::text],
  'usuario A exclui o proprio planejamento'
);

select is_empty(
  $$select codigo_componente
      from public.planejamento_componentes
     where planejamento_id = 'plano-a'$$,
  'exclusao do planejamento remove componentes por cascade'
);

select * from finish();
rollback;
