from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260924193000_create_planejamentos_salvos.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_migration_existe_e_nao_modela_dados_pessoais_do_historico():
    sql = _sql()
    assert "create table public.planejamentos_salvos" in sql
    assert "create table public.planejamento_componentes" in sql

    proibidos = (
        " ra ",
        "email",
        "nota",
        "conceito",
        "docente",
        "turma",
        "historico_bruto",
        "token",
        "senha",
    )
    corpo_tabelas = sql.split("alter table public.planejamentos_salvos")[0]
    for termo in proibidos:
        assert termo not in corpo_tabelas


def test_todas_as_tabelas_expostas_tem_rls_habilitada():
    sql = _sql()
    assert (
        "alter table public.planejamentos_salvos enable row level security;"
        in sql
    )
    assert (
        "alter table public.planejamento_componentes enable row level security;"
        in sql
    )


def test_anon_nao_recebe_permissoes_e_authenticated_recebe_apenas_dml():
    sql = _sql()
    assert (
        "revoke all on table public.planejamentos_salvos from anon, authenticated;"
        in sql
    )
    assert (
        "revoke all on table public.planejamento_componentes from anon, authenticated;"
        in sql
    )
    assert "grant select, insert, update, delete" in sql
    assert "grant all" not in sql
    assert not re.search(r"grant\s+.+\s+to\s+anon\b", sql)


def test_cada_operacao_tem_politica_explicita_para_authenticated():
    sql = _sql()
    for tabela in ("planejamentos_salvos", "planejamento_componentes"):
        for operacao in ("select", "insert", "update", "delete"):
            nome = f'{tabela}_{operacao}_proprio'
            assert f'create policy "{nome}"' in sql
            trecho = sql.split(f'create policy "{nome}"', 1)[1]
            trecho = trecho.split("create policy", 1)[0]
            assert f"for {operacao}" in trecho
            assert "to authenticated" in trecho
            assert "(select auth.uid()) is not null" in trecho
            assert "(select auth.uid()) = proprietario_id" in trecho


def test_insert_e_update_validam_proprietario_resultante():
    sql = _sql()
    for tabela in ("planejamentos_salvos", "planejamento_componentes"):
        insert = sql.split(
            f'create policy "{tabela}_insert_proprio"', 1
        )[1].split("create policy", 1)[0]
        update = sql.split(
            f'create policy "{tabela}_update_proprio"', 1
        )[1].split("create policy", 1)[0]
        assert "with check" in insert
        assert "using" in update
        assert "with check" in update


def test_proprietario_referencia_auth_users_e_filhos_nao_podem_trocar_dono():
    sql = _sql()
    assert (
        "proprietario_id uuid not null references auth.users(id) on delete cascade"
        in sql
    )
    assert (
        "foreign key (planejamento_id, proprietario_id)"
        in sql
    )
    assert (
        "references public.planejamentos_salvos "
        "(planejamento_id, proprietario_id)"
        in sql
    )


def test_limites_estruturais_do_contrato_persistivel_estao_no_banco():
    sql = _sql()
    assert "char_length(btrim(titulo)) between 1 and 120" in sql
    assert "check (schema_version = 1)" in sql
    assert "check (posicao between 1 and 200)" in sql
    assert "primary key (planejamento_id, codigo_componente)" in sql
    assert "unique (planejamento_id, posicao)" in sql


def test_colunas_de_rls_possuem_indice_dedicado():
    sql = _sql()
    assert "planejamentos_salvos_proprietario_idx" in sql
    assert "planejamento_componentes_proprietario_idx" in sql
