import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INVENTARIO = BASE / "dados" / "inventario_cursos.json"


def test_inventario_oficial_de_cursos_tem_estrutura_auditavel():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    cursos = data["cursos"]

    assert data["schema_version"] == 3
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
        assert all(base_id in ids for base_id in curso["cursos_base_admitidos"])
        if curso["curso_base"] is not None:
            assert curso["curso_base"] in curso["cursos_base_admitidos"]


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

    assert data["total_documentos_curriculares_localizados"] == len(matrizes) == 51
    assert len({matriz["id"] for matriz in matrizes}) == len(matrizes)

    for matriz in matrizes:
        assert isinstance(matriz["ano"], int)
        assert matriz["rotulo"]
        assert matriz["ato_aprovacao"]
        assert isinstance(matriz["atos_complementares"], list)
        assert isinstance(matriz["observacoes"], list)
        assert matriz["ppc_url"].startswith("https://")
        assert "ufabc.edu.br/" in matriz["ppc_url"]
        assert matriz["indice_oficial_url"].startswith("https://")
        assert "ufabc.edu.br/" in matriz["indice_oficial_url"]
        if matriz["transicao_url"] is not None:
            assert matriz["transicao_url"].startswith("https://")
            assert "ufabc.edu.br/" in matriz["transicao_url"]


def test_todos_os_cursos_tem_fonte_inicial_sem_alegar_cobertura_academica():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    cursos = data["cursos"]

    assert data["total_cursos_com_fontes_localizadas"] == len(cursos) == 35
    for curso in cursos:
        assert curso["levantamento_matrizes"] == "fontes_localizadas_parcialmente"
        assert curso["validacao_academica"] == "nao_iniciada"
        assert curso["matrizes"]


def test_alertas_de_multipla_trajetoria_permanecem_explicitos():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    por_id = {curso["id"]: curso for curso in data["cursos"]}

    filosofia = por_id["filosofia_bacharelado"]["matrizes"][0]
    planejamento = por_id["planejamento_territorial"]["matrizes"][0]

    assert por_id["filosofia_bacharelado"]["cursos_base_admitidos"] == [
        "bch",
        "bct",
        "lch",
    ]
    assert por_id["planejamento_territorial"]["cursos_base_admitidos"] == [
        "bch",
        "bct",
    ]
    assert any("BC&T e de LCH" in note for note in filosofia["observacoes"])
    assert any("ingressantes de BC&T" in note for note in planejamento["observacoes"])


def test_retificacoes_nao_sao_confundidas_com_regras_de_transicao():
    data = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    por_matriz = {
        matriz["id"]: matriz
        for curso in data["cursos"]
        for matriz in curso["matrizes"]
    }

    for matrix_id in {"bct_2023", "bct_2015", "leila_2025"}:
        assert por_matriz[matrix_id]["atos_complementares"]
        assert por_matriz[matrix_id]["ato_transicao"] is None


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
