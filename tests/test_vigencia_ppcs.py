import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INVENTARIO = BASE / "dados" / "inventario_cursos.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    inventario = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return inventario, vigencia


def test_avaliacao_de_vigencia_cobre_exatamente_os_93_ppcs():
    inventario, vigencia = _carregar()

    inventariados = {
        (curso["id"], matriz["ano"])
        for curso in inventario["cursos"]
        for matriz in curso["matrizes"]
    }
    aplicaveis = {
        (item["curso_id"], ano)
        for item in vigencia["classificacao"]
        for ano in item["matrizes_candidatas_anos"]
    }
    nao_aplicaveis = {
        (item["curso_id"], ano)
        for item in vigencia["classificacao"]
        for ano in item["matrizes_nao_aplicaveis_anos"]
    }

    pendentes = {
        (item["curso_id"], ano)
        for item in vigencia["classificacao"]
        for ano in item["matrizes_pendentes_anos"]
    }
    assert not (pendentes & aplicaveis)
    assert not (pendentes & nao_aplicaveis)
    assert not (aplicaveis & nao_aplicaveis)
    assert aplicaveis | nao_aplicaveis | pendentes == inventariados
    assert len(inventariados) == 93
    assert len(aplicaveis) == 48
    assert len(nao_aplicaveis) == 0
    assert len(pendentes) == 45
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "candidatas": 48,
        "nao_aplicaveis": 0,
        "pendentes": 45,
        "ppcs_historicos_candidatos": 13,
    }


def test_todos_os_cursos_tem_justificativa_e_evidencia_oficial():
    inventario, vigencia = _carregar()
    cursos = {curso["id"] for curso in inventario["cursos"]}
    classificados = {item["curso_id"] for item in vigencia["classificacao"]}
    fontes = vigencia["fontes_oficiais"]

    assert classificados == cursos
    assert all(fonte["url"].startswith("https://") for fonte in fontes.values())
    assert all("ufabc.edu.br/" in fonte["url"] for fonte in fontes.values())

    for item in vigencia["classificacao"]:
        assert item["justificativa"].strip()
        assert item["evidencias"]
        assert all(chave in fontes for chave in item["evidencias"])


def test_ppcs_historicos_que_ainda_podem_reger_estudantes_ativos():
    _, vigencia = _carregar()
    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}

    assert 2022 in por_curso["lch"]["matrizes_candidatas_anos"]
    assert 2022 in por_curso["lcne"]["matrizes_candidatas_anos"]
    assert 2017 in por_curso["ciencia_computacao"]["matrizes_candidatas_anos"]
    assert 2021 in por_curso["neurociencia"]["matrizes_candidatas_anos"]
    assert 2015 in por_curso["quimica"]["matrizes_candidatas_anos"]
    assert 2010 in por_curso["quimica"]["matrizes_pendentes_anos"]

    engenharias = {
        "engenharia_ambiental_urbana",
        "engenharia_energia",
        "engenharia_informacao",
        "engenharia_instrumentacao_automacao_robotica",
        "engenharia_materiais",
        "engenharia_aeroespacial",
        "engenharia_biomedica",
        "engenharia_gestao",
    }
    assert all(
        2017 in por_curso[curso_id]["matrizes_candidatas_anos"]
        for curso_id in engenharias
    )


def test_exclusoes_sem_comprovacao_voltam_a_ficar_pendentes_salvo_promocao_documentada():
    _, vigencia = _carregar()
    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}

    assert 2015 in por_curso["bct"]["matrizes_pendentes_anos"]
    assert 2018 in por_curso["biotecnologia"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["ciencias_biologicas"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["ciencia_computacao"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["neurociencia"]["matrizes_pendentes_anos"]
    assert 2021 not in por_curso["neurociencia"]["matrizes_pendentes_anos"]
    assert 2021 in por_curso["neurociencia"]["matrizes_candidatas_anos"]
    assert 2015 not in por_curso["quimica"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["quimica"]["matrizes_candidatas_anos"]


def test_avaliacao_e_explicitamente_datada_e_nao_confunde_vigencia_com_suporte():
    _, vigencia = _carregar()

    assert vigencia["avaliado_em"] == "2026-09-16"
    assert vigencia["criterio"]["data_corte"] == "2026-09-16"
    assert "Não modela regras curriculares" in vigencia["escopo"]
    assert any(
        "não declara qualquer matriz academicamente suportada" in ressalva
        for ressalva in vigencia["ressalvas"]
    )


def test_reabertura_preserva_historico_e_registra_promocoes_documentadas():
    _, vigencia = _carregar()
    assert vigencia["schema_version"] == 2
    assert vigencia["estado_avaliacao"] == "preliminar"
    assert vigencia["revisao_humana"] == "pendente"

    promovidas_do_historico = {
        ("neurociencia", 2021),
        ("quimica", 2015),
    }
    encontradas = set()

    for item in vigencia["classificacao"]:
        anterior = item["classificacao_anterior"]
        assert anterior["estado"] == "nao_validada"
        assert anterior["justificativa"].strip()
        anteriores_excluidas = set(anterior["matrizes_nao_aplicaveis_anos"])
        pendentes = set(item["matrizes_pendentes_anos"])
        promovidas = anteriores_excluidas & set(item["matrizes_candidatas_anos"])
        assert anteriores_excluidas == pendentes | promovidas
        encontradas |= {(item["curso_id"], ano) for ano in promovidas}
        assert item["revisao_humana"] == "pendente"
        assert not item["decisoes_exclusao"]

    assert encontradas == promovidas_do_historico
