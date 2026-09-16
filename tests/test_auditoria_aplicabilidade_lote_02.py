import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_02_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def test_lote_02_audita_tres_familias_sem_promover_status():
    auditoria, vigencia = _carregar()
    auditadas = {
        (item["curso_id"], item["matriz_ano"]): item
        for item in auditoria["matrizes"]
    }

    assert set(auditadas) == {
        ("politicas_publicas", 2015),
        ("ciencia_computacao", 2015),
        ("filosofia_licenciatura", 2022),
    }
    assert all(item["status_antes"] == "pendente" for item in auditadas.values())
    assert all(item["status_resultante"] == "pendente" for item in auditadas.values())
    assert all(item["decisao_publicavel"] is False for item in auditadas.values())

    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}
    assert 2015 in por_curso["politicas_publicas"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["ciencia_computacao"]["matrizes_pendentes_anos"]
    assert 2022 in por_curso["filosofia_licenciatura"]["matrizes_pendentes_anos"]


def test_contrato_individual_tem_campos_e_revisao_humana_pendente():
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
        assert item["revisao_humana"]["pronto_para_mudar_status"] is False


def test_fontes_usadas_sao_oficiais_e_identificam_secao():
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


def test_bpp_2015_nao_usa_prazo_de_minuta_como_regra_final():
    auditoria, _ = _carregar()
    item = next(
        item
        for item in auditoria["matrizes"]
        if item["curso_id"] == "politicas_publicas"
    )
    fontes = auditoria["fontes_oficiais"]

    assert "2030" in fontes["bpp_minuta_transicao_2023"]["interpretacao"]
    assert "não contém data terminal" in fontes["bpp_transicao_final_30_2023"]["interpretacao"]
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert "retirada" in item["calculo_termino_validade"]["motivo"]
    assert item["status_resultante"] == "pendente"


def test_bcc_2015_preserva_conflito_entre_substituicao_e_ppc_do_ano_de_ingresso():
    auditoria, _ = _carregar()
    item = next(
        item
        for item in auditoria["matrizes"]
        if item["curso_id"] == "ciencia_computacao"
    )
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["ppc_substituto"]["ano"] == 2017
    assert item["tempo_integralizacao"]["valor"] == 4
    assert item["tempo_integralizacao"]["unidade"] == "anos"
    assert "PPC vigente em seu ano de ingresso" in efeitos
    assert "tensão documental" in efeitos
    assert item["status_resultante"] == "pendente"


def test_lfil_2022_preserva_opcao_explicita_sem_inventar_data_terminal():
    auditoria, _ = _carregar()
    item = next(
        item
        for item in auditoria["matrizes"]
        if item["curso_id"] == "filosofia_licenciatura"
    )
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["tempo_integralizacao"]["valor"] == 12
    assert item["tempo_integralizacao"]["unidade"] == "quadrimestres"
    assert "matrizes 2022 ou 2023" in efeitos
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert item["status_resultante"] == "pendente"


def test_lote_02_nao_altera_resumo_global_nem_declara_suporte():
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
        "pendentes": 47,
        "candidatas": 46,
        "ppcs_historicos_candidatos": 11,
    }
    assert all(
        "suportada" not in item.get("status_resultante", "")
        for item in auditoria["matrizes"]
    )
