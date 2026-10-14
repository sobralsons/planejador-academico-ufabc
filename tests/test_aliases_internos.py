import json

import pytest

from planejador.curriculo import carregar_equivalencias
from planejador.evidencias_historico import converter_historico_consolidado_em_evidencias
from planejador.historico import consolidar_historico
from planejador.modelos import RegistroHistorico
from planejador.requisitos_curriculares import UnidadeRequisito


@pytest.mark.parametrize("codigos", [("INTERNO",), ("OFICIAL",), ("INTERNO", "OFICIAL"), ("OFICIAL", "INTERNO")])
def test_alias_interno_e_codigo_oficial_sao_uma_unica_identidade(tmp_path, codigos):
    path = tmp_path / "equivalencias.json"
    path.write_text(json.dumps({"aliases_internos": {"INTERNO": "OFICIAL"}}), encoding="utf-8")
    simples, compostas = carregar_equivalencias(path)
    registros = [RegistroHistorico("2026.1", "OB", c, "Componente Sintético", 12, 144, 0, "", "A", "APR", "") for c in codigos]
    situacao = consolidar_historico(registros, simples, compostas)
    assert situacao.conclusoes_confiaveis() == {"OFICIAL"}
    assert set(situacao.tentativas) == {"OFICIAL"}
    assert tuple(r.codigo for r in registros) == codigos
    conversao = converter_historico_consolidado_em_evidencias(situacao)
    assert sum(e.quantidade(UnidadeRequisito.CREDITOS) for e in conversao.conjunto.evidencias) == 12


def test_projecao_personalizada_reconhece_alias_interno(tmp_path):
    path = tmp_path / "equivalencias.json"
    path.write_text(json.dumps({"aliases_internos": {"INTERNO": "OFICIAL"}}), encoding="utf-8")
    simples, compostas = carregar_equivalencias(path)
    registros = [RegistroHistorico("2026.1", "OB", "INTERNO", "Componente Sintético", 12, 144, 0, "", "", "MATR", "")]
    situacao = consolidar_historico(registros, simples, compostas)
    assert situacao.codigos_projetados("nenhuma") == set()
    assert situacao.codigos_projetados("personalizada", ("INTERNO",)) == {"OFICIAL"}


@pytest.mark.parametrize("aliases", [{"A": "A"}, {"A": "B", "B": "A"}, {"A": "B", "B": "C"}])
def test_aliases_internos_rejeitam_ciclos_e_encadeamento(tmp_path, aliases):
    path = tmp_path / "equivalencias.json"
    path.write_text(json.dumps({"aliases_internos": aliases}), encoding="utf-8")
    with pytest.raises(ValueError, match="Alias interno"):
        carregar_equivalencias(path)


@pytest.mark.parametrize("destino", ["OFICIAL", "OUTRO"])
def test_alias_nao_pode_ser_origem_de_equivalencia_academica(tmp_path, destino):
    path = tmp_path / "equivalencias.json"
    path.write_text(json.dumps({"aliases_internos": {"INTERNO": "OFICIAL"}, "equivalencias_academicas": {"INTERNO": destino}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Alias interno conflitante"):
        carregar_equivalencias(path)


def test_alias_com_quantidades_divergentes_preserva_indeterminacao(tmp_path):
    path = tmp_path / "equivalencias.json"
    path.write_text(json.dumps({"aliases_internos": {"INTERNO": "OFICIAL"}}), encoding="utf-8")
    simples, compostas = carregar_equivalencias(path)
    registros = [RegistroHistorico("2026.1", "OB", c, "Componente Sintético", cr, cr * 12, 0, "", "A", "APR", "") for c, cr in (("INTERNO", 11), ("OFICIAL", 12))]
    situacao = consolidar_historico(registros, simples, compostas)
    conversao = converter_historico_consolidado_em_evidencias(situacao, unidades_completas=frozenset({UnidadeRequisito.CREDITOS}))
    assert UnidadeRequisito.CREDITOS not in conversao.conjunto.unidades_completas
    assert sum(e.quantidade(UnidadeRequisito.CREDITOS) for e in conversao.conjunto.evidencias) == 0
    assert conversao.conflitos


def test_convalidacoes_conflitantes_apos_normalizar_alias_sao_rejeitadas(tmp_path):
    path = tmp_path / "equivalencias.json"
    path.write_text(json.dumps({"aliases_internos": {"INTERNO": "OFICIAL"}}), encoding="utf-8")
    simples, compostas = carregar_equivalencias(path)
    with pytest.raises(ValueError, match="Convalidações conflitantes"):
        consolidar_historico([], simples, compostas, {"INTERNO": "A", "OFICIAL": "B"})


@pytest.mark.parametrize("regras", [
    {"equivalencias_academicas": {"ANTIGO": "INTERNO"}},
    {"equivalencias_compostas": [{"origens": ["INTERNO", "B"], "destino": "C"}]},
    {"equivalencias_compostas": [{"origens": ["A", "B"], "destino": "INTERNO"}]},
])
def test_regras_academicas_devem_usar_codigos_canonicos(tmp_path, regras):
    path = tmp_path / "equivalencias.json"
    path.write_text(json.dumps({**regras, "aliases_internos": {"INTERNO": "OFICIAL"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Alias interno"):
        carregar_equivalencias(path)
