from dataclasses import fields

import pytest

from persistencia import (
    ClassePersistencia,
    ErroAutorizacaoPersistencia,
    ErroConflitoPersistencia,
    RascunhoPlanejamentoPersistivel,
    RepositorioPlanejamentosMemoria,
    politica_dados,
)
from planejador.modelos import RegistroHistorico


def _plano(
    planejamento_id: str = "plano-1",
    proprietario_id: str = "user-a",
    *,
    titulo: str = "Meu planejamento",
) -> RascunhoPlanejamentoPersistivel:
    return RascunhoPlanejamentoPersistivel(
        planejamento_id=planejamento_id,
        proprietario_id=proprietario_id,
        curso_id="ciencia_dados",
        matriz_id="2023",
        versao_regras="regras-v1",
        titulo=titulo,
        componentes_planejados=("MCTA001-17", "MCTB002-17"),
    )


def test_politica_mantem_historico_e_evidencias_temporarios_por_padrao():
    por_chave = {item.chave: item for item in politica_dados()}

    for chave in (
        "arquivo_historico_bruto",
        "registros_historico_detalhados",
        "evidencias_academicas_derivadas",
    ):
        assert por_chave[chave].classe == ClassePersistencia.TEMPORARIO
        assert por_chave[chave].persistir_por_padrao is False

    assert (
        por_chave["credenciais_tokens_sessoes"].classe
        == ClassePersistencia.PROIBIDO
    )
    assert por_chave["credenciais_tokens_sessoes"].persistir_por_padrao is False


def test_contrato_persistivel_nao_tem_campos_de_identidade_ou_historico():
    nomes = {campo.name for campo in fields(RascunhoPlanejamentoPersistivel)}

    proibidos = {
        "ra",
        "nome",
        "email",
        "conceito",
        "docentes",
        "turma",
        "historico",
        "registro_historico",
        "token",
        "sessao",
        "senha",
    }
    assert not (nomes & proibidos)
    assert "proprietario_id" in nomes
    assert "componentes_planejados" in nomes


def test_repositorio_isola_leitura_listagem_edicao_e_exclusao_por_usuario():
    repo = RepositorioPlanejamentosMemoria()
    plano_a = _plano()
    plano_b = _plano("plano-2", "user-b", titulo="Plano B")
    repo.salvar("user-a", plano_a)
    repo.salvar("user-b", plano_b)

    assert repo.obter("user-a", "plano-1") == plano_a
    assert repo.obter("user-b", "plano-1") is None
    assert repo.listar("user-a") == (plano_a,)
    assert repo.listar("user-b") == (plano_b,)

    assert repo.renomear("user-b", "plano-1", "Ataque") is None
    assert repo.obter("user-a", "plano-1").titulo == "Meu planejamento"

    assert repo.excluir("user-b", "plano-1") is False
    assert repo.obter("user-a", "plano-1") == plano_a


def test_salvar_com_proprietario_diferente_do_ator_e_rejeitado():
    repo = RepositorioPlanejamentosMemoria()

    with pytest.raises(ErroAutorizacaoPersistencia, match="não autorizada"):
        repo.salvar("user-b", _plano(proprietario_id="user-a"))

    assert repo.quantidade_total_para_testes() == 0


def test_colisao_de_id_entre_usuarios_nao_transfere_propriedade():
    repo = RepositorioPlanejamentosMemoria()
    repo.salvar("user-a", _plano())

    with pytest.raises(ErroConflitoPersistencia, match="indisponível"):
        repo.salvar(
            "user-b",
            _plano("plano-1", "user-b", titulo="Tentativa de colisão"),
        )

    assert repo.obter("user-a", "plano-1").proprietario_id == "user-a"


def test_excluir_todos_remove_somente_dados_do_proprio_usuario():
    repo = RepositorioPlanejamentosMemoria()
    repo.salvar("user-a", _plano("a-1", "user-a"))
    repo.salvar("user-a", _plano("a-2", "user-a"))
    repo.salvar("user-b", _plano("b-1", "user-b"))

    assert repo.excluir_todos("user-a") == 2
    assert repo.listar("user-a") == ()
    assert len(repo.listar("user-b")) == 1
    assert repo.quantidade_total_para_testes() == 1


def test_historico_detalhado_nao_pode_ser_salvo_na_fronteira_de_planejamentos():
    repo = RepositorioPlanejamentosMemoria()
    registro = RegistroHistorico(
        periodo="2026.1",
        categoria_original="Sintética",
        codigo="A",
        nome="Componente sintético",
        creditos=4,
        carga_horaria=48,
        carga_extensao=0,
        turma="A",
        conceito="A",
        situacao="APR",
        docentes="Docente sintético",
    )

    with pytest.raises(TypeError, match="RascunhoPlanejamentoPersistivel"):
        repo.salvar("user-a", registro)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "alteracao",
    [
        {"planejamento_id": ""},
        {"proprietario_id": "usuario com espaco"},
        {"curso_id": "curso/com/barra"},
        {"titulo": " "},
        {"componentes_planejados": ("A", "A")},
        {"schema_version": True},
        {"schema_version": 2},
    ],
)
def test_contrato_rejeita_identificadores_e_estrutura_invalidos(alteracao):
    dados = {
        "planejamento_id": "plano-1",
        "proprietario_id": "user-a",
        "curso_id": "curso",
        "matriz_id": "2023",
        "versao_regras": "v1",
        "titulo": "Plano",
        "componentes_planejados": ("A",),
        "schema_version": 1,
    }
    dados.update(alteracao)

    with pytest.raises(ValueError):
        RascunhoPlanejamentoPersistivel(**dados)


def test_repositorio_permite_atualizar_somente_registro_do_mesmo_proprietario():
    repo = RepositorioPlanejamentosMemoria()
    original = _plano()
    repo.salvar("user-a", original)

    atualizado = _plano(titulo="Plano revisado")
    repo.salvar("user-a", atualizado)

    assert repo.obter("user-a", "plano-1") == atualizado
    assert repo.quantidade_total_para_testes() == 1
