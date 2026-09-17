import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDITORIA = BASE / "dados" / "auditoria_aplicabilidade_lote_08_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return auditoria, vigencia


def _por_chave(auditoria):
    return {
        (item["curso_id"], item["matriz_ano"]): item
        for item in auditoria["auditoria"]
    }


def test_lote_08_audita_exatamente_tres_ppcs_e_so_promove_dois():
    auditoria, _ = _carregar()
    por_chave = _por_chave(auditoria)

    assert set(por_chave) == {
        ("ciencias_biologicas", 2015),
        ("fisica", 2015),
        ("biotecnologia", 2018),
    }
    assert por_chave[("ciencias_biologicas", 2015)]["resultado"] == "candidata_preliminar"
    assert por_chave[("fisica", 2015)]["resultado"] == "candidata_preliminar"
    assert por_chave[("biotecnologia", 2018)]["resultado"] == "pendente"
    assert auditoria["resumo"] == {
        "ppcs_auditados_lote": 3,
        "promovidos_a_candidata_preliminar": 2,
        "mantidos_pendentes": 1,
        "exclusoes_definitivas": 0,
        "revisao_humana": "pendente",
        "decisoes_publicaveis": 0,
    }


def test_lote_08_mantem_contrato_de_decisao_e_revisao_humana():
    auditoria, _ = _carregar()
    obrigatorios = set(auditoria["campos_obrigatorios_decisao"])

    for item in auditoria["auditoria"]:
        assert obrigatorios <= set(item)
        assert item["calculo_termino_validade"]
        assert item["fontes"]
        assert item["revisao_humana"]["estado"] == "pendente"
        assert item["revisao_humana"]["decisao_publicavel"] is False

    assert auditoria["politica_decisao"]["norma_geral_basta_para_excluir"] is False
    assert auditoria["politica_decisao"]["ausencia_de_prorrogacao_basta_para_excluir"] is False
    assert auditoria["politica_decisao"]["lista_colacao_sozinha_comprova_estudante_ativo_na_data_corte"] is False


def test_ciencias_biologicas_2015_tem_regra_especifica_de_opcao():
    auditoria, _ = _carregar()
    item = _por_chave(auditoria)[("ciencias_biologicas", 2015)]

    assert "PPC-BCB/2015" in item["regras_transicao"]
    assert "PPC-BCB/2023" in item["regras_transicao"]
    assert "ingressantes antes de 2023" in item["regras_transicao"]
    assert item["revisao_humana"]["pronto_para_mudar_status"] is True


def test_fisica_2015_usa_transicao_2026_sem_promover_2009_por_inferencia():
    auditoria, vigencia = _carregar()
    item = _por_chave(auditoria)[("fisica", 2015)]
    por_curso = {curso["curso_id"]: curso for curso in vigencia["classificacao"]}

    assert "81/2026" in item["regras_transicao"]
    assert "2009" in item["possiveis_excecoes"]
    assert 2015 in por_curso["fisica"]["matrizes_candidatas_anos"]
    assert 2009 in por_curso["fisica"]["matrizes_pendentes_anos"]


def test_biotecnologia_2018_preserva_decisao_historica_do_lote_08():
    auditoria, vigencia = _carregar()
    item = _por_chave(auditoria)[("biotecnologia", 2018)]
    por_curso = {curso["curso_id"]: curso for curso in vigencia["classificacao"]}

    assert "1º quadrimestre de 2026" in item["calculo_termino_validade"]
    assert "71/2025" in item["calculo_termino_validade"]
    assert item["revisao_humana"]["pronto_para_mudar_status"] is False
    assert item["resultado"] == "pendente"
    # O lote 8 permanece histórico; a promoção só ocorreu no lote 9, após
    # verificação integral do Anexo II atualizado pelo Ato CG nº 71/2025.
    assert 2018 not in por_curso["biotecnologia"]["matrizes_pendentes_anos"]
    assert 2018 in por_curso["biotecnologia"]["matrizes_candidatas_anos"]


def test_lote_08_nao_reproduz_dados_pessoais_da_fonte_de_colacao():
    auditoria, _ = _carregar()
    texto = json.dumps(auditoria, ensure_ascii=False).lower()

    assert auditoria["politica_decisao"]["dados_pessoais_da_fonte_operacional_sao_reproduzidos"] is False
    for chave in ("ra", "discente_id", "nome_discente", "cpf", "email_discente"):
        assert f'"{chave}"' not in texto


def test_vigencia_central_reflete_promocoes_posteriores_sem_reescrever_lote_08():
    _, vigencia = _carregar()
    por_curso = {item["curso_id"]: item for item in vigencia["classificacao"]}

    assert 2015 in por_curso["ciencias_biologicas"]["matrizes_candidatas_anos"]
    assert 2010 in por_curso["ciencias_biologicas"]["matrizes_pendentes_anos"]
    assert 2015 in por_curso["fisica"]["matrizes_candidatas_anos"]
    assert 2009 in por_curso["fisica"]["matrizes_pendentes_anos"]
    assert 2018 in por_curso["biotecnologia"]["matrizes_candidatas_anos"]
    assert vigencia["resumo"] == {
        "ppcs_total": 93,
        "candidatas": 56,
        "nao_aplicaveis": 0,
        "pendentes": 37,
        "ppcs_historicos_candidatos": 21,
    }


def test_lote_08_nao_declara_suporte_academico():
    auditoria, _ = _carregar()
    texto = json.dumps(auditoria, ensure_ascii=False).lower()

    assert "sem declarar vigência normativa definitiva, suporte acadêmico ou exclusão" in auditoria["escopo"]
    assert "decisao_publicavel" in texto
    assert all(
        item["revisao_humana"]["decisao_publicavel"] is False
        for item in auditoria["auditoria"]
    )
