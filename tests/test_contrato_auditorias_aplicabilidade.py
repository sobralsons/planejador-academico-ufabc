"""Contrato documental; não comprova vigência nem integralização acadêmica."""

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest


BASE = Path(__file__).resolve().parents[1]
LOTES = sorted((BASE / "dados").glob("auditoria_aplicabilidade_lote_*.json"))
CAMPOS_DECISAO = (
    "ppc_substituido", "ppc_substituto", "entrada_em_vigor",
    "tempo_integralizacao", "calculo_termino_validade", "regras_transicao",
    "possiveis_excecoes",
)


@pytest.mark.parametrize("arquivo", LOTES, ids=lambda p: p.stem)
def test_lote_obedece_formato_declarado_e_resolve_referencias(arquivo):
    lote = json.loads(arquivo.read_text(encoding="utf-8"))
    versao = lote["schema_version"]
    assert type(versao) is int and versao in (1, 2)
    if versao == 1:
        colecao, fontes_key, data_key = "matrizes", "fontes_oficiais", "analisado_em"
        tipos = (dict, dict, dict, dict, dict, list, list)
        status_key = "status_resultante"
        assert "auditoria" not in lote
    else:
        colecao, fontes_key, data_key = "auditoria", "fontes", "avaliado_em"
        tipos = (str,) * len(CAMPOS_DECISAO)
        status_key = "resultado"
        assert "matrizes" not in lote

    assert isinstance(lote[data_key], str) and lote[data_key].strip()
    fontes = lote[fontes_key]
    assert isinstance(fontes, dict) and fontes
    for fonte in fontes.values():
        url = urlparse(fonte["url"])
        assert url.scheme == "https"
        assert url.hostname == "ufabc.edu.br" or (
            url.hostname and url.hostname.endswith(".ufabc.edu.br")
        )
        assert fonte["referencia"].strip()

    itens = lote[colecao]
    assert isinstance(itens, list) and itens
    chaves = [(item["curso_id"], item["matriz_ano"]) for item in itens]
    assert len(chaves) == len(set(chaves))
    for item in itens:
        assert item["curso_id"].strip()
        assert type(item["matriz_ano"]) is int
        for campo, tipo in zip(CAMPOS_DECISAO, tipos):
            assert isinstance(item[campo], tipo) and item[campo]
        assert item[status_key] in ("pendente", "candidata_preliminar")
        assert isinstance(item["fontes"], list) and item["fontes"]
        assert set(item["fontes"]) <= fontes.keys()
        assert item["revisao_humana"]["estado"] == "pendente"
        decisao = item if versao == 1 else item["revisao_humana"]
        assert decisao["decisao_publicavel"] is False
