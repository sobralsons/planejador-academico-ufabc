import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_10_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def test_lote_10_audita_somente_bcc_2015_e_2010():
    auditoria, _ = _carregar()

    itens = {
        (item["curso_id"], item["matriz_ano"]): item
        for item in auditoria["auditoria"]
    }
    assert set(itens) == {
        ("ciencia_computacao", 2015),
        ("ciencia_computacao", 2010),
    }
    for item in itens.values():
        assert item["status_antes"] == "pendente"
        assert item["resultado"] == "candidata_preliminar"
        assert item["aplicado_no_estado_global"] is False


def test_transicao_2023_preserva_matriz_vigente_no_ano_de_ingresso():
    auditoria, _ = _carregar()

    for item in auditoria["auditoria"]:
        assert "anteriormente a 2023" in item["regras_transicao"]
        assert "vigente no seu ano de ingresso" in item["regras_transicao"]
        assert item["revisao_humana"]["pronto_para_mudar_status"] is True
        assert item["revisao_humana"]["decisao_publicavel"] is False

    por_ano = {item["matriz_ano"]: item for item in auditoria["auditoria"]}
    assert "2010, 2015, 2017 e 2023" in por_ano[2010]["regras_transicao"]


def test_lote_10_registra_fontes_oficiais_atuais():
    auditoria, _ = _carregar()
    fontes = auditoria["fontes"]

    assert fontes["bcc_transicao_2023"]["url"].endswith(
        "cg_ato-decisorio_044_anexo-02.pdf"
    )
    assert fontes["bcc_pagina_atual"]["url"] == (
        "https://prograd.ufabc.edu.br/cursos/bcc"
    )
    assert "2010-2015-2017" in fontes["bcc_pagina_atual"]["uso"]
    assert "vigente no ano de ingresso" in fontes["bcc_transicao_2023"]["uso"]


def test_lote_10_nao_exclui_nem_declara_suporte_publico():
    auditoria, _ = _carregar()

    assert auditoria["politica_decisao"]["norma_geral_basta_para_excluir"] is False
    assert (
        auditoria["politica_decisao"]
        ["revogacao_formal_do_ppc_basta_para_excluir_estudantes_em_transicao"]
        is False
    )
    assert auditoria["politica_decisao"]["ausencia_de_prorrogacao_basta_para_excluir"] is False
    assert auditoria["resumo"]["exclusoes_definitivas"] == 0
    assert auditoria["resumo"]["decisoes_publicaveis"] == 0
    assert auditoria["resumo"]["revisao_humana"] == "pendente"


def test_lote_10_preserva_estado_global_antes_do_ci():
    auditoria, vigencia = _carregar()
    por_curso = {curso["curso_id"]: curso for curso in vigencia["classificacao"]}
    bcc = por_curso["ciencia_computacao"]

    assert auditoria["resumo"]["estado_global_alterado_neste_commit"] is False
    assert {2015, 2010} <= set(bcc["matrizes_pendentes_anos"])
    assert not ({2015, 2010} & set(bcc["matrizes_candidatas_anos"]))
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "nao_aplicaveis": 0,
        "pendentes": 39,
        "candidatas": 54,
        "ppcs_historicos_candidatos": 19,
    }
