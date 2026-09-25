from planejador.academico import auditoria_integralizacao
from planejador.alocacao_evidencias import avaliar_modelo_com_evidencias
from planejador.avaliador_requisitos import EstadoAvaliacao
from planejador.evidencias_historico import converter_historico_consolidado_em_evidencias
from planejador.historico import consolidar_historico
from planejador.modelos import Categoria, DisciplinaCurricular, RegistroHistorico
from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


def _registro(codigo: str, creditos: int = 4) -> RegistroHistorico:
    return RegistroHistorico(
        periodo="2026.1",
        categoria_original="Sintética",
        codigo=codigo,
        nome=f"Disciplina {codigo}",
        creditos=creditos,
        carga_horaria=creditos * 12,
        carga_extensao=0,
        turma="A",
        conceito="A",
        situacao="APR",
        docentes="Docente Sintético",
    )


def _disciplina(codigo: str, creditos: int = 4) -> DisciplinaCurricular:
    return DisciplinaCurricular(
        codigo=codigo,
        nome=f"Disciplina {codigo}",
        categoria=Categoria.OBRIGATORIA,
        creditos=creditos,
        t=creditos,
        p=0,
        e=0,
        i=0,
    )


def _avaliar_generico(situacao, codigo: str, minimo: int):
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset({UnidadeRequisito.CREDITOS}),
    )
    modelo = ModeloRequisitosCurriculares(
        curso_id="curso_sintetico",
        matriz_id="2026",
        requisitos=(
            RequisitoQuantitativo(
                id="obrigatorias",
                descricao="Créditos obrigatórios",
                integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
                seletor=SeletorComponentes(codigos=frozenset({codigo})),
                limite=LimiteQuantitativo(UnidadeRequisito.CREDITOS, minimo),
            ),
        ),
    )
    return conversao, avaliar_modelo_com_evidencias(modelo, conversao.conjunto)


def test_legado_e_generico_concordam_em_creditos_diretos_cumpridos_e_pendentes():
    for minimo, estado, pendente in (
        (4, EstadoAvaliacao.CUMPRIDO, 0),
        (8, EstadoAvaliacao.PENDENTE, 4),
    ):
        situacao = consolidar_historico([_registro("A")], {})
        legado = auditoria_integralizacao(
            {"creditos_obrigatorios": minimo},
            {"A": _disciplina("A")},
            situacao,
            set(situacao.concluidas),
        )
        conversao, generico = _avaliar_generico(situacao, "A", minimo)

        regra = generico.avaliacao.por_id["obrigatorias"]
        categoria = legado["por_categoria"]["obrigatoria"]

        assert conversao.rastreabilidade_completa
        assert generico.avaliacao is not None
        assert regra.estado == estado
        assert regra.valor_considerado == categoria["integralizado_confirmado"]
        assert categoria["pendente_confirmado"] == pendente


def test_divergencia_conhecida_equivalencia_nao_transfere_creditos_no_generico():
    situacao = consolidar_historico([_registro("A")], {"A": "B"})
    legado = auditoria_integralizacao(
        {"creditos_obrigatorios": 4},
        {"B": _disciplina("B")},
        situacao,
        set(situacao.concluidas),
    )
    conversao, generico = _avaliar_generico(situacao, "B", 4)

    # Divergência esperada da migração: o legado usa os créditos cadastrados no
    # destino B; o genérico reconhece o componente B, mas não inventa seus créditos.
    assert legado["por_categoria"]["obrigatoria"]["integralizado_confirmado"] == 4
    assert UnidadeRequisito.CREDITOS not in conversao.conjunto.unidades_completas
    assert any(item.codigo_destino == "B" for item in conversao.pendencias)
    assert generico.avaliacao is not None
    assert generico.avaliacao.por_id["obrigatorias"].estado == EstadoAvaliacao.INDETERMINADO
