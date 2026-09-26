begin;

select plan(13);

insert into auth.users (id, email)
values
  ('11111111-1111-1111-1111-111111111111', 'rpc-a@example.invalid'),
  ('22222222-2222-2222-2222-222222222222', 'rpc-b@example.invalid');

set local role anon;

select throws_ok(
  $call$
    select public.salvar_planejamento_autenticado(
      'rpc-plano', 'curso', '2023', 'v1', 'Anon', array['A']::text[]
    )
  $call$,
  '42501',
  null,
  'anon nao executa RPC de persistencia'
);

set local role authenticated;
set local request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';

select lives_ok(
  $call$
    select public.salvar_planejamento_autenticado(
      'rpc-plano', 'curso-a', '2023', 'v1', 'Plano A', array['A','B']::text[]
    )
  $call$,
  'usuario A salva planejamento por RPC'
);

select results_eq(
  $$select proprietario_id::text
      from public.planejamentos_salvos
     where planejamento_id = 'rpc-plano'$$,
  array['11111111-1111-1111-1111-111111111111'::text],
  'RPC deriva proprietario de auth.uid'
);

select results_eq(
  $$select codigo_componente || ':' || posicao::text
      from public.planejamento_componentes
     where planejamento_id = 'rpc-plano'
     order by posicao$$,
  array['A:1'::text, 'B:2'::text],
  'RPC preserva ordem dos componentes'
);

select lives_ok(
  $call$
    select public.salvar_planejamento_autenticado(
      'rpc-plano', 'curso-a', '2023', 'v2', 'Plano A v2', array['B','C']::text[]
    )
  $call$,
  'usuario A atualiza mesmo planejamento atomicamente'
);

select results_eq(
  $$select titulo
      from public.planejamentos_salvos
     where planejamento_id = 'rpc-plano'$$,
  array['Plano A v2'::text],
  'update pela RPC altera campos do planejamento'
);

select results_eq(
  $$select codigo_componente || ':' || posicao::text
      from public.planejamento_componentes
     where planejamento_id = 'rpc-plano'
     order by posicao$$,
  array['B:1'::text, 'C:2'::text],
  'update pela RPC substitui componentes antigos'
);

select throws_ok(
  $call$
    select public.salvar_planejamento_autenticado(
      'rpc-plano', 'curso-a', '2023', 'v3', 'Nao deve persistir',
      array['D','D']::text[]
    )
  $call$,
  '23505',
  null,
  'falha em componentes invalida a chamada inteira'
);

select results_eq(
  $$select titulo
      from public.planejamentos_salvos
     where planejamento_id = 'rpc-plano'$$,
  array['Plano A v2'::text],
  'falha atomica preserva titulo anterior'
);

select results_eq(
  $$select codigo_componente || ':' || posicao::text
      from public.planejamento_componentes
     where planejamento_id = 'rpc-plano'
     order by posicao$$,
  array['B:1'::text, 'C:2'::text],
  'falha atomica preserva componentes anteriores'
);

set local request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';

select lives_ok(
  $call$
    select public.salvar_planejamento_autenticado(
      'rpc-plano', 'curso-b', '2023', 'v1', 'Plano B', array['X']::text[]
    )
  $call$,
  'usuario B reutiliza o mesmo planejamento_id no proprio escopo'
);

select results_eq(
  $$select titulo
      from public.planejamentos_salvos
     where planejamento_id = 'rpc-plano'$$,
  array['Plano B'::text],
  'usuario B ve somente sua versao do id compartilhado'
);

set local request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';

select results_eq(
  $$select titulo
      from public.planejamentos_salvos
     where planejamento_id = 'rpc-plano'$$,
  array['Plano A v2'::text],
  'usuario A continua vendo apenas sua versao apos escrita de B'
);

select * from finish();
rollback;
