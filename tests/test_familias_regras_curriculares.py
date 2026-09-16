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

    assert len(esperadas) == 48
    assert len(mapeadas) == 48
    assert mapeadas == esperadas
    pendentes = {
        (item["curso_id"], ano)
        for item in vigencia["classificacao"]
        for ano in item["matrizes_pendentes_anos"]
    }
    fila = [(c, a) for f in familias["familias"] for c, a in f["matrizes_pendentes"]]
    assert len(fila) == len(set(fila)) == 45
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


def test_evidencias_representativas_sao_oficiais_da_ufabc():
    familias, _ = _carregar()
    evidencias = familias["evidencias_representativas"]

    assert evidencias
    for evidencia in evidencias:
        assert evidencia["fonte"].startswith("https://")
        assert "ufabc.edu.br" in evidencia["fonte"]
        assert evidencia["evidencia"].strip()
