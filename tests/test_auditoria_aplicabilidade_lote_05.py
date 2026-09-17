import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_05_2026-09-16.json"
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


def test_lote_05_audita_tres_matrizes_e_promove_apenas_quimica_2015():
    auditoria, vigencia = _carregar()
    auditadas = _por_matriz(auditoria)

    assert set(auditadas) == {
        ("quimica", 2015),
        ("fisica", 2015),
        ("relacoes_internacionais", 2015),
    }
    assert all(item["status_antes"] == "pendente" for item in auditadas.values())
    assert auditadas[("quimica", 2015)]["status_resultante"] == "candidata_preliminar"
    assert auditadas[("fisica", 2015)]["status_resultante"] == "pendente"
    assert auditadas[("relacoes_internacionais", 2015)]["status_resultante"] == "pendente"
    assert all(item["decisao_publicavel"] is False for item in auditadas.values())

    # O lote 5 preserva sua decisão histórica. Física 2015 só foi promovida
    # posteriormente, no lote 8, após documento de transição atualizado em 2026.
    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}
    assert 2015 in por_curso["quimica"]["matrizes_candidatas_anos"]
    assert 2010 in por_curso["quimica"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["fisica"]["matrizes_candidatas_anos"]
    assert 2015 not in por_curso["fisica"]["matrizes_pendentes_anos"]
    assert 2009 in por_curso["fisica"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["relacoes_internacionais"]["matrizes_pendentes_anos"]


def test_contrato_do_lote_05_preserva_revisao_humana_e_nao_publica():
    auditoria, _ = _carregar()
    obrigatorios = set(auditoria["campos_obrigatorios_por_decisao"])
    auditadas = _por_matriz(auditoria)

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

    assert auditadas[("quimica", 2015)]["revisao_humana"]["pronto_para_mudar_status"] is True
    assert auditadas[("fisica", 2015)]["revisao_humana"]["pronto_para_mudar_status"] is False
    assert auditadas[("relacoes_internacionais", 2015)]["revisao_humana"]["pronto_para_mudar_status"] is False


def test_fontes_do_lote_05_sao_oficiais_e_identificam_secao():
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


def test_quimica_2015_exige_evidencia_operacional_explicita_alem_da_transicao():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("quimica", 2015)]
    fontes = auditoria["fontes_oficiais"]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert "Ingressantes até 2022" in efeitos
    assert "obrigatória no PPC 2015" in efeitos
    assert "84h" in efeitos
    assert "obrigatória no PPC 2015" in fontes["bq_justificativa_2025"]["interpretacao"]
    assert "84h" in fontes["bq_servico_atual"]["interpretacao"]
    assert item["calculo_termino_validade"]["resultado_teorico"].startswith("2025")
    assert item["status_resultante"] == "candidata_preliminar"
    assert item["decisao_publicavel"] is False


def test_fisica_2015_nao_promove_listagem_e_ttmc_2026_a_prova_de_vigencia():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("fisica", 2015)]
    motivo = item["calculo_termino_validade"]["motivo"]

    assert item["tempo_integralizacao"]["valor"] == 4
    assert item["tempo_integralizacao"]["unidade"] == "anos"
    assert "Ato CG nº 81/2026" in motivo
    assert "não afirma que o PPC 2015 permaneça ativo" in motivo
    assert item["status_resultante"] == "pendente"


def test_bri_2015_preserva_efeito_da_retificacao_sem_inventar_revogacao():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("relacoes_internacionais", 2015)]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])
    motivo = item["calculo_termino_validade"]["motivo"]

    assert item["entrada_em_vigor"]["estado"] == "comprovada_com_retificacao_relevante"
    assert "suprimida a cláusula" in efeitos
    assert "ingressantes até 2022" in efeitos
    assert "removeu expressamente" in motivo
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert item["status_resultante"] == "pendente"


def test_lote_05_preserva_promocao_sem_congelar_resumo_global_posterior():
    auditoria, vigencia = _carregar()

    assert auditoria["resumo"] == {
        "matrizes_auditadas": 3,
        "permanecem_pendentes": 2,
        "mudaram_para_nao_aplicavel": 0,
        "mudaram_para_candidata_preliminar": 1,
        "decisoes_publicaveis": 0,
    }
    resumo_global = vigencia["resumo"]
    assert resumo_global["ppcs_total"] == 93
    assert resumo_global["nao_aplicaveis"] == 0
    assert resumo_global["candidatas"] + resumo_global["pendentes"] == 93


def test_lote_05_nao_declara_suporte_academico():
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
