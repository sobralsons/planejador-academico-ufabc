import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_06_2026-09-16.json"
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


def test_lote_06_preserva_decisoes_historicas_e_promocao_posterior_do_bch():
    auditoria, vigencia = _carregar()
    auditadas = _por_matriz(auditoria)

    assert set(auditadas) == {
        ("quimica", 2010),
        ("bch", 2015),
        ("quimica_licenciatura", 2022),
    }
    assert all(item["status_antes"] == "pendente" for item in auditadas.values())
    assert all(item["status_resultante"] == "pendente" for item in auditadas.values())
    assert all(item["decisao_publicavel"] is False for item in auditadas.values())

    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}
    assert 2010 in por_curso["quimica"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["bch"]["matrizes_candidatas_anos"]
    assert 2015 not in por_curso["bch"]["matrizes_pendentes_anos"]
    assert 2022 in por_curso["quimica_licenciatura"]["matrizes_pendentes_anos"]


def test_contrato_do_lote_06_expoe_lacunas_e_revisao_humana():
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
        assert item["lacunas"]
        assert item["fontes"]
        assert item["revisao_humana"]["estado"] == "pendente"
        assert item["revisao_humana"]["pronto_para_mudar_status"] is False
        assert item["decisao_publicavel"] is False


def test_fontes_do_lote_06_sao_oficiais_e_identificam_secao():
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


def test_quimica_2010_preserva_evidencia_operacional_sem_promocao_automatica():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("quimica", 2010)]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])
    motivo = item["calculo_termino_validade"]["motivo"]

    assert "se formarão pelo PPC 2010" in efeitos
    assert "80h" in efeitos
    assert item["tempo_integralizacao"]["valor"] is None
    assert "cadeia de substituições 2010→2015→2023" in " ".join(item["possiveis_excecoes"])
    assert "não fecham sozinhas a vigência normativa" in motivo
    assert item["status_resultante"] == "pendente"


def test_bch_2015_registra_estado_historico_antes_da_evidencia_do_lote_07():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("bch", 2015)]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["ppc_substituto"]["ano"] == 2020
    assert item["entrada_em_vigor"]["marco"] == "2020-04-01"
    assert item["tempo_integralizacao"]["valor"] == 9
    assert item["tempo_integralizacao"]["unidade"] == "quadrimestres"
    assert "ingressantes até 2019" in efeitos
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert item["status_resultante"] == "pendente"


def test_lic_quimica_2022_preserva_12_quadrimestres_sem_inventar_extincao():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("quimica_licenciatura", 2022)]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["tempo_integralizacao"]["valor"] == 12
    assert item["tempo_integralizacao"]["unidade"] == "quadrimestres"
    assert "Ingressantes até 2022" in efeitos
    assert "PPCs 2022, 2015 e 2010" in efeitos
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert item["status_resultante"] == "pendente"


def test_lote_06_preserva_resumo_historico_e_estado_global_atual():
    auditoria, vigencia = _carregar()

    assert auditoria["resumo"] == {
        "matrizes_auditadas": 3,
        "permanecem_pendentes": 3,
        "mudaram_para_nao_aplicavel": 0,
        "mudaram_para_candidata_preliminar": 0,
        "decisoes_publicaveis": 0,
    }
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "nao_aplicaveis": 0,
        "pendentes": 37,
        "candidatas": 56,
        "ppcs_historicos_candidatos": 21,
    }


def test_lote_06_nao_declara_suporte_academico():
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
