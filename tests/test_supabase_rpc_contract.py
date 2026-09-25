from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260925163000_create_salvar_planejamento_rpc.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_rpc_nao_recebe_proprietario_e_deriva_dono_de_auth_uid():
    sql = _sql()

    assinatura = sql.split("returns void", 1)[0]
    assert "p_proprietario" not in assinatura
    assert "proprietario_id" not in assinatura
    assert "v_proprietario_id uuid := auth.uid()" in sql


def test_rpc_e_security_invoker_e_nao_bypassa_rls():
    sql = _sql()

    assert "security invoker" in sql
    assert "security definer" not in sql
    assert "revoke all on function" in sql
    assert "from public, anon" in sql
    assert "grant execute on function" in sql
    assert "to authenticated" in sql


def test_rpc_salva_plano_e_componentes_no_mesmo_corpo_transacional():
    sql = _sql()

    corpo = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    assert "insert into public.planejamentos_salvos" in corpo
    assert "on conflict (proprietario_id, planejamento_id)" in corpo
    assert "delete from public.planejamento_componentes" in corpo
    assert "insert into public.planejamento_componentes" in corpo
    assert "with ordinality" in corpo


def test_rpc_nao_modela_dados_pessoais_ou_historico():
    sql = re.sub(r"--.*$", "", _sql(), flags=re.MULTILINE)

    for termo in (
        "email",
        "nome",
        "ra ",
        "nota",
        "conceito",
        "docente",
        "turma",
        "historico",
        "token",
        "senha",
    ):
        assert termo not in sql
