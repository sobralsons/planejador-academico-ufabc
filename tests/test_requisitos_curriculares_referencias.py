import pytest

from planejador.requisitos_curriculares import (
    GrupoRequisitos,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorGrupo,
    RequisitoQuantitativo,
    SeletorComponentes,
    SequenciaRequisitos,
    TipoIntegralizador,
    UnidadeRequisito,
)


def _requisito_base() -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id="base",
        descricao="Requisito base",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(codigos=frozenset({"A"})),
        limite=LimiteQuantitativo(UnidadeRequisito.CREDITOS, 4),
    )


def test_grupo_nao_pode_referenciar_a_si_mesmo():
    with pytest.raises(ValueError, match="não pode referenciar a si mesmo"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2023",
            requisitos=(_requisito_base(),),
            grupos=(
                GrupoRequisitos(
                    id="grupo",
                    descricao="Grupo inválido",
                    requisitos=("grupo", "base"),
                    operador=OperadorGrupo.QUALQUER,
                ),
            ),
        )


def test_sequencia_rejeita_etapa_que_nao_existe():
    with pytest.raises(ValueError, match="regras inexistentes"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2023",
            requisitos=(_requisito_base(),),
            sequencias=(
                SequenciaRequisitos(
                    id="etapas",
                    descricao="Etapas inválidas",
                    etapas=("base", "inexistente"),
                ),
            ),
        )
