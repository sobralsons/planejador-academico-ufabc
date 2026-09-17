import pytest

from planejador.alocacao_evidencias import (
    ConjuntoEvidencias,
    DecisaoAlocacao,
    EvidenciaAcademica,
    alocar_evidencias,
    avaliar_modelo_com_evidencias,
    evidencia_atende_seletor,
)
from planejador.avaliador_requisitos import EstadoAvaliacao
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


def _req(
    id_: str,
    minimo: int,
    *,
    unidade: UnidadeRequisito = UnidadeRequisito.CREDITOS,
    codigos=(),
    tags=(),
    maximo=None,
):
    return RequisitoQuantitativo(
        id=id_,
        descricao=id_,
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(
            codigos=frozenset(codigos),
            tags=frozenset(tags),
            qualquer_componente=not codigos and not tags,
        ),
        limite=LimiteQuantitativo(unidade, minimo, maximo),
    )


def _evidencia(id_: str, unidade, quantidade, *, codigos=(), tags=()):
    return EvidenciaAcademica(
        id=id_,
        codigos=frozenset(codigos),
        tags=frozenset(tags),
        quantidades={unidade: quantidade},
    )


def test_seletor_usa_apenas_criterios_estruturados_e_respeita_operador():
    evidencia = EvidenciaAcademica(
        id="e1",
        codigos=frozenset({"ABC-23"}),
        tags=frozenset({"extensao"}),
        quantidades={UnidadeRequisito.CREDITOS: 4},
    )
    todos = SeletorComponentes(
        codigos=frozenset({"ABC-23"}),
        tags=frozenset({"outra_tag"}),
    )
    qualquer = SeletorComponentes(
        codigos=frozenset({"ABC-23"}),
        tags=frozenset({"outra_tag"}),
        operador=OperadorSeletor.QUALQUER_CRITERIO,
    )

    assert evidencia_atende_seletor(evidencia, todos) is False
    assert evidencia_atende_seletor(evidencia, qualquer) is True


def test_codigo_so_e_reconhecido_quando_foi_explicitamente_incluido_na_evidencia():
    requisito = _req("r", 4, codigos=("NOVO-23",))
    modelo = ModeloRequisitosCurriculares("curso", "2023", (requisito,))

    somente_antigo = ConjuntoEvidencias(
        (_evidencia("e", UnidadeRequisito.CREDITOS, 4, codigos=("ANTIGO-17",)),),
        frozenset({UnidadeRequisito.CREDITOS}),
    )
    resultado = avaliar_modelo_com_evidencias(modelo, somente_antigo)
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.PENDENTE

    reconhecido = ConjuntoEvidencias(
        (_evidencia(
            "e", UnidadeRequisito.CREDITOS, 4,
            codigos=("ANTIGO-17", "NOVO-23"),
        ),),
        frozenset({UnidadeRequisito.CREDITOS}),
    )
    resultado = avaliar_modelo_com_evidencias(modelo, reconhecido)
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.CUMPRIDO


def test_evidencia_inequivoca_e_alocada_automaticamente():
    requisito = _req("obrigatorias", 4, tags=("obrigatoria",))
    modelo = ModeloRequisitosCurriculares("curso", "2023", (requisito,))
    conjunto = ConjuntoEvidencias(
        (_evidencia(
            "disciplina_a", UnidadeRequisito.CREDITOS, 4,
            tags=("obrigatoria",),
        ),),
        frozenset({UnidadeRequisito.CREDITOS}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert resultado.alocacao.alocacoes[0].origem == "automatica"
    assert resultado.alocacao.medicoes["obrigatorias"].valor == 4
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.CUMPRIDO


def test_evidencia_ambigua_nao_e_escolhida_automaticamente():
    a = _req("a", 4, tags=("flexivel",))
    b = _req("b", 4, tags=("flexivel",))
    modelo = ModeloRequisitosCurriculares("curso", "2023", (a, b))
    conjunto = ConjuntoEvidencias(
        (_evidencia("e", UnidadeRequisito.CREDITOS, 4, tags=("flexivel",)),),
        frozenset({UnidadeRequisito.CREDITOS}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert len(resultado.alocacao.pendencias) == 1
    assert resultado.alocacao.medicoes["a"].dados_completos is False
    assert resultado.alocacao.medicoes["b"].dados_completos is False
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.INDETERMINADO


def test_decisao_explicita_pode_dividir_quantidade_sem_dupla_contagem():
    a = _req("a", 4, tags=("flexivel",))
    b = _req("b", 4, tags=("flexivel",))
    modelo = ModeloRequisitosCurriculares("curso", "2023", (a, b))
    conjunto = ConjuntoEvidencias(
        (_evidencia("e", UnidadeRequisito.CREDITOS, 8, tags=("flexivel",)),),
        frozenset({UnidadeRequisito.CREDITOS}),
    )
    decisoes = (
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("a",), 4),
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("b",), 4),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto, decisoes)

    assert resultado.alocacao.medicoes["a"].valor == 4
    assert resultado.alocacao.medicoes["b"].valor == 4
    assert not resultado.alocacao.pendencias
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.CUMPRIDO


def test_decisoes_nao_podem_consumir_mais_que_a_evidencia():
    a = _req("a", 4, tags=("flexivel",))
    b = _req("b", 4, tags=("flexivel",))
    modelo = ModeloRequisitosCurriculares("curso", "2023", (a, b))
    conjunto = ConjuntoEvidencias(
        (_evidencia("e", UnidadeRequisito.CREDITOS, 8, tags=("flexivel",)),),
    )
    decisoes = (
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("a",), 5),
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("b",), 4),
    )

    with pytest.raises(ValueError, match="excede a quantidade disponível"):
        alocar_evidencias(modelo, conjunto, decisoes)


def test_reuso_em_dois_requisitos_exige_compartilhamento_explicito():
    a = _req("a", 4, tags=("comum",))
    b = _req("b", 4, tags=("comum",))
    modelo = ModeloRequisitosCurriculares("curso", "2023", (a, b))
    conjunto = ConjuntoEvidencias(
        (_evidencia("e", UnidadeRequisito.CREDITOS, 4, tags=("comum",)),),
    )
    decisao = (
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("a", "b"), 4),
    )

    with pytest.raises(ValueError, match="regra explícita"):
        alocar_evidencias(modelo, conjunto, decisao)


def test_compartilhamento_explicito_permite_reuso_e_respeita_teto():
    a = _req("a", 4, tags=("comum",))
    b = _req("b", 4, tags=("comum",))
    regra = RegraCompartilhamento(
        "a", "b", UnidadeRequisito.CREDITOS, maximo_compartilhavel=4
    )
    modelo = ModeloRequisitosCurriculares(
        "curso", "2023", (a, b), compartilhamentos=(regra,)
    )
    conjunto = ConjuntoEvidencias(
        (_evidencia("e", UnidadeRequisito.CREDITOS, 4, tags=("comum",)),),
        frozenset({UnidadeRequisito.CREDITOS}),
    )
    decisao = (
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("a", "b"), 4),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto, decisao)
    assert resultado.alocacao.compartilhamentos_usados[frozenset({"a", "b"})] == 4
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.CUMPRIDO

    regra_teto = RegraCompartilhamento(
        "a", "b", UnidadeRequisito.CREDITOS, maximo_compartilhavel=2
    )
    modelo_teto = ModeloRequisitosCurriculares(
        "curso", "2023", (a, b), compartilhamentos=(regra_teto,)
    )
    with pytest.raises(ValueError, match="excede o máximo"):
        alocar_evidencias(modelo_teto, conjunto, decisao)


def test_compartilhamento_minimo_obrigatorio_bloqueia_avaliacao_ate_ser_comprovado():
    a = _req("a", 2, tags=("comum",))
    b = _req("b", 2, tags=("comum",))
    regra = RegraCompartilhamento(
        "a", "b", UnidadeRequisito.CREDITOS,
        maximo_compartilhavel=4,
        minimo_compartilhavel=4,
    )
    modelo = ModeloRequisitosCurriculares(
        "curso", "2023", (a, b), compartilhamentos=(regra,)
    )
    conjunto = ConjuntoEvidencias(
        (_evidencia("e", UnidadeRequisito.CREDITOS, 4, tags=("comum",)),),
        frozenset({UnidadeRequisito.CREDITOS}),
    )
    decisoes_sem_reuso = (
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("a",), 2),
        DecisaoAlocacao("e", UnidadeRequisito.CREDITOS, ("b",), 2),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto, decisoes_sem_reuso)

    assert resultado.alocacao.pronta_para_avaliacao is False
    assert resultado.alocacao.bloqueios
    assert resultado.avaliacao is None


def test_contribuicao_interna_reusa_evidencia_do_total_sem_consumir_duas_vezes():
    total = _req(
        "extensao_total", 10,
        unidade=UnidadeRequisito.HORAS,
        tags=("extensao",),
    )
    parte = RestricaoContribuicao(
        id="extensao_estagio",
        descricao="Parcela extensionista de estágio",
        requisito_total="extensao_total",
        seletor=SeletorComponentes(tags=frozenset({"estagio_extensionista"})),
        limite=LimiteQuantitativo(UnidadeRequisito.HORAS, 4, 10),
    )
    modelo = ModeloRequisitosCurriculares(
        "curso", "2023", (total,), contribuicoes=(parte,)
    )
    conjunto = ConjuntoEvidencias(
        (_evidencia(
            "atividade", UnidadeRequisito.HORAS, 10,
            tags=("extensao", "estagio_extensionista"),
        ),),
        frozenset({UnidadeRequisito.HORAS}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert resultado.alocacao.medicoes["extensao_total"].valor == 10
    assert resultado.alocacao.medicoes["extensao_estagio"].valor == 10
    assert sum(a.quantidade for a in resultado.alocacao.alocacoes) == 10
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.CUMPRIDO


def test_unidade_completa_sem_evidencia_produz_pendencia_real():
    requisito = _req("creditos", 4)
    modelo = ModeloRequisitosCurriculares("curso", "2023", (requisito,))
    conjunto = ConjuntoEvidencias(
        (), frozenset({UnidadeRequisito.CREDITOS})
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert resultado.alocacao.medicoes["creditos"].valor == 0
    assert resultado.alocacao.medicoes["creditos"].dados_completos is True
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.PENDENTE


def test_unidade_incompleta_sem_evidencia_permanece_indeterminada():
    requisito = _req("horas", 100, unidade=UnidadeRequisito.HORAS, tags=("atividade",))
    modelo = ModeloRequisitosCurriculares("curso", "2023", (requisito,))

    resultado = avaliar_modelo_com_evidencias(modelo, ConjuntoEvidencias(()))

    assert resultado.alocacao.medicoes["horas"].dados_completos is False
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.INDETERMINADO


def test_componentes_sao_contados_na_unidade_correta():
    requisito = _req(
        "tcc_etapa", 1,
        unidade=UnidadeRequisito.COMPONENTES,
        codigos=("TG1",),
    )
    modelo = ModeloRequisitosCurriculares("curso", "2023", (requisito,))
    conjunto = ConjuntoEvidencias(
        (_evidencia(
            "tg1", UnidadeRequisito.COMPONENTES, 1,
            codigos=("TG1",),
        ),),
        frozenset({UnidadeRequisito.COMPONENTES}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert resultado.alocacao.medicoes["tcc_etapa"].unidade == UnidadeRequisito.COMPONENTES
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.CUMPRIDO
