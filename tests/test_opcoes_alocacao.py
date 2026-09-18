import pytest

from planejador.alocacao_evidencias import ConjuntoEvidencias, EvidenciaAcademica
from planejador.avaliador_requisitos import EstadoAvaliacao
from planejador.evidencias_historico import converter_historico_consolidado_em_evidencias
from planejador.historico import consolidar_historico
from planejador.modelos import RegistroHistorico
from planejador.opcoes_alocacao import (
    aplicar_opcao_alocacao_componentes,
    gerar_opcoes_alocacao_componentes,
)
from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


def _registro(codigo: str) -> RegistroHistorico:
    return RegistroHistorico(
        periodo="2026.1",
        categoria_original="Sintética",
        codigo=codigo,
        nome=f"Componente {codigo}",
        creditos=4,
        carga_horaria=48,
        carga_extensao=0,
        turma="A",
        conceito="A",
        situacao="APR",
        docentes="Docente Sintético",
    )


def _req(id_: str, codigo: str) -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id=id_,
        descricao=id_,
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(codigos=frozenset({codigo})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )


def test_evidencia_atomica_com_dois_destinos_gera_duas_opcoes_sem_preferencia():
    evidencia = EvidenciaAcademica(
        id="e",
        codigos=frozenset({"X"}),
        tags=frozenset({"flexivel"}),
        recursos_componentes=frozenset({"r1"}),
        quantidades={UnidadeRequisito.COMPONENTES: 1},
    )
    a = RequisitoQuantitativo(
        id="a",
        descricao="A",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(tags=frozenset({"flexivel"})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    b = RequisitoQuantitativo(
        id="b",
        descricao="B",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(tags=frozenset({"flexivel"})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    modelo = ModeloRequisitosCurriculares("curso", "2026", (a, b))
    conjunto = ConjuntoEvidencias(
        (evidencia,),
        frozenset({UnidadeRequisito.COMPONENTES}),
    )

    plano = gerar_opcoes_alocacao_componentes(modelo, conjunto)

    assert len(plano.questoes) == 1
    questao = plano.questoes[0]
    assert questao.completa is True
    assert questao.auto_resolvivel is False
    assert len(questao.opcoes) == 2
    assert {opcao.requisitos_destino for opcao in questao.opcoes} == {
        ("a",),
        ("b",),
    }
    assert plano.decisoes_univocas == ()
    assert "não expressa preferência" in questao.motivo


def test_ids_e_ordem_das_opcoes_sao_estaveis_independentemente_da_ordem_das_evidencias():
    e1 = EvidenciaAcademica(
        id="a",
        codigos=frozenset({"A"}),
        recursos_componentes=frozenset({"ra"}),
        quantidades={UnidadeRequisito.COMPONENTES: 1},
    )
    e2 = EvidenciaAcademica(
        id="c",
        codigos=frozenset({"C"}),
        recursos_componentes=frozenset({"ra"}),
        quantidades={UnidadeRequisito.COMPONENTES: 1},
    )
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (_req("req_a", "A"), _req("req_c", "C")),
    )

    p1 = gerar_opcoes_alocacao_componentes(
        modelo,
        ConjuntoEvidencias(
            (e1, e2),
            frozenset({UnidadeRequisito.COMPONENTES}),
        ),
    )
    p2 = gerar_opcoes_alocacao_componentes(
        modelo,
        ConjuntoEvidencias(
            (e2, e1),
            frozenset({UnidadeRequisito.COMPONENTES}),
        ),
    )

    assert tuple(q.id for q in p1.questoes) == tuple(q.id for q in p2.questoes)
    assert tuple(o.id for o in p1.questoes[0].opcoes) == tuple(
        o.id for o in p2.questoes[0].opcoes
    )


def test_limite_de_complexidade_falha_fechado_sem_gerar_escolha_parcial():
    evidencias = tuple(
        EvidenciaAcademica(
            id=f"e{i}",
            codigos=frozenset({f"C{i}"}),
            recursos_componentes=frozenset({"recurso_comum"}),
            quantidades={UnidadeRequisito.COMPONENTES: 1},
        )
        for i in range(3)
    )
    requisitos = tuple(_req(f"r{i}", f"C{i}") for i in range(3))
    modelo = ModeloRequisitosCurriculares("curso", "2026", requisitos)
    conjunto = ConjuntoEvidencias(
        evidencias,
        frozenset({UnidadeRequisito.COMPONENTES}),
    )

    plano = gerar_opcoes_alocacao_componentes(
        modelo,
        conjunto,
        max_evidencias_por_questao=2,
    )

    assert len(plano.questoes) == 1
    assert plano.questoes[0].completa is False
    assert plano.questoes[0].opcoes == ()
    assert "Nenhuma escolha automática" in plano.questoes[0].motivo


def test_fluxo_end_to_end_equivalencia_composta_expoe_ab_ou_c_e_aplica_escolha():
    situacao = consolidar_historico(
        [_registro("A"), _registro("B")],
        {},
        [({"A", "B"}, "C")],
    )
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (
            _req("usar_a", "A"),
            _req("usar_b", "B"),
            _req("usar_c", "C"),
        ),
    )

    plano = gerar_opcoes_alocacao_componentes(modelo, conversao.conjunto)

    assert len(plano.questoes) == 1
    questao = plano.questoes[0]
    assert len(questao.opcoes) == 2

    por_evidencias = {
        frozenset(opcao.evidencias_usadas): opcao
        for opcao in questao.opcoes
    }
    opcao_ab = por_evidencias[
        frozenset({"historico:A:componente", "historico:B:componente"})
    ]
    opcao_c = por_evidencias[
        frozenset({"historico:equivalencia_composta:C:componente"})
    ]

    resultado_ab = aplicar_opcao_alocacao_componentes(
        modelo, conversao.conjunto, opcao_ab
    )
    assert resultado_ab.avaliacao is not None
    assert resultado_ab.avaliacao.por_id["usar_a"].estado == EstadoAvaliacao.CUMPRIDO
    assert resultado_ab.avaliacao.por_id["usar_b"].estado == EstadoAvaliacao.CUMPRIDO
    assert resultado_ab.avaliacao.por_id["usar_c"].estado == EstadoAvaliacao.PENDENTE

    resultado_c = aplicar_opcao_alocacao_componentes(
        modelo, conversao.conjunto, opcao_c
    )
    assert resultado_c.avaliacao is not None
    assert resultado_c.avaliacao.por_id["usar_c"].estado == EstadoAvaliacao.CUMPRIDO
    assert resultado_c.avaliacao.por_id["usar_a"].estado == EstadoAvaliacao.PENDENTE
    assert resultado_c.avaliacao.por_id["usar_b"].estado == EstadoAvaliacao.PENDENTE

    assert opcao_ab.id != opcao_c.id
    assert plano.opcao_por_id(opcao_c.id) == opcao_c


def test_impacto_da_opcao_e_calculado_sem_ser_usado_como_ranking():
    evidencia = EvidenciaAcademica(
        id="e",
        codigos=frozenset({"X"}),
        tags=frozenset({"flexivel"}),
        recursos_componentes=frozenset({"r"}),
        quantidades={UnidadeRequisito.COMPONENTES: 1},
    )
    a = RequisitoQuantitativo(
        id="a",
        descricao="A",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(tags=frozenset({"flexivel"})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    b = RequisitoQuantitativo(
        id="b",
        descricao="B",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(tags=frozenset({"flexivel"})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    modelo = ModeloRequisitosCurriculares("curso", "2026", (a, b))
    plano = gerar_opcoes_alocacao_componentes(
        modelo,
        ConjuntoEvidencias(
            (evidencia,),
            frozenset({UnidadeRequisito.COMPONENTES}),
        ),
    )

    assert len(plano.questoes[0].opcoes) == 2
    for opcao in plano.questoes[0].opcoes:
        assert len(opcao.impactos) == 1
        impacto = opcao.impactos[0]
        assert impacto.estado_antes == EstadoAvaliacao.INDETERMINADO
        assert impacto.estado_depois == EstadoAvaliacao.CUMPRIDO
        assert impacto.valor_antes == 0
        assert impacto.valor_depois == 1

    # Mesmo que as opções tenham impacto calculado, nenhuma recebe seleção
    # automática por parecer melhor.
    assert plano.decisoes_univocas == ()


def test_busca_por_id_rejeita_opcao_inexistente():
    plano = gerar_opcoes_alocacao_componentes(
        ModeloRequisitosCurriculares(
            "curso",
            "2026",
            (
                RequisitoQuantitativo(
                    id="r",
                    descricao="R",
                    integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
                    seletor=SeletorComponentes(codigos=frozenset({"A"})),
                    limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
                ),
            ),
        ),
        ConjuntoEvidencias(()),
    )

    with pytest.raises(ValueError, match="inexistente ou ambígua"):
        plano.opcao_por_id("opcao_nao_existe")
