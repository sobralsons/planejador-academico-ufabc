import copy
import json
from pathlib import Path

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
    matriz = inventario["cursos"][0]["matrizes"][0]
    matriz.update(
        aplicabilidade="nao_aplicavel",
        evidencias_aplicabilidade=["ato oficial exclui estudantes ativos"],
        modelagem="nao_iniciada",
        testes="nao_iniciados",
        revisao_humana="nao_iniciada",
    )

    relatorio = avaliar_cobertura_publica(inventario)

    assert relatorio.liberacao_permitida
    assert relatorio.matrizes_aplicaveis == 0


def test_inventario_vazio_nunca_e_considerado_publicavel():
    relatorio = avaliar_cobertura_publica({"total_cursos": 0, "cursos": []})

    assert not relatorio.liberacao_permitida
    assert relatorio.inconsistencias == ("inventário sem cursos",)
