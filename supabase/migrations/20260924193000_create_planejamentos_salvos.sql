-- Base inicial de persistencia multiusuario.
-- Escopo deliberadamente minimo: somente rascunhos de planejamento.
-- Historico SIGAA bruto/detalhado, evidencias derivadas, RA, nome, email,
-- credenciais e tokens nao pertencem a estas tabelas.

create table public.planejamentos_salvos (
    planejamento_id text not null,
    proprietario_id uuid not null references auth.users(id) on delete cascade,
    curso_id text not null,
    matriz_id text not null,
    versao_regras text not null,
    titulo text not null,
    schema_version smallint not null default 1,
    criado_em timestamptz not null default now(),
    atualizado_em timestamptz not null default now(),

    constraint planejamentos_salvos_id_valido
        check (planejamento_id ~ '^[A-Za-z0-9_.:-]{1,128}$'),
    constraint planejamentos_salvos_curso_valido
        check (curso_id ~ '^[A-Za-z0-9_.:-]{1,128}$'),
    constraint planejamentos_salvos_matriz_valida
        check (matriz_id ~ '^[A-Za-z0-9_.:-]{1,128}$'),
    constraint planejamentos_salvos_versao_valida
        check (versao_regras ~ '^[A-Za-z0-9_.:-]{1,128}$'),
    constraint planejamentos_salvos_titulo_valido
        check (char_length(btrim(titulo)) between 1 and 120),
    constraint planejamentos_salvos_schema_v1
        check (schema_version = 1),
    constraint planejamentos_salvos_pk
        primary key (proprietario_id, planejamento_id)
);

create table public.planejamento_componentes (
    planejamento_id text not null,
    proprietario_id uuid not null,
    codigo_componente text not null,
    posicao smallint not null,

    constraint planejamento_componentes_codigo_valido
        check (codigo_componente ~ '^[A-Za-z0-9_.-]{1,32}$'),
    constraint planejamento_componentes_posicao_valida
        check (posicao between 1 and 200),
    constraint planejamento_componentes_pk
        primary key (proprietario_id, planejamento_id, codigo_componente),
    constraint planejamento_componentes_posicao_unica
        unique (proprietario_id, planejamento_id, posicao),
    constraint planejamento_componentes_plano_fk
        foreign key (proprietario_id, planejamento_id)
        references public.planejamentos_salvos (proprietario_id, planejamento_id)
        on delete cascade
);

alter table public.planejamentos_salvos enable row level security;
alter table public.planejamento_componentes enable row level security;

revoke all on table public.planejamentos_salvos from anon, authenticated;
revoke all on table public.planejamento_componentes from anon, authenticated;

grant select, insert, update, delete
    on table public.planejamentos_salvos
    to authenticated;

grant select, insert, update, delete
    on table public.planejamento_componentes
    to authenticated;

create policy "planejamentos_salvos_select_proprio"
    on public.planejamentos_salvos
    for select
    to authenticated
    using (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

create policy "planejamentos_salvos_insert_proprio"
    on public.planejamentos_salvos
    for insert
    to authenticated
    with check (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

create policy "planejamentos_salvos_update_proprio"
    on public.planejamentos_salvos
    for update
    to authenticated
    using (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    )
    with check (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

create policy "planejamentos_salvos_delete_proprio"
    on public.planejamentos_salvos
    for delete
    to authenticated
    using (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

create policy "planejamento_componentes_select_proprio"
    on public.planejamento_componentes
    for select
    to authenticated
    using (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

create policy "planejamento_componentes_insert_proprio"
    on public.planejamento_componentes
    for insert
    to authenticated
    with check (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

create policy "planejamento_componentes_update_proprio"
    on public.planejamento_componentes
    for update
    to authenticated
    using (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    )
    with check (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

create policy "planejamento_componentes_delete_proprio"
    on public.planejamento_componentes
    for delete
    to authenticated
    using (
        (select auth.uid()) is not null
        and (select auth.uid()) = proprietario_id
    );

comment on table public.planejamentos_salvos is
    'Rascunhos de planejamento pertencentes a um unico usuario autenticado.';

comment on table public.planejamento_componentes is
    'Componentes planejados de um rascunho; no maximo 200 posicoes por planejamento.';
