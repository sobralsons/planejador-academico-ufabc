import pytest

from planejador.alocacao_evidencias import (
    ConjuntoEvidencias,
    DecisaoAlocacao,
    EvidenciaAcademica,
    alocar_evidencias,
)
from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


def _modelo():
    requisito = RequisitoQuantitativo(
        id="r",
        descricao="Requisito",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(qualquer_componente=True),
        limite=LimiteQuantitativo(UnidadeRequisito.CREDITOS, 1),
    )
    return ModeloRequisitosCurriculares("curso", "2023", (requisito,))


@pytest.mark.parametrize(
    "quantidades",
    [
        {UnidadeRequisito.CREDITOS: 0},
        {UnidadeRequisito.HORAS: 10},
    ],
)
def test_decisao_explicita_exige_quantidade_positiva_na_unidade(quantidades):
    evidencia = EvidenciaAcademica(
        id="e",
        quantidades=quantidades,
    )
    decisao = DecisaoAlocacao(
        "e", UnidadeRequisito.CREDITOS, ("r",), 1
    )

    with pytest.raises(ValueError, match="não possui quantidade positiva"):
        alocar_evidencias(
            _modelo(),
            ConjuntoEvidencias((evidencia,)),
            (decisao,),
        )
