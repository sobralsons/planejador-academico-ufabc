import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_03_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def test_lote_03_audita_tres_familias_sem_promover_status():
    auditoria, vigencia = _carregar()
    auditadas = {
        (item["curso_id"], item["matriz_ano"]): item
        for item in auditoria["matrizes"]
    }

    assert set(auditadas) == {
        ("ciencias_economicas", 2017),
        ("matematica", 2017),
        ("lch", 2019),
    }
    assert all(item["status_antes"] == "pendente" for item in auditadas.values())
    assert all(item["status_resultante"] == "pendente" for item in auditadas.values())
    assert all(item["decisao_publicavel"] is False for item in auditadas.values())

    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}
    assert 2017 in por_curso["ciencias_economicas"]["matrizes_pendentes_anos"]
    assert 2017 in por_curso["matematica"]["matrizes_pendentes_anos"]
    assert 2019 in por_curso["lch"]["matrizes_pendentes_anos"]


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
        assert item["calculo_termino_validade"]["resultado_teorico"] is None
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


def test_bce_2017_registra_cadeia_intermediaria_sem_usar_ttmc_como_prova_de_vigencia():
    auditoria, _ = _carregar()
    item = next(
        item
        for item in auditoria["matrizes"]
        if item["curso_id"] == "ciencias_economicas"
    )
    cadeia = item["cadeia_substituicao"]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert [passo["ano"] for passo in cadeia] == [2021, 2022]
    assert item["ppc_substituto"]["ano"] == 2021
    assert "Revoga e substitui diretamente" in cadeia[0]["efeito"]
    assert "Ingressantes até 2020" in efeitos
    assert "não é usada isoladamente" in efeitos
    assert item["status_resultante"] == "pendente"


def test_bm_2017_preserva_opcao_explicita_sem_exclusao_por_prazo_generico():
    auditoria, _ = _carregar()
    item = next(
        item
        for item in auditoria["matrizes"]
        if item["curso_id"] == "matematica"
    )
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["tempo_integralizacao"]["valor"] == 4
    assert item["tempo_integralizacao"]["unidade"] == "anos"
    assert "Ingressantes até 2022" in efeitos
    assert "não optam" in efeitos
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert item["status_resultante"] == "pendente"


def test_lch_2019_mantem_diferenca_de_coorte_explicita_sem_inventar_data_terminal():
    auditoria, _ = _carregar()
    item = next(
        item
        for item in auditoria["matrizes"]
        if item["curso_id"] == "lch"
    )
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])
    motivo = item["calculo_termino_validade"]["motivo"]

    assert item["tempo_integralizacao"]["valor"] == 12
    assert item["tempo_integralizacao"]["unidade"] == "quadrimestres"
    assert "Ingressantes até 2022" in efeitos
    assert "anteriores a 2022" in efeitos
    assert "diferença de coorte" in motivo
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert item["status_resultante"] == "pendente"


def test_lote_03_preserva_suas_decisoes_sem_congelar_resumo_global_antigo():
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
        "pendentes": 40,
        "candidatas": 53,
        "ppcs_historicos_candidatos": 18,
    }
    assert all(
        "suportada" not in item.get("status_resultante", "")
        for item in auditoria["matrizes"]
    )
