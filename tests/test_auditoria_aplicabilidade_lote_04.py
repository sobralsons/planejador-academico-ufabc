import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_04_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def _por_matriz(auditoria):
    return {
        (item["curso_id"], item["matriz_ano"]): item
        for item in auditoria["matrizes"]
    }


def test_lote_04_audita_tres_matrizes_e_promove_apenas_neuro_2021():
    auditoria, vigencia = _carregar()
    auditadas = _por_matriz(auditoria)

    assert set(auditadas) == {
        ("neurociencia", 2021),
        ("neurociencia", 2015),
        ("lcne", 2019),
    }
    assert all(item["status_antes"] == "pendente" for item in auditadas.values())
    assert auditadas[("neurociencia", 2021)]["status_resultante"] == "candidata_preliminar"
    assert auditadas[("neurociencia", 2015)]["status_resultante"] == "pendente"
    assert auditadas[("lcne", 2019)]["status_resultante"] == "pendente"
    assert all(item["decisao_publicavel"] is False for item in auditadas.values())

    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}
    assert 2021 in por_curso["neurociencia"]["matrizes_candidatas_anos"]
    assert 2015 in por_curso["neurociencia"]["matrizes_pendentes_anos"]
    assert 2019 in por_curso["lcne"]["matrizes_pendentes_anos"]


def test_contrato_do_lote_04_preserva_revisao_humana_e_nao_publica():
    auditoria, _ = _carregar()
    obrigatorios = set(auditoria["campos_obrigatorios_por_decisao"])

    for item in auditoria["matrizes"]:
        assert obrigatorios <= set(item)
        assert item["ppc_substituido"]["ano"] == item["matriz_ano"]
        assert item["ppc_substituto"]["ano"] > item["matriz_ano"]
        assert item["entrada_em_vigor"]["estado"]
        assert item["tempo_integralizacao"]["estado"]
        assert item["calculo_termino_validade"]["estado"] == "inconclusivo"
        assert item["calculo_termino_validade"]["motivo"].strip()
        assert item["regras_transicao"]
        assert item["possiveis_excecoes"]
        assert item["fontes"]
        assert item["revisao_humana"]["estado"] == "pendente"
        assert item["decisao_publicavel"] is False

    assert _por_matriz(auditoria)[("neurociencia", 2021)]["revisao_humana"]["pronto_para_mudar_status"] is True
    assert _por_matriz(auditoria)[("neurociencia", 2015)]["revisao_humana"]["pronto_para_mudar_status"] is False
    assert _por_matriz(auditoria)[("lcne", 2019)]["revisao_humana"]["pronto_para_mudar_status"] is False


def test_fontes_do_lote_04_sao_oficiais_e_identificam_secao():
    auditoria, _ = _carregar()
    fontes = auditoria["fontes_oficiais"]
    usadas = {
        fonte_id
        for item in auditoria["matrizes"]
        for fonte_id in item["fontes"]
    }

    assert usadas <= set(fontes)
    for fonte_id in usadas:
        fonte = fontes[fonte_id]
        assert fonte["url"].startswith("https://")
        assert "ufabc.edu.br" in fonte["url"]
        assert fonte["referencia"].strip()
        assert fonte["secao"].strip()
        assert fonte["interpretacao"].strip()


def test_neuro_2021_exige_evidencia_positiva_atual_e_ato_de_transicao():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("neurociencia", 2021)]
    fontes = auditoria["fontes_oficiais"]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["ppc_substituto"]["ano"] == 2023
    assert item["tempo_integralizacao"]["valor"] == 12
    assert "Ingressantes até 2022" in efeitos
    assert "três projetos pedagógicos ativos" in efeitos
    assert "três projetos pedagógicos ativos" in fontes["neuro_faq_atual"]["interpretacao"]
    assert item["status_resultante"] == "candidata_preliminar"
    assert item["decisao_publicavel"] is False


def test_neuro_2015_preserva_conflito_entre_prazo_especifico_e_pagina_atual():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("neurociencia", 2015)]
    motivo = item["calculo_termino_validade"]["motivo"]

    assert item["calculo_termino_validade"]["resultado_teorico"] == "2025"
    assert "validade de 4 anos" in item["calculo_termino_validade"]["regra_especifica"]
    assert "três projetos pedagógicos ativos" in motivo
    assert item["status_resultante"] == "pendente"
    assert item["revisao_humana"]["pronto_para_mudar_status"] is False


def test_lcne_2019_nao_converte_prazo_de_migracao_em_extincao():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("lcne", 2019)]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["tempo_integrizacao"]["valor"] == 12
    assert "Ingressantes até 2022" in efeitos
    assert "31/12/2024" in efeitos
    assert "não uma data de extinção" in efeitos
    assert item["status_resultante"] == "pendente"


def test_lote_04_altera_resumo_global_em_exatamente_uma_matriz_sem_criar_exclusao():
    auditoria, vigencia = _carregar()

    assert auditoria["resumo"] == {
        "matrizes_auditadas": 3,
        "permanecem_pendentes": 2,
        "mudaram_para_nao_aplicavel": 0,
        "mudaram_para_candidata_preliminar": 1,
        "decisoes_publicaveis": 0,
    }
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "nao_aplicaveis": 0,
        "pendentes": 42,
        "candidatas": 51,
        "ppcs_historicos_candidatos": 16,
    }


def test_promocao_preliminar_nao_declara_suporte_academico():
    auditoria, vigencia = _carregar()

    assert all(
        "suportada" not in item.get("status_resultante", "")
        for item in auditoria["matrizes"]
    )
    assert vigencia["revisao_humana"] == "pendente"
    assert any(
        "não declara qualquer matriz academicamente suportada" in ressalva
        for ressalva in vigencia["ressalvas"]
    )
