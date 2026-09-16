import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_09_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def test_lote_09_audita_somente_biotecnologia_2018():
    auditoria, _ = _carregar()

    assert len(auditoria["auditoria"]) == 1
    item = auditoria["auditoria"][0]
    assert (item["curso_id"], item["matriz_ano"]) == ("biotecnologia", 2018)
    assert item["status_antes"] == "pendente"
    assert item["resultado"] == "candidata_preliminar"


def test_transicao_2025_preserva_opcao_explicita_pelo_ppc_2018():
    auditoria, _ = _carregar()
    item = auditoria["auditoria"][0]

    assert "ingressantes até 2022" in item["regras_transicao"]
    assert "PPC 2018" in item["regras_transicao"]
    assert "PPC 2023" in item["regras_transicao"]
    assert "71/2025" in item["entrada_em_vigor"]
    assert item["revisao_humana"]["pronto_para_mudar_status"] is True
    assert item["revisao_humana"]["decisao_publicavel"] is False


def test_lote_09_registra_fontes_oficiais_atualizadas():
    auditoria, _ = _carregar()
    fontes = auditoria["fontes"]

    assert fontes["biotecnologia_transicao_2025"]["url"].endswith(
        "comissao_ato_decisorio_71_anexo2.pdf"
    )
    assert fontes["biotecnologia_pagina_atual"]["url"] == (
        "https://prograd.ufabc.edu.br/cursos/bb"
    )
    assert "Art. 2º" in fontes["biotecnologia_ato_71_2025"]["uso"]


def test_lote_09_nao_exclui_nem_declara_suporte_publico():
    auditoria, _ = _carregar()
    item = auditoria["auditoria"][0]

    assert auditoria["politica_decisao"]["norma_geral_basta_para_excluir"] is False
    assert auditoria["politica_decisao"]["ausencia_de_prorrogacao_basta_para_excluir"] is False
    assert auditoria["resumo"]["exclusoes_definitivas"] == 0
    assert auditoria["resumo"]["decisoes_publicaveis"] == 0
    assert item["revisao_humana"]["estado"] == "pendente"


def test_lote_09_sincroniza_estado_global_sem_declarar_suporte():
    auditoria, vigencia = _carregar()
    item = auditoria["auditoria"][0]
    por_curso = {curso["curso_id"]: curso for curso in vigencia["classificacao"]}

    assert item["aplicado_no_estado_global"] is True
    assert auditoria["resumo"]["estado_global_alterado_neste_commit"] is True
    assert 2018 not in por_curso["biotecnologia"]["matrizes_pendentes_anos"]
    assert 2018 in por_curso["biotecnologia"]["matrizes_candidatas_anos"]
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "nao_aplicaveis": 0,
        "pendentes": 39,
        "candidatas": 54,
        "ppcs_historicos_candidatos": 19,
    }
