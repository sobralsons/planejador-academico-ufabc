import pytest

from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    RequisitoQuantitativo,
    RestricaoContribuicao,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
    RegraCompartilhamento,
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


def _horas(id_, minimo, maximo):
    return RequisitoQuantitativo(
        id=id_, descricao=id_, integralizador=TipoIntegralizador.EXTENSAO,
        seletor=SeletorComponentes(qualquer_componente=True),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, minimo, maximo),
    )


def test_parcela_obrigatoria_nao_pode_exceder_teto_do_total():
    total = _horas("total", 100, 100)
    parte = RestricaoContribuicao(
        "parte", "Parcela", "total", SeletorComponentes(qualquer_componente=True),
        LimiteQuantitativo(UnidadeRequisito.HORAS, 120, 120),
    )
    with pytest.raises(ValueError, match="teto do total"):
        ModeloRequisitosCurriculares("curso", "2026", (total,), contribuicoes=(parte,))


def test_parcelas_podem_sobrepor_se_sem_somar_minimos_cegamente():
    total = _horas("total", 100, 100)
    partes = tuple(RestricaoContribuicao(
        id_, id_, "total", SeletorComponentes(tags=frozenset({"mesmo_conjunto"})),
        LimiteQuantitativo(UnidadeRequisito.HORAS, 100, 100),
    ) for id_ in ("parte_a", "parte_b"))
    modelo = ModeloRequisitosCurriculares("curso", "2026", (total,), contribuicoes=partes)
    assert len(modelo.contribuicoes) == 2


def test_compartilhamento_obrigatorio_nao_pode_exceder_teto_de_nenhum_lado():
    for requisitos in ((_horas("a", 100, 100), _horas("b", 0, None)),
                       (_horas("a", 0, None), _horas("b", 100, 100))):
        with pytest.raises(ValueError, match="excede teto"):
            ModeloRequisitosCurriculares(
                "curso", "2026", requisitos,
                compartilhamentos=(RegraCompartilhamento(
                    "a", "b", UnidadeRequisito.HORAS, 120, 120,
                ),),
            )


@pytest.mark.parametrize("valor", [True, 1.5, float("nan"), float("inf")])
def test_compartilhamento_rejeita_minimo_invalido(valor):
    with pytest.raises(ValueError, match="inteiro"):
        RegraCompartilhamento("a", "b", UnidadeRequisito.HORAS, 200, valor)
