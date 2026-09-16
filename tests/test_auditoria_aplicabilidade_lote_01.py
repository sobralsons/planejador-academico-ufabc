import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_01_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def test_lote_audita_exatamente_tres_matrizes_e_preserva_decisao_historica():
    auditoria, vigencia = _carregar()

    auditadas = {
        (item["curso_id"], item["matriz_ano"]): item
        for item in auditoria["matrizes"]
    }
    assert set(auditadas) == {
        ("bct", 2015),
        ("biotecnologia", 2018),
        ("ciencias_biologicas", 2015),
    }
    assert all(item["status_antes"] == "pendente" for item in auditadas.values())
    assert all(item["status_resultante"] == "pendente" for item in auditadas.values())
    assert all(item["decisao_publicavel"] is False for item in auditadas.values())

    # O lote 1 permanece como registro histórico. BCT 2015 foi promovido depois,
    # no lote 7, por nova evidência oficial de uso operacional em 2026.
    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}
    assert 2015 in por_curso["bct"]["matrizes_candidatas_anos"]
    assert 2015 not in por_curso["bct"]["matrizes_pendentes_anos"]
    assert 2018 in por_curso["biotecnologia"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["ciencias_biologicas"]["matrizes_pendentes_anos"]


def test_cada_decisao_preenche_contrato_minimo_e_preserva_revisao_humana():
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


def test_fontes_sao_oficiais_e_especificas_para_o_lote():
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
        assert fonte["tipo"] in {
            "resolucao",
            "ppc",
            "ato_decisorio_consepe",
            "ato_decisorio_cg",
            "documento_complementar_transicao",
            "retificacao",
            "pagina_oficial_prograd",
        }
        assert fonte["referencia"].strip()


def test_bct_2015_nao_e_excluido_por_calculo_teorico_diante_da_transicao_2025():
    auditoria, _ = _carregar()
    bct = next(item for item in auditoria["matrizes"] if item["curso_id"] == "bct")

    assert bct["calculo_termino_validade"]["resultado_teorico"]
    assert bct["calculo_termino_validade"]["estado"] == "inconclusivo"
    assert "bct_transicao_70_2025" in bct["fontes"]
    assert any(
        regra["ato"].startswith("Ato Decisório CG nº 70/2025")
        for regra in bct["regras_transicao"]
    )
    assert bct["status_resultante"] == "pendente"


def test_biotecnologia_2018_considera_atualizacao_de_transicao_de_2025():
    auditoria, _ = _carregar()
    item = next(
        item for item in auditoria["matrizes"] if item["curso_id"] == "biotecnologia"
    )

    assert "biotecnologia_transicao_34_2023" in item["fontes"]
    assert "biotecnologia_ato_71_2025" in item["fontes"]
    assert any("71/2025" in regra["ato"] for regra in item["regras_transicao"])
    assert any("Anexo II" in lacuna and "71/2025" in lacuna for lacuna in item["lacunas"])
    assert item["status_resultante"] == "pendente"


def test_ciencias_biologicas_2015_preserva_escolha_explicita_sem_inventar_prazo():
    auditoria, _ = _carregar()
    item = next(
        item
        for item in auditoria["matrizes"]
        if item["curso_id"] == "ciencias_biologicas"
    )

    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])
    assert "optar pelo PPC 2015 ou pelo PPC 2023" in efeitos
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert item["status_resultante"] == "pendente"


def test_resumo_do_lote_permanece_historico_sem_congelar_estado_global_antigo():
    auditoria, vigencia = _carregar()
    assert auditoria["resumo"] == {
        "matrizes_auditadas": 3,
        "permanecem_pendentes": 3,
        "mudaram_para_nao_aplicavel": 0,
        "mudaram_para_aplicavel": 0,
        "decisoes_publicaveis": 0,
    }
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "nao_aplicaveis": 0,
        "pendentes": 42,
        "candidatas": 51,
        "ppcs_historicos_candidatos": 16,
    }
