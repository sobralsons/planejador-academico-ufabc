import copy
import json
from pathlib import Path

import pytest

from planejador.cobertura import avaliar_cobertura_publica


BASE = Path(__file__).resolve().parents[1]
INVENTARIO = BASE / "dados" / "inventario_cursos.json"


def _inventario_real():
    return json.loads(INVENTARIO.read_text(encoding="utf-8"))


def _inventario_minimo_completo():
    return {
        "total_cursos": 1,
        "cursos": [
            {
                "id": "curso_teste",
                "levantamento_matrizes": "concluido",
                "matrizes": [
                    {
                        "id": "curso_teste_2023",
                        "aplicabilidade": "aplicavel",
                        "evidencias_aplicabilidade": ["ato oficial de transição"],
                        "modelagem": "concluida",
                        "testes": "aprovados",
                        "revisao_humana": "aprovada",
                    }
                ],
            }
        ],
    }


def test_inventario_atual_bloqueia_liberacao_publica():
    relatorio = avaliar_cobertura_publica(_inventario_real())

    assert not relatorio.liberacao_permitida
    assert relatorio.cursos_total == 35
    assert len(relatorio.cursos_com_levantamento_incompleto) == 35
    assert relatorio.matrizes_total == 93
    assert len(relatorio.matrizes_com_aplicabilidade_pendente) == 93
    assert relatorio.matrizes_aplicaveis == 0
    assert relatorio.matrizes_aplicaveis_nao_validadas == ()
    assert relatorio.impedimentos


def test_inventario_completo_permite_liberacao_publica():
    relatorio = avaliar_cobertura_publica(_inventario_minimo_completo())

    assert relatorio.liberacao_permitida
    assert relatorio.impedimentos == ()


def test_matriz_aplicavel_sem_validacao_bloqueia_liberacao():
    inventario = copy.deepcopy(_inventario_minimo_completo())
    inventario["cursos"][0]["matrizes"][0]["testes"] = "nao_iniciados"

    relatorio = avaliar_cobertura_publica(inventario)

    assert not relatorio.liberacao_permitida
    assert relatorio.matrizes_aplicaveis_nao_validadas == (
        "curso_teste_2023",
    )


def test_matriz_nao_aplicavel_nao_exige_modelagem():
    inventario = _inventario_minimo_completo()
    matriz = copy.deepcopy(inventario["cursos"][0]["matrizes"][0])
    matriz.update(
        id="curso_teste_2010",
        aplicabilidade="nao_aplicavel",
        evidencias_aplicabilidade=["ato oficial exclui estudantes ativos"],
        modelagem="nao_iniciada",
        testes="nao_iniciados",
        revisao_humana="aprovada",
    )
    inventario["cursos"][0]["matrizes"].append(matriz)

    relatorio = avaliar_cobertura_publica(inventario)

    assert relatorio.liberacao_permitida
    assert relatorio.matrizes_aplicaveis == 1


@pytest.mark.parametrize("evidencias", [None, [], [""], ["  "], "ato", [None]])
@pytest.mark.parametrize("aplicabilidade", ["aplicavel", "nao_aplicavel"])
def test_decisao_sem_evidencia_valida_bloqueia(evidencias, aplicabilidade):
    inventario = _inventario_minimo_completo()
    matriz = copy.deepcopy(inventario["cursos"][0]["matrizes"][0])
    matriz.update(id="outra", aplicabilidade=aplicabilidade,
                  evidencias_aplicabilidade=evidencias)
    inventario["cursos"][0]["matrizes"].append(matriz)
    assert not avaliar_cobertura_publica(inventario).liberacao_permitida


def test_exclusao_exige_revisao_humana_mesmo_com_evidencia():
    inventario = _inventario_minimo_completo()
    matriz = copy.deepcopy(inventario["cursos"][0]["matrizes"][0])
    matriz.update(id="antiga", aplicabilidade="nao_aplicavel",
                  revisao_humana="nao_iniciada")
    inventario["cursos"][0]["matrizes"].append(matriz)
    relatorio = avaliar_cobertura_publica(inventario)
    assert not relatorio.liberacao_permitida
    assert "antiga" in relatorio.matrizes_com_aplicabilidade_pendente


def test_nao_pode_excluir_todas_as_matrizes_de_um_curso():
    inventario = _inventario_minimo_completo()
    inventario["cursos"][0]["matrizes"][0]["aplicabilidade"] = "nao_aplicavel"
    relatorio = avaliar_cobertura_publica(inventario)
    assert not relatorio.liberacao_permitida
    assert "curso curso_teste sem matriz aplicável" in relatorio.inconsistencias


def test_inventario_vazio_nunca_e_considerado_publicavel():
    relatorio = avaliar_cobertura_publica({"total_cursos": 0, "cursos": []})

    assert not relatorio.liberacao_permitida
    assert relatorio.inconsistencias == ("inventário sem cursos",)
