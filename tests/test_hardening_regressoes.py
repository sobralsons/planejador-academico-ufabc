import time

import pytest

from api.app import app
from planejador.alocacao_evidencias import (
    ConjuntoEvidencias,
    EvidenciaAcademica,
    avaliar_modelo_com_evidencias,
)
from planejador.avaliador_requisitos import EstadoAvaliacao
from planejador.evidencias_historico import (
    MetadadosCodigoEvidencia,
    converter_historico_consolidado_em_evidencias,
)
from planejador.historico import consolidar_historico
from planejador.modelos import RegistroHistorico
from planejador.opcoes_alocacao import gerar_opcoes_alocacao_componentes
from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorSeletor,
    RegraCompartilhamento,
    RequisitoQuantitativo,
    RestricaoContribuicao,
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


def _requisito_componente(id_: str, *, tags=(), codigos=()):
    return RequisitoQuantitativo(
        id=id_,
        descricao=id_,
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(
            tags=frozenset(tags),
            codigos=frozenset(codigos),
        ),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )


def test_teto_de_contribuicao_limita_o_total_contabilizavel():
    total = RequisitoQuantitativo(
        id="extensao_total",
        descricao="Extensão total",
        integralizador=TipoIntegralizador.EXTENSAO,
        seletor=SeletorComponentes(tags=frozenset({"extensao"})),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, 100),
    )
    eventos = RestricaoContribuicao(
        id="eventos",
        descricao="Eventos podem contribuir com no máximo 40 horas",
        requisito_total="extensao_total",
        seletor=SeletorComponentes(tags=frozenset({"evento"})),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, 0, 40),
    )
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (total,),
        contribuicoes=(eventos,),
    )
    somente_eventos = ConjuntoEvidencias(
        (
            EvidenciaAcademica(
                id="100h_eventos",
                tags=frozenset({"extensao", "evento"}),
                quantidades={UnidadeRequisito.HORAS: 100},
            ),
        ),
        frozenset({UnidadeRequisito.HORAS}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, somente_eventos)

    assert resultado.avaliacao is not None
    assert resultado.alocacao.medicoes["eventos"].valor == 100
    assert resultado.alocacao.medicoes["extensao_total"].valor == 40
    assert resultado.avaliacao.por_id["extensao_total"].estado == EstadoAvaliacao.PENDENTE

    misto = ConjuntoEvidencias(
        (
            EvidenciaAcademica(
                id="40h_eventos",
                tags=frozenset({"extensao", "evento"}),
                quantidades={UnidadeRequisito.HORAS: 40},
            ),
            EvidenciaAcademica(
                id="60h_projeto",
                tags=frozenset({"extensao", "projeto"}),
                quantidades={UnidadeRequisito.HORAS: 60},
            ),
        ),
        frozenset({UnidadeRequisito.HORAS}),
    )
    resultado_misto = avaliar_modelo_com_evidencias(modelo, misto)
    assert resultado_misto.avaliacao is not None
    assert resultado_misto.alocacao.medicoes["extensao_total"].valor == 100
    assert resultado_misto.avaliacao.estado == EstadoAvaliacao.CUMPRIDO


def test_equivalencia_simples_nao_cruza_codigo_de_a_com_classificacao_de_b():
    situacao = consolidar_historico([_registro("A")], {"A": "B"})
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        metadados_por_codigo={
            "A": MetadadosCodigoEvidencia(categorias=frozenset({"livre"})),
            "B": MetadadosCodigoEvidencia(categorias=frozenset({"obrigatoria"})),
        },
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )
    impossivel = RequisitoQuantitativo(
        id="impossivel",
        descricao="Código A classificado como obrigatória",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(
            codigos=frozenset({"A"}),
            categorias=frozenset({"obrigatoria"}),
            operador=OperadorSeletor.TODOS_CRITERIOS,
        ),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    reconhecido = RequisitoQuantitativo(
        id="b_obrigatoria",
        descricao="B reconhecida como obrigatória",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(
            codigos=frozenset({"B"}),
            categorias=frozenset({"obrigatoria"}),
            operador=OperadorSeletor.TODOS_CRITERIOS,
        ),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (impossivel, reconhecido),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conversao.conjunto)

    assert resultado.avaliacao is not None
    assert resultado.avaliacao.por_id["impossivel"].estado != EstadoAvaliacao.CUMPRIDO
    evidencias_a = [
        item for item in conversao.conjunto.evidencias if item.codigos == frozenset({"A"})
    ]
    evidencias_b = [
        item for item in conversao.conjunto.evidencias if item.codigos == frozenset({"B"})
    ]
    assert evidencias_a and evidencias_b
    assert all(item.categorias == frozenset({"livre"}) for item in evidencias_a)
    assert all(item.categorias == frozenset({"obrigatoria"}) for item in evidencias_b)


def test_consolidacao_com_ciclos_e_derivacoes_compostas_tem_limite_de_custo():
    registros = [_registro(f"C{i}") for i in range(29)]
    regras_compostas = [
        ({f"C{i - 2}", f"C{i - 1}"}, f"C{i}")
        for i in range(2, 29)
    ]
    equivalencias = {"C28": "C0"}

    inicio = time.perf_counter()
    situacao = consolidar_historico(
        registros,
        equivalencias,
        regras_compostas,
    )
    duracao = time.perf_counter() - inicio

    assert duracao < 1.0
    assert len(situacao.concluidas) == 29
    assert all(
        len(derivacoes) <= 64
        for derivacoes in situacao.derivacoes_conclusao.values()
    )


def test_excesso_de_derivacoes_falha_fechado_sem_materializar_destino():
    registros = [
        _registro(codigo)
        for indice in range(7)
        for codigo in (f"A{indice}", f"B{indice}")
    ]
    equivalencias = {
        **{f"A{indice}": f"X{indice}" for indice in range(7)},
        **{f"B{indice}": f"X{indice}" for indice in range(7)},
    }
    situacao = consolidar_historico(
        registros,
        equivalencias,
        [({*(f"X{indice}" for indice in range(7))}, "Z")],
    )

    assert "Z" in situacao.concluidas
    assert "Z" in situacao.derivacoes_incompletas
    assert len(situacao.derivacoes_conclusao["Z"]) <= 64

    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )
    assert all(
        "Z" not in evidencia.codigos
        for evidencia in conversao.conjunto.evidencias
    )
    assert UnidadeRequisito.COMPONENTES not in conversao.conjunto.unidades_completas
    assert any(
        item.codigo_destino == "Z" and "limite seguro" in item.motivo
        for item in conversao.pendencias
    )


def test_gerador_inclui_opcao_compartilhada_quando_regra_autoriza():
    evidencia = EvidenciaAcademica(
        id="componente",
        tags=frozenset({"flexivel"}),
        quantidades={UnidadeRequisito.COMPONENTES: 1},
    )
    a = _requisito_componente("a", tags=("flexivel",))
    b = _requisito_componente("b", tags=("flexivel",))
    modelo = ModeloRequisitosCurriculares(
        "curso",
        "2026",
        (a, b),
        compartilhamentos=(
            RegraCompartilhamento(
                "a",
                "b",
                UnidadeRequisito.COMPONENTES,
                maximo_compartilhavel=1,
            ),
        ),
    )
    conjunto = ConjuntoEvidencias(
        (evidencia,),
        frozenset({UnidadeRequisito.COMPONENTES}),
    )

    plano = gerar_opcoes_alocacao_componentes(modelo, conjunto)

    assert len(plano.questoes) == 1
    questao = plano.questoes[0]
    assert questao.completa is True
    assert len(questao.opcoes) == 3
    destinos = {
        tuple(sorted(opcao.requisitos_destino))
        for opcao in questao.opcoes
    }
    assert destinos == {("a",), ("b",), ("a", "b")}
    compartilhada = next(
        opcao
        for opcao in questao.opcoes
        if tuple(sorted(opcao.requisitos_destino)) == ("a", "b")
    )
    assert compartilhada.estado_modelo_depois == EstadoAvaliacao.CUMPRIDO


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("creditos", True),
        ("creditos", "4"),
        ("carga_horaria", True),
        ("carga_horaria", "48"),
        ("carga_extensao", True),
        ("carga_extensao", "12"),
    ],
)
def test_api_rejeita_coercao_de_quantidades_inteiras(campo, valor):
    import asyncio
    import httpx2

    payload = {
        "componentes": [{"codigo": "A", campo: valor}],
        "equivalencias_compostas": [],
        "requisitos": [{"id": "r", "codigo": "A"}],
    }

    async def executar():
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/v1/synthetic/component-allocation/options",
                json=payload,
            )

    resposta = asyncio.run(executar())
    assert resposta.status_code == 422
    assert "request_invalido" in resposta.text
