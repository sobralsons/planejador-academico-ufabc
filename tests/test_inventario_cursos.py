import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INVENTARIO = BASE / "dados" / "inventario_cursos.json"


def test_inventario_oficial_de_cursos_tem_estrutura_auditavel():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    cursos = data["cursos"]

    assert data["fonte_oficial"].startswith("https://prograd.ufabc.edu.br/")
    assert data["total_cursos"] == len(cursos) == 35
    assert len({curso["id"] for curso in cursos}) == len(cursos)
    assert len({curso["nome"] for curso in cursos}) == len(cursos)

    ids = {curso["id"] for curso in cursos}
    for curso in cursos:
        assert curso["tipo"] in {"ingresso", "formacao_especifica"}
        assert curso["levantamento_matrizes"] == "pendente"
        assert curso["validacao_academica"] == "nao_iniciada"
        assert curso["matrizes"] == []
        assert curso["curso_base"] is None or curso["curso_base"] in ids


def test_inventario_nao_confunde_curso_com_matriz_validada():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    assert all(not curso["matrizes"] for curso in data["cursos"])
    assert "não matrizes curriculares" in data["aviso"]
