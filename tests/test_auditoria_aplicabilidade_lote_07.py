import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_07_2026-09-16.json"
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


def _chaves_recursivas(valor):
    if isinstance(valor, dict):
        for chave, item in valor.items():
            yield chave.lower()
            yield from _chaves_recursivas(item)
    elif isinstance(valor, list):
        for item in valor:
            yield from _chaves_recursivas(item)


def test_lote_07_promove_exatamente_bct_2009_bct_2015_e_bch_2015():
    auditoria, vigencia = _carregar()
    auditadas = _por_matriz(auditoria)

    assert set(auditadas) == {
        ("bct", 2009),
        ("bct", 2015),
        ("bch", 2015),
    }
    assert all(item["status_antes"] == "pendente" for item in auditadas.values())
    assert all(
        item["status_resultante"] == "candidata_preliminar"
        for item in auditadas.values()
    )
    assert all(item["decisao_publicavel"] is False for item in auditadas.values())

    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}
    assert por_curso["bct"]["matrizes_candidatas_anos"] == [2023, 2015, 2009]
    assert por_curso["bct"]["matrizes_pendentes_anos"] == []
    assert 2015 in por_curso["bch"]["matrizes_candidatas_anos"]
    assert 2015 not in por_curso["bch"]["matrizes_pendentes_anos"]
    assert 2010 in por_curso["bch"]["matrizes_pendentes_anos"]


def test_contrato_do_lote_07_preserva_incerteza_normativa_e_revisao_humana():
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
        assert item["revisao_humana"]["pronto_para_mudar_status"] is True
        assert item["decisao_publicavel"] is False


def test_colacao_2026_e_evidencia_operacional_nao_certificacao_final():
    auditoria, _ = _carregar()
    fonte = auditoria["fontes_oficiais"]["colacao_30jun2026"]

    assert "Projeto Pedagógico Considerado" in fonte["secao"]
    assert "BCT 2009" in fonte["interpretacao"]
    assert "BCT 2015" in fonte["interpretacao"]
    assert "BCH 2015" in fonte["interpretacao"]
    assert auditoria["politica_decisao"][
        "lista_de_solicitantes_nao_prova_colacao_efetivada"
    ] is True
    assert auditoria["politica_decisao"][
        "evidencia_operacional_atual_nao_substitui_contrato_temporal"
    ] is True


def test_lote_07_nao_reproduz_identificadores_discentes_da_fonte():
    auditoria, _ = _carregar()
    chaves = set(_chaves_recursivas(auditoria))
    texto = AUDITORIA.read_text(encoding="utf-8").lower()

    assert auditoria["politica_decisao"]["dados_pessoais_reproduzidos"] is False
    assert "ra" not in chaves
    assert "discente_id" not in chaves
    assert "identificador_discente" not in chaves
    assert "nenhum identificador discente" in texto or "sem reproduzir identificadores" in texto


def test_bct_2009_nao_transforma_matriz_sugerida_em_prazo_normativo():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("bct", 2009)]

    assert item["tempo_integralizacao"]["valor"] == 9
    assert item["tempo_integralizacao"]["unidade"] == "quadrimestres"
    assert "sem_equivalencia_normativa_confirmada" in item["tempo_integralizacao"]["estado"]
    assert item["calculo_termino_validade"]["resultado_teorico"] is None
    assert "BCT 2009" in item["calculo_termino_validade"]["motivo"]


def test_bct_2015_preserva_rotulos_institucionais_sem_criar_novos_ppcs():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("bct", 2015)]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert "BCT 2015-2016" in efeitos
    assert "BCT 2015-2017" in efeitos
    assert "sem multiplicar versões por rótulo de matriz" in efeitos
    assert auditoria["politica_decisao"][
        "nomenclatura_institucional_de_matriz_nao_cria_novo_ppc"
    ] is True


def test_bch_2015_combina_preservacao_de_coorte_com_uso_operacional_atual():
    auditoria, _ = _carregar()
    item = _por_matriz(auditoria)[("bch", 2015)]
    efeitos = " ".join(regra["efeito_relevante"] for regra in item["regras_transicao"])

    assert item["entrada_em_vigor"]["marco"] == "2020-04-01"
    assert "Ingressantes até 2019" in efeitos
    assert "BCH 2015" in efeitos
    assert item["calculo_termino_validade"]["resultado_teorico"] is None


def test_lote_07_atualiza_resumo_global_sem_criar_exclusao():
    auditoria, vigencia = _carregar()

    assert auditoria["resumo"] == {
        "matrizes_auditadas": 3,
        "permanecem_pendentes": 0,
        "mudaram_para_nao_aplicavel": 0,
        "mudaram_para_candidata_preliminar": 3,
        "decisoes_publicaveis": 0,
    }
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "nao_aplicaveis": 0,
        "pendentes": 39,
        "candidatas": 54,
        "ppcs_historicos_candidatos": 19,
    }


def test_lote_07_nao_declara_suporte_academico():
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
