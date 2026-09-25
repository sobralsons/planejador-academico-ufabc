from pathlib import Path

from planejador.alocacao_evidencias import (
    ConjuntoEvidencias,
    EvidenciaAcademica,
    avaliar_modelo_com_evidencias,
)
from planejador.avaliador_requisitos import (
    ContextoAvaliacaoCurricular,
    EstadoAplicabilidade,
    EstadoAvaliacao,
    MedicaoRequisito,
    avaliar_modelo_requisitos,
)
from planejador.requisitos_curriculares import (
    CondicaoCurricular,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorCondicao,
    RegraAplicabilidade,
    RegraCompartilhamento,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


BASE = Path(__file__).resolve().parents[1]
CONTRATO = BASE / "docs/CONTRATO_INTEGRACAO_MOTOR_CURRICULAR.md"


def _requisito(id_: str, minimo: int = 4) -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id=id_,
        descricao=f"Requisito {id_}",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(tags=frozenset({id_})),
        limite=LimiteQuantitativo(UnidadeRequisito.CREDITOS, minimo),
    )


def test_contrato_documenta_fronteiras_e_fail_closed():
    texto = CONTRATO.read_text(encoding="utf-8")

    for simbolo in (
        "ModeloRequisitosCurriculares",
        "ResultadoConversaoHistorico",
        "ConjuntoEvidencias.unidades_completas",
        "EvidenciaAcademica",
        "avaliar_modelo_com_evidencias",
        "PendenciaAlocacao",
        "DecisaoAlocacao",
        "EstadoAplicabilidade",
        "EstadoAvaliacao",
        "MedicaoRequisito.dados_completos",
    ):
        assert simbolo in texto

    assert "dados incompletos nunca podem provar pendência" in texto
    assert "não pode cair silenciosamente" in texto
    assert "modo sombra" in texto
    assert "teste diferencial legado × genérico" in texto


def test_dado_incompleto_nao_prova_pendencia_mas_pode_provar_cumprimento():
    requisito = _requisito("r", minimo=4)
    modelo = ModeloRequisitosCurriculares("curso", "2026", (requisito,))

    abaixo = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={
                "r": MedicaoRequisito(
                    requisito_id="r",
                    unidade=UnidadeRequisito.CREDITOS,
                    valor=3,
                    dados_completos=False,
                )
            }
        ),
    )
    suficiente = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(
            medicoes={
                "r": MedicaoRequisito(
                    requisito_id="r",
                    unidade=UnidadeRequisito.CREDITOS,
                    valor=4,
                    dados_completos=False,
                )
            }
        ),
    )

    assert abaixo.estado == EstadoAvaliacao.INDETERMINADO
    assert abaixo.por_id["r"].estado == EstadoAvaliacao.INDETERMINADO
    assert suficiente.estado == EstadoAvaliacao.CUMPRIDO
    assert suficiente.por_id["r"].estado == EstadoAvaliacao.CUMPRIDO


def test_aplicabilidade_sem_atributo_permanece_indeterminada():
    requisito = _requisito("r")
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (requisito,),
        aplicabilidade=(
            RegraAplicabilidade(
                id="aplica",
                descricao="Depende do ano de ingresso",
                condicoes=(
                    CondicaoCurricular(
                        campo="ano_ingresso",
                        operador=OperadorCondicao.MAIOR_OU_IGUAL,
                        valor=2023,
                    ),
                ),
            ),
        ),
    )

    resultado = avaliar_modelo_requisitos(
        modelo,
        ContextoAvaliacaoCurricular(),
    )

    assert resultado.aplicabilidade == EstadoAplicabilidade.INDETERMINADA
    assert resultado.estado == EstadoAvaliacao.INDETERMINADO


def test_bloqueio_de_alocacao_nao_produz_avaliacao():
    requisito_a = _requisito("a", minimo=1)
    requisito_b = _requisito("b", minimo=1)
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (requisito_a, requisito_b),
        compartilhamentos=(
            RegraCompartilhamento(
                requisito_a="a",
                requisito_b="b",
                unidade=UnidadeRequisito.CREDITOS,
                maximo_compartilhavel=1,
                minimo_compartilhavel=1,
            ),
        ),
    )
    conjunto = ConjuntoEvidencias(
        evidencias=(
            EvidenciaAcademica(
                id="somente_a",
                tags=frozenset({"a"}),
                quantidades={UnidadeRequisito.CREDITOS: 1},
            ),
        ),
        unidades_completas=frozenset({UnidadeRequisito.CREDITOS}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert resultado.alocacao.bloqueios
    assert not resultado.alocacao.pronta_para_avaliacao
    assert resultado.avaliacao is None
