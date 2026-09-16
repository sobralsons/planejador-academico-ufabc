import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INVENTARIO = BASE / "dados" / "inventario_cursos.json"


def test_inventario_oficial_de_cursos_tem_estrutura_auditavel():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    cursos = data["cursos"]

    assert data["schema_version"] == 2
    assert data["fonte_oficial"].startswith("https://prograd.ufabc.edu.br/")
    assert data["total_cursos"] == len(cursos) == 35
    assert len({curso["id"] for curso in cursos}) == len(cursos)
    assert len({curso["nome"] for curso in cursos}) == len(cursos)

    ids = {curso["id"] for curso in cursos}
    for curso in cursos:
        assert curso["tipo"] in {
            "ingresso",
            "formacao_especifica",
            "oferta_especial",
        }
        assert curso["levantamento_matrizes"] in {
            "pendente",
            "fontes_localizadas_parcialmente",
        }
        assert curso["validacao_academica"] == "nao_iniciada"
        assert curso["curso_base"] is None or curso["curso_base"] in ids


def test_inventario_nao_confunde_curso_com_matriz_validada():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    matrizes = [
        matriz
        for curso in data["cursos"]
        for matriz in curso["matrizes"]
    ]

    assert matrizes
    assert all(matriz["aplicabilidade"] == "a_confirmar" for matriz in matrizes)
    assert all(matriz["modelagem"] == "nao_iniciada" for matriz in matrizes)
    assert all(matriz["testes"] == "nao_iniciados" for matriz in matrizes)
    assert all(matriz["revisao_humana"] == "nao_iniciada" for matriz in matrizes)
    assert "não torna uma matriz suportada" in data["aviso"]


def test_documentos_curriculares_localizados_sao_unicos_e_rastreaveis():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    matrizes = [
        matriz
        for curso in data["cursos"]
        for matriz in curso["matrizes"]
    ]

    assert data["total_documentos_curriculares_localizados"] == len(matrizes) == 30
    assert len({matriz["id"] for matriz in matrizes}) == len(matrizes)

    for matriz in matrizes:
        assert isinstance(matriz["ano"], int)
        assert matriz["rotulo"]
        assert matriz["ato_aprovacao"]
        assert matriz["ppc_url"].startswith("https://")
        assert "ufabc.edu.br/" in matriz["ppc_url"]
        assert matriz["indice_oficial_url"].startswith("https://")
        assert "ufabc.edu.br/" in matriz["indice_oficial_url"]
        if matriz["transicao_url"] is not None:
            assert matriz["transicao_url"].startswith("https://")
            assert "ufabc.edu.br/" in matriz["transicao_url"]


def test_primeiro_lote_tem_fontes_sem_alegar_cobertura_academica():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    por_id = {curso["id"]: curso for curso in data["cursos"]}
    primeiro_lote = {
        "bct",
        "bch",
        "lch",
        "lcne",
        "leila",
        "lec_ciencias_humanas_sociais",
        "engenharia_ambiental_urbana",
        "engenharia_energia",
        "engenharia_informacao",
        "engenharia_instrumentacao_automacao_robotica",
        "engenharia_materiais",
        "engenharia_aeroespacial",
        "engenharia_biomedica",
        "engenharia_gestao",
    }

    assert data["total_cursos_com_fontes_localizadas"] == len(primeiro_lote) == 14
    for course_id in primeiro_lote:
        curso = por_id[course_id]
        assert curso["levantamento_matrizes"] == "fontes_localizadas_parcialmente"
        assert curso["validacao_academica"] == "nao_iniciada"
        assert curso["matrizes"]


def test_educacao_do_campo_e_registrada_como_oferta_especial():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    curso = next(
        curso
        for curso in data["cursos"]
        if curso["id"] == "lec_ciencias_humanas_sociais"
    )

    assert curso["tipo"] == "oferta_especial"
    assert curso["campi"] == ["São Bernardo do Campo"]
    assert curso["matrizes"][0]["vigencia_ingresso"] == (
        "Turma de ingresso de 2024 da oferta especial"
    )
