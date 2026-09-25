-- Persistencia atomica de rascunhos pelo usuario autenticado.
-- A funcao nao recebe proprietario_id: o dono vem exclusivamente de auth.uid().
-- Executa como invoker para manter grants e RLS ativos.

create or replace function public.salvar_planejamento_autenticado(
    p_planejamento_id text,
    p_curso_id text,
    p_matriz_id text,
    p_versao_regras text,
    p_titulo text,
    p_componentes text[]
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_proprietario_id uuid := auth.uid();
begin
    if v_proprietario_id is null then
        raise insufficient_privilege
            using message = 'Usuario autenticado obrigatorio.';
    end if;

    insert into public.planejamentos_salvos (
        planejamento_id,
        proprietario_id,
        curso_id,
        matriz_id,
        versao_regras,
        titulo,
        schema_version
    )
    values (
        p_planejamento_id,
        v_proprietario_id,
        p_curso_id,
        p_matriz_id,
        p_versao_regras,
        p_titulo,
        1
    )
    on conflict (proprietario_id, planejamento_id)
    do update set
        curso_id = excluded.curso_id,
        matriz_id = excluded.matriz_id,
        versao_regras = excluded.versao_regras,
        titulo = excluded.titulo,
        schema_version = 1,
        atualizado_em = now();

    delete from public.planejamento_componentes
     where proprietario_id = v_proprietario_id
       and planejamento_id = p_planejamento_id;

    insert into public.planejamento_componentes (
        planejamento_id,
        proprietario_id,
        codigo_componente,
        posicao
    )
    select
        p_planejamento_id,
        v_proprietario_id,
        item.codigo,
        item.posicao::smallint
    from unnest(coalesce(p_componentes, array[]::text[]))
         with ordinality as item(codigo, posicao);
end;
$$;

revoke all on function public.salvar_planejamento_autenticado(
    text, text, text, text, text, text[]
) from public, anon;

grant execute on function public.salvar_planejamento_autenticado(
    text, text, text, text, text, text[]
) to authenticated;

comment on function public.salvar_planejamento_autenticado(
    text, text, text, text, text, text[]
) is
    'Salva atomicamente um rascunho e seus componentes para auth.uid(); nao aceita proprietario_id.';
