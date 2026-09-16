import pytest

from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    RequisitoQuantitativo,
    RestricaoContribuicao,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


def test_contribuicao_participa_dos_ids_e_nao_pode_colidir_com_requisito():
    total = RequisitoQuantitativo(
        id="extensao_total",
        descricao="Extensão total",
        integralizador=TipoIntegralizador.EXTENSAO,
        seletor=SeletorComponentes(tags=frozenset({"extensao"})),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, 100),
    )
    parte = RestricaoContribuicao(
        id="extensao_estagio",
        descricao="Parcela extensionista de estágio",
        requisito_total="extensao_total",
        seletor=SeletorComponentes(tags=frozenset({"estagio_extensionista"})),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, 40, 40),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id="curso",
        matriz_id="2026",
        requisitos=(total,),
        contribuicoes=(parte,),
    )
    assert "extensao_estagio" in modelo.ids_regras

    requisito_colidente = RequisitoQuantitativo(
        id="extensao_estagio",
        descricao="ID colidente",
        integralizador=TipoIntegralizador.EXTENSAO,
        seletor=SeletorComponentes(tags=frozenset({"outra"})),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, 1),
    )
    with pytest.raises(ValueError, match="IDs de regras curriculares"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2026",
            requisitos=(total, requisito_colidente),
            contribuicoes=(parte,),
        )
