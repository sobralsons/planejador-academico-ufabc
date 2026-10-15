import json
from pathlib import Path

import pytest

from planejador.academico import auditoria_integralizacao
from planejador.curriculo import carregar_curriculo
from planejador.historico import consolidar_historico
from planejador.integracao_motor_curricular import avaliar_bct_2015_em_modo_sombra
from planejador.modelos import RegistroHistorico, ResumoHistorico


BASE = Path(__file__).resolve().parents[1]
CASOS = BASE / "dados/casos_academicos_bct_2015_r1.json"


def _carregar_casos() -> dict:
    return json.loads(CASOS.read_text(encoding="utf-8"))


def _registro(dados: dict) -> RegistroHistorico:
    creditos = dados["creditos"]
    return RegistroHistorico(
        periodo="2026.1",
        categoria_original="Sintética",
        codigo=dados["codigo"],
        nome=f"Componente sintético {dados['codigo']}",
        creditos=creditos,
        carga_horaria=creditos * 12,
        carga_extensao=0,
        turma="A",
        conceito="A",
        situacao="APR",
        docentes="Docente Sintético",
    )


def _estado_legado(requisito: str, legado: dict, metadados: dict) -> str:
    if requisito != "atividades_complementares":
        return legado["por_categoria"]["obrigatoria"]["estado_confirmado"]
    if (
        legado["atividades_complementares_horas"]
        >= metadados["atividades_complementares_horas"]
    ):
        return "cumprido"
    return "pendente"


def test_fixture_e_sintetica_revisavel_e_permanece_nao_publicavel():
    fixture = _carregar_casos()
    metadados, _ = carregar_curriculo("dados/curriculos/bct_2015.json")
    ids = [caso["id"] for caso in fixture["casos"]]

    assert fixture["curso_id"] == "bct_2015"
    assert fixture["matriz_id"] == "2015"
    assert fixture["dados_sinteticos"] is True
    assert fixture["revisao_humana"]["estado"] == "pendente"
    assert fixture["revisao_humana"]["decisao_publicavel"] is False
    assert fixture["fonte_regra"] in metadados["fontes_regras"]
    assert len(ids) == len(set(ids))
    assert all(caso["descricao"].strip() for caso in fixture["casos"])
    assert {caso["tipo"] for caso in fixture["casos"]} == {
        "cumprimento",
        "pendencia",
        "dado_ausente",
        "equivalencia",
        "divergencia",
    }


@pytest.mark.parametrize("caso", _carregar_casos()["casos"], ids=lambda caso: caso["id"])
def test_casos_revisaveis_executam_no_fluxo_real_do_modo_sombra(caso):
    metadados, curriculo_completo = carregar_curriculo(
        "dados/curriculos/bct_2015.json"
    )
    codigo_destino = caso.get("codigo_destino", "BIS0005-15")
    curriculo = {codigo_destino: curriculo_completo[codigo_destino]}
    metadados = {
        **metadados,
        "creditos_obrigatorios": caso.get("minimo_creditos_obrigatorios", 0),
        "creditos_opcao_limitada": 0,
        "creditos_livres": 0,
        "atividades_complementares_horas": caso.get(
            "minimo_atividades_complementares_horas", 0
        ),
    }
    situacao = consolidar_historico(
        [_registro(item) for item in caso.get("registros", [])],
        caso.get("equivalencias", {}),
        resumo=ResumoHistorico(
            atividades_complementares_horas=caso.get(
                "atividades_complementares_horas"
            )
        ),
    )
    legado = auditoria_integralizacao(
        metadados,
        curriculo,
        situacao,
        set(situacao.concluidas),
    )
    if "valor_legado_atividades_complementares" in caso:
        legado["atividades_complementares_horas"] = caso[
            "valor_legado_atividades_complementares"
        ]

    sombra = avaliar_bct_2015_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        resultado_legado=legado,
        pacote_piloto_confirmado=True,
        aplicabilidade_confirmada=True,
        classificacoes_validadas=caso.get("classificacoes_validadas", True),
    )
    esperado = caso["esperado"]
    requisito = esperado["requisito"]

    assert _estado_legado(requisito, legado, metadados) == esperado["estado_legado"]
    assert sombra.requisitos[requisito].estado.value == esperado["estado_generico"]
    assert sombra.divergencias[requisito].classificacao == esperado["divergencia"]
    assert sombra.autoridade == "legado"
    assert sombra.publicavel is False
