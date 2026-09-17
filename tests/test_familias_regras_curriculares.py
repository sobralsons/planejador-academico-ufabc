import json
from pathlib import Path

# Estes testes protegem o contrato de cobertura antes de alterar o modelo curricular.
BASE = Path(__file__).resolve().parents[1]
FAMILIAS = BASE / "dados" / "familias_regras_curriculares_2026-09-16.json"
VIGENCIA = BASE / "dados" / "vigencia_ppcs_2026-09-16.json"


def _carregar():
    familias = json.loads(FAMILIAS.read_text(encoding="utf-8"))
    vigencia = json.loads(VIGENCIA.read_text(encoding="utf-8"))
    return familias, vigencia


def test_familias_preservam_candidatas_e_incluem_todas_as_pendentes():
    familias, vigencia = _carregar()

    esperadas = {
        (item["curso_id"], ano)
        for item in vigencia["classificacao"]
        for ano in item["matrizes_candidatas_anos"]
    }
    mapeadas = {
        (curso_id, ano)
        for familia in familias["familias"]
        for curso_id, ano in familia["matrizes"]
    }

    # Lote 10: BCC 2010 e 2015 foram promovidas na base do PR #4.
    assert len(esperadas) == 56
    assert len(mapeadas) == 56
    assert mapeadas == esperadas
    pendentes = {
        (item["curso_id"], ano)
        for item in vigencia["classificacao"]
        for ano in item["matrizes_pendentes_anos"]
    }
    fila = [(c, a) for f in familias["familias"] for c, a in f["matrizes_pendentes"]]
    assert len(fila) == len(set(fila)) == 37
    assert set(fila) == pendentes
    assert not (set(fila) & mapeadas)
    assert len(set(fila) | mapeadas) == 93
    assert familias["schema_version"] == 2


def test_matriz_aplicavel_pertence_a_uma_unica_familia():
    familias, _ = _carregar()
    itens = [
        (curso_id, ano)
        for familia in familias["familias"]
        for curso_id, ano in familia["matrizes"]
    ]
    assert len(itens) == len(set(itens))


def test_familias_referenciam_apenas_capacidades_declaradas():
    familias, _ = _carregar()
    capacidades = set(familias["capacidades_modelo"])

    for familia in familias["familias"]:
        assert familia["capacidades_criticas"]
        assert set(familia["capacidades_criticas"]) <= capacidades


def test_mapa_expoe_lacunas_que_o_modelo_atual_nao_deve_ocultar():
    familias, _ = _carregar()
    capacidades = familias["capacidades_modelo"]

    assert capacidades["categorias_creditos"]["estado_atual"] == "suportado_basico"
    assert capacidades["grupos_escolha"]["estado_atual"] == "ausente"
    assert capacidades["requisitos_condicionais"]["estado_atual"] == "ausente"
    assert capacidades["formacao_docente"]["estado_atual"] == "ausente"
    assert capacidades["sobreposicao_cargas"]["estado_atual"] == "ausente"
    assert capacidades["reuso_curso_base"]["estado_atual"] == "ausente_explicito"


def test_familias_de_maior_risco_preservam_requisitos_distintos():
    familias, _ = _carregar()
    por_id = {familia["id"]: familia for familia in familias["familias"]}

    engenharias = por_id["engenharias"]
    assert len(engenharias["matrizes"]) == 16
    assert "estagio_horas" in engenharias["capacidades_criticas"]
    assert "tcc_etapas" in engenharias["capacidades_criticas"]

    licenciaturas = por_id["licenciaturas_formacao_especifica"]
    assert "formacao_docente" in licenciaturas["capacidades_criticas"]
    assert "estagio_horas" in licenciaturas["capacidades_criticas"]

    especiais = por_id["novas_licenciaturas_ingresso_e_oferta_especial"]
    assert "oferta_especial" in especiais["capacidades_criticas"]
    assert "requisitos_condicionais" in especiais["capacidades_criticas"]


def test_neuro_2021_migra_para_familia_candidata_sem_ocultar_pendencias():
    familias, _ = _carregar()
    por_id = {familia["id"]: familia for familia in familias["familias"]}
    familia = por_id["bacharelados_cientificos_tecnologicos"]

    assert ["neurociencia", 2021] in familia["matrizes"]
    assert ["neurociencia", 2021] not in familia["matrizes_pendentes"]
    assert ["neurociencia", 2015] in familia["matrizes_pendentes"]
    assert ["neurociencia", 2010] in familia["matrizes_pendentes"]


def test_quimica_2015_migra_para_familia_candidata_sem_ocultar_2010():
    familias, _ = _carregar()
    por_id = {familia["id"]: familia for familia in familias["familias"]}
    familia = por_id["bacharelados_cientificos_tecnologicos"]

    assert ["quimica", 2015] in familia["matrizes"]
    assert ["quimica", 2015] not in familia["matrizes_pendentes"]
    assert ["quimica", 2010] in familia["matrizes_pendentes"]


def test_lote_07_migra_bct_e_bch_para_familia_candidata_sem_ocultar_bch_2010():
    familias, _ = _carregar()
    por_id = {familia["id"]: familia for familia in familias["familias"]}
    familia = por_id["interdisciplinares_bacharelado"]

    promovidas = [
        ["bct", 2009],
        ["bct", 2015],
        ["bch", 2015],
    ]
    for matriz in promovidas:
        assert matriz in familia["matrizes"]
        assert matriz not in familia["matrizes_pendentes"]

    assert ["bch", 2010] in familia["matrizes_pendentes"]


def test_lotes_08_e_09_atualizam_familia_cientifica_sem_inferir_outras_matrizes():
    familias, _ = _carregar()
    por_id = {familia["id"]: familia for familia in familias["familias"]}
    familia = por_id["bacharelados_cientificos_tecnologicos"]

    promovidas = [
        ["ciencias_biologicas", 2015],
        ["fisica", 2015],
        ["biotecnologia", 2018],
    ]
    for matriz in promovidas:
        assert matriz in familia["matrizes"]
        assert matriz not in familia["matrizes_pendentes"]

    assert ["ciencias_biologicas", 2010] in familia["matrizes_pendentes"]
    assert ["fisica", 2009] in familia["matrizes_pendentes"]


def test_lote_10_sincroniza_bcc_sem_promover_matematica_do_lote_11():
    familias, vigencia = _carregar()
    familia = next(f for f in familias["familias"]
                   if f["id"] == "bacharelados_cientificos_tecnologicos")
    for ano in (2010, 2015):
        assert ["ciencia_computacao", ano] in familia["matrizes"]
        assert ["ciencia_computacao", ano] not in familia["matrizes_pendentes"]
    # A sincronização de Matemática 2017 é uma etapa separada, não implícita.
    for ano in (2010, 2012, 2017):
        assert ["matematica", ano] in familia["matrizes_pendentes"]
    assert vigencia["revisao_humana"] == "pendente"
    assert all(not item["matrizes_nao_aplicaveis_anos"]
               for item in vigencia["classificacao"])


def test_evidencias_representativas_sao_oficiais_da_ufabc():
    familias, _ = _carregar()
    evidencias = familias["evidencias_representativas"]

    assert evidencias
    for evidencia in evidencias:
        assert evidencia["fonte"].startswith("https://")
        assert "ufabc.edu.br" in evidencia["fonte"]
        assert evidencia["evidencia"].strip()
