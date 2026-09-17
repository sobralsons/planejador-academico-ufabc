import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_11_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def test_lote_11_audita_somente_matematica_2017_2012_2010():
    auditoria, _ = _carregar()
    itens = {item["matriz_ano"]: item for item in auditoria["auditoria"]}

    assert set(itens) == {2017, 2012, 2010}
    assert all(item["curso_id"] == "matematica" for item in itens.values())
    assert all(item["status_antes"] == "pendente" for item in itens.values())
    assert itens[2017]["aplicado_no_estado_global"] is True
    assert itens[2012]["aplicado_no_estado_global"] is False
    assert itens[2010]["aplicado_no_estado_global"] is False


def test_matematica_2017_tem_preservacao_normativa_expressa():
    auditoria, _ = _carregar()
    item = next(item for item in auditoria["auditoria"] if item["matriz_ano"] == 2017)

    assert item["resultado"] == "candidata_preliminar"
    assert item["aplicado_no_estado_global"] is True
    assert "Resolução ConsEPE nº 210/2016" in item["ppc_substituido"]
    assert "ingressantes até 2022" in item["regras_transicao"]
    assert item["revisao_humana"]["pronto_para_mudar_status"] is True
    assert item["revisao_humana"]["decisao_publicavel"] is False


def test_matematica_2012_e_2010_nao_sao_promovidas_pela_ttmc_sozinha():
    auditoria, _ = _carregar()
    itens = {item["matriz_ano"]: item for item in auditoria["auditoria"]}

    for ano in (2012, 2010):
        item = itens[ano]
        assert item["resultado"] == "pendente"
        assert item["aplicado_no_estado_global"] is False
        assert item["revisao_humana"]["pronto_para_mudar_status"] is False
        assert "TTMC" in item["calculo_termino_validade"] or "TTMC" in item["regras_transicao"]

    assert auditoria["politica_decisao"]["ttmc_sozinha_nao_prova_vigencia"] is True
    assert auditoria["politica_decisao"]["ambiguidade_mantem_pendente"] is True


def test_lote_11_registra_fontes_oficiais_sem_confundir_lista_com_vigencia():
    auditoria, _ = _carregar()
    fontes = auditoria["fontes"]

    assert fontes["bm_ato_262_2023"]["url"].endswith(
        "ad_consepe_262_-_atualiza_pp_bacharelado_em_matemtica.pdf"
    )
    assert fontes["bm_transicao_40_2023"]["url"].endswith(
        "cg_ato-decisorio_040_anexo-2.pdf"
    )
    assert fontes["bm_pagina_atual"]["url"] == "https://prograd.ufabc.edu.br/cursos/bm"
    assert "2017, 2012 e 2010" in fontes["bm_pagina_atual"]["uso"]
    assert "não é usado isoladamente" in fontes["bm_ppc_2012"]["uso"]


def test_lote_11_sincroniza_somente_matematica_2017_no_estado_global():
    auditoria, vigencia = _carregar()
    por_curso = {curso["curso_id"]: curso for curso in vigencia["classificacao"]}
    matematica = por_curso["matematica"]

    assert auditoria["resumo"] == {
        "ppcs_auditados_lote": 3,
        "evidencias_suficientes_para_candidatura_preliminar": 1,
        "permanecem_pendentes": 2,
        "estado_global_alterado_neste_commit": True,
        "exclusoes_definitivas": 0,
        "revisao_humana": "pendente",
        "decisoes_publicaveis": 0,
    }
    assert matematica["matrizes_pendentes_anos"] == [2012, 2010]
    assert matematica["matrizes_candidatas_anos"] == [2023, 2017]
    assert matematica["matrizes_nao_aplicaveis_anos"] == []
    assert "bm_ato_262_2023" in matematica["evidencias"]
    assert "bm_transicao_40_2023" in matematica["evidencias"]
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "nao_aplicaveis": 0,
        "pendentes": 36,
        "candidatas": 57,
        "ppcs_historicos_candidatos": 22,
    }


def test_lote_11_nao_declara_suporte_publico_nem_exclusao():
    auditoria, _ = _carregar()

    assert auditoria["resumo"]["exclusoes_definitivas"] == 0
    assert auditoria["resumo"]["decisoes_publicaveis"] == 0
    assert auditoria["politica_decisao"]["norma_geral_basta_para_excluir"] is False
    assert auditoria["politica_decisao"]["revisao_humana_concluida"] is False
