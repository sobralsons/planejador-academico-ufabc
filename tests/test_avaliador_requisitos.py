import pytest

from planejador.avaliador_requisitos import (
    ContextoAvaliacaoCurricular,
    EstadoAplicabilidade,
    EstadoAvaliacao,
    MedicaoRequisito,
    avaliar_modelo_requisitos,
)
from planejador.requisitos_curriculares import (
    CondicaoCurricular,
    GrupoRequisitos,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorCondicao,
    OperadorGrupo,
    ReferenciaCursoBase,
    RegraAplicabilidade,
    RegraCondicional,
    RequisitoQuantitativo,
    RestricaoContribuicao,
    SeletorComponentes,
    SequenciaRequisitos,
    TipoIntegralizador,
    UnidadeRequisito,
)


def _req(
    id_: str,
    minimo: int,
    *,
    unidade: UnidadeRequisito = UnidadeRequisito.CREDITOS,
    maximo: int | None = None,
) -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id=id_,
        descricao=id_,
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(qualquer_componente=True),
        limite=LimiteQuantitativo(unidade, minimo, maximo),
    )


def _med(
    id_: str,
    valor: int | None,
    *,
    unidade: UnidadeRequisito = UnidadeRequisito.CREDITOS,
    completos: bool = True,
) -> MedicaoRequisito:
    return MedicaoRequisito(id_, unidade, valor, completos)


def test_quantitativo_distingue_cumprido_pendente_e_indeterminado():
    modelo = ModeloRequisitosCurriculares("curso", "2026", (_req("r", 8),))

    cumprido = avaliar_modelo_requisitos(
        modelo, ContextoAvaliacaoCurricular(medicoes={"r": _med("r", 8)})
    )
    pendente = avaliar_modelo_requisitos(
        modelo, ContextoAvaliacaoCurricular(medicoes={"r": _med("r", 4)})
    )
    incompleto = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={"r": _med("r", 4, completos=False)}
        ),
    )
    ausente = avaliar_modelo_requisitos(modelo, ContextoAvaliacaoCurricular())

    assert cumprido.estado == EstadoAvaliacao.CUMPRIDO
    assert pendente.estado == EstadoAvaliacao.PENDENTE
    assert incompleto.estado == EstadoAvaliacao.INDETERMINADO
    assert ausente.estado == EstadoAvaliacao.INDETERMINADO


def test_grupo_qualquer_nao_exige_todas_as_alternativas():
    a = _req("a", 4)
    b = _req("b", 4)
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (a, b),
        grupos=(
            GrupoRequisitos(
                id="escolha",
                descricao="A ou B",
                requisitos=("a", "b"),
                operador=OperadorGrupo.QUALQUER,
            ),
        ),
    )
    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={"a": _med("a", 4), "b": _med("b", 0)}
        ),
    )

    assert resultado.estado == EstadoAvaliacao.CUMPRIDO
    assert resultado.regras_raiz == ("escolha",)
    assert resultado.por_id["escolha"].estado == EstadoAvaliacao.CUMPRIDO


def test_grupo_minimo_preserva_incerteza_quando_ela_pode_mudar_resultado():
    requisitos = tuple(
        _req(id_, 1, unidade=UnidadeRequisito.COMPONENTES)
        for id_ in ("a", "b", "c")
    )
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        requisitos,
        grupos=(
            GrupoRequisitos(
                id="duas_de_tres",
                descricao="Duas de três",
                requisitos=("a", "b", "c"),
                operador=OperadorGrupo.MINIMO,
                minimo_requisitos=2,
            ),
        ),
    )
    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={
                "a": _med("a", 1, unidade=UnidadeRequisito.COMPONENTES),
                "b": _med("b", 0, unidade=UnidadeRequisito.COMPONENTES),
            }
        ),
    )

    assert resultado.estado == EstadoAvaliacao.INDETERMINADO


def test_condicional_exige_somente_o_ramo_selecionado():
    regular = _req("regular", 8)
    especial = _req("especial", 4)
    condicao = CondicaoCurricular(
        "modalidade",
        OperadorCondicao.IGUAL,
        "especial",
    )
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (regular, especial),
        condicionais=(
            RegraCondicional(
                id="trilha",
                descricao="Trilha por modalidade",
                condicao=condicao,
                requisitos_se_verdadeira=("especial",),
                requisitos_se_falsa=("regular",),
            ),
        ),
    )
    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={"especial": _med("especial", 4)},
            atributos={"modalidade": "especial"},
        ),
    )

    assert resultado.estado == EstadoAvaliacao.CUMPRIDO
    assert "regular" not in resultado.por_id
    assert resultado.por_id["trilha"].estado == EstadoAvaliacao.CUMPRIDO


def test_condicional_sem_atributo_nao_vira_pendencia():
    regular = _req("regular", 8)
    especial = _req("especial", 4)
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (regular, especial),
        condicionais=(
            RegraCondicional(
                id="trilha",
                descricao="Trilha",
                condicao=CondicaoCurricular(
                    "modalidade", OperadorCondicao.IGUAL, "especial"
                ),
                requisitos_se_verdadeira=("especial",),
                requisitos_se_falsa=("regular",),
            ),
        ),
    )
    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={
                "especial": _med("especial", 4),
                "regular": _med("regular", 0),
            }
        ),
    )

    assert resultado.estado == EstadoAvaliacao.INDETERMINADO


def test_aplicabilidade_fica_separada_do_estado_de_integralizacao():
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (_req("r", 4),),
        aplicabilidade=(
            RegraAplicabilidade(
                id="coorte",
                descricao="Somente ingressantes 2026",
                condicoes=(
                    CondicaoCurricular(
                        "ano_ingresso", OperadorCondicao.MAIOR_OU_IGUAL, 2026
                    ),
                ),
            ),
        ),
    )

    nao_aplicavel = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(atributos={"ano_ingresso": 2025}),
    )
    incerto = avaliar_modelo_requisitos(modelo, ContextoAvaliacaoCurricular())

    assert nao_aplicavel.aplicabilidade == EstadoAplicabilidade.NAO_APLICAVEL
    assert nao_aplicavel.estado is None
    assert incerto.aplicabilidade == EstadoAplicabilidade.INDETERMINADA
    assert incerto.estado == EstadoAvaliacao.INDETERMINADO


def test_sequencia_com_ordem_obrigatoria_exige_evidencia_da_ordem():
    a = _req("etapa_a", 1, unidade=UnidadeRequisito.COMPONENTES)
    b = _req("etapa_b", 1, unidade=UnidadeRequisito.COMPONENTES)
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (a, b),
        sequencias=(
            SequenciaRequisitos(
                id="sequencia",
                descricao="Etapas em ordem",
                etapas=("etapa_a", "etapa_b"),
                ordem_obrigatoria=True,
            ),
        ),
    )
    medicoes = {
        "etapa_a": _med("etapa_a", 1, unidade=UnidadeRequisito.COMPONENTES),
        "etapa_b": _med("etapa_b", 1, unidade=UnidadeRequisito.COMPONENTES),
    }

    sem_ordem = avaliar_modelo_requisitos(
        modelo, ContextoAvaliacaoCurricular(medicoes=medicoes)
    )
    confirmada = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes=medicoes,
            sequencias_confirmadas={"sequencia": True},
        ),
    )

    assert sem_ordem.estado == EstadoAvaliacao.INDETERMINADO
    assert confirmada.estado == EstadoAvaliacao.CUMPRIDO


def test_restricao_de_contribuicao_compoe_o_requisito_total():
    total = _req(
        "extensao_total",
        100,
        unidade=UnidadeRequisito.HORAS,
    )
    parcela = RestricaoContribuicao(
        id="extensao_estagio",
        descricao="Parcela de estágio",
        requisito_total="extensao_total",
        seletor=SeletorComponentes(qualquer_componente=True),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, 40, 40),
    )
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (total,),
        contribuicoes=(parcela,),
    )
    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={
                "extensao_total": _med(
                    "extensao_total", 100, unidade=UnidadeRequisito.HORAS
                ),
                "extensao_estagio": _med(
                    "extensao_estagio", 20, unidade=UnidadeRequisito.HORAS
                ),
            }
        ),
    )

    assert resultado.por_id["extensao_total"].estado == EstadoAvaliacao.PENDENTE
    assert resultado.por_id["extensao_estagio"].estado == EstadoAvaliacao.PENDENTE
    assert resultado.estado == EstadoAvaliacao.PENDENTE


def test_curso_base_obrigatorio_sem_confirmacao_fica_indeterminado():
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (_req("r", 4),),
        cursos_base=(
            ReferenciaCursoBase(
                curso_id="bct",
                matriz_id="2023",
                exigir_conclusao_base=True,
            ),
        ),
    )
    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(medicoes={"r": _med("r", 4)}),
    )

    assert resultado.estado == EstadoAvaliacao.INDETERMINADO
    assert (
        resultado.por_id["curso_base:bct:2023"].estado
        == EstadoAvaliacao.INDETERMINADO
    )


def test_unidade_incompativel_e_erro_de_integracao_nao_regra_academica():
    modelo = ModeloRequisitosCurriculares("curso", "2026", (_req("r", 4),))

    with pytest.raises(ValueError, match="mas a regra exige creditos"):
        avaliar_modelo_requisitos(
            modelo,
            ContextoAvaliacaoCurricular(
                medicoes={
                    "r": _med("r", 4, unidade=UnidadeRequisito.HORAS)
                }
            ),
        )


def test_teto_limita_contribuicao_sem_transformar_excesso_em_falha():
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (_req("r", 4, maximo=6),),
    )
    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(medicoes={"r": _med("r", 9)}),
    )

    regra = resultado.por_id["r"]
    assert regra.estado == EstadoAvaliacao.CUMPRIDO
    assert regra.valor_observado == 9
    assert regra.valor_considerado == 6
