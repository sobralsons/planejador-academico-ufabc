from __future__ import annotations

from dataclasses import dataclass

from planejador.evidencias_historico import converter_historico_consolidado_em_evidencias
from planejador.historico import consolidar_historico
from planejador.modelos import RegistroHistorico
from planejador.opcoes_alocacao import gerar_opcoes_alocacao_componentes
from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)

from .contratos import (
    CenarioSinteticoEntrada,
    DecisaoAlocacaoSaida,
    ImpactoRequisitoSaida,
    OpcaoAlocacaoSaida,
    QuestaoAlocacaoSaida,
    ResultadoOpcoesSinteticas,
)


@dataclass(frozen=True)
class ErroCenarioSintetico(Exception):
    codigo: str
    mensagem: str


def gerar_opcoes_sinteticas(
    entrada: CenarioSinteticoEntrada,
) -> ResultadoOpcoesSinteticas:
    """Adapta entrada HTTP sintética ao núcleo sem duplicar regra acadêmica."""

    codigos_disponiveis = {item.codigo for item in entrada.componentes}
    for regra in entrada.equivalencias_compostas:
        ausentes = set(regra.origens) - codigos_disponiveis
        if ausentes:
            raise ErroCenarioSintetico(
                "origem_inexistente",
                "Equivalência composta referencia origem não presente no cenário.",
            )

    registros = tuple(_registro_sintetico(item) for item in entrada.componentes)
    situacao = consolidar_historico(
        list(registros),
        {},
        [
            (set(regra.origens), regra.destino)
            for regra in entrada.equivalencias_compostas
        ],
    )
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )
    modelo = ModeloRequisitosCurriculares(
        curso_id="api_sintetica",
        matriz_id="api_sintetica_v1",
        requisitos=tuple(_requisito(item.id, item.codigo) for item in entrada.requisitos),
    )

    try:
        plano = gerar_opcoes_alocacao_componentes(modelo, conversao.conjunto)
    except ValueError as exc:
        raise ErroCenarioSintetico(
            "cenario_incompativel",
            "O cenário sintético não pôde ser processado com segurança.",
        ) from exc

    # Reavaliação sem decisões explícitas, apenas para informar o estado inicial.
    from planejador.alocacao_evidencias import avaliar_modelo_com_evidencias

    inicial = avaliar_modelo_com_evidencias(modelo, conversao.conjunto)
    estado_inicial = (
        inicial.avaliacao.estado.value
        if inicial.avaliacao is not None
        else None
    )

    return ResultadoOpcoesSinteticas(
        estado_inicial=estado_inicial,
        questoes=tuple(_questao_saida(item) for item in plano.questoes),
    )


def _registro_sintetico(item) -> RegistroHistorico:
    return RegistroHistorico(
        periodo="SINTETICO",
        categoria_original="SINTETICO",
        codigo=item.codigo,
        nome="",
        creditos=item.creditos,
        carga_horaria=item.carga_horaria,
        carga_extensao=item.carga_extensao,
        turma="",
        conceito="",
        situacao="APR",
        docentes="",
    )


def _requisito(id_: str, codigo: str) -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id=id_,
        descricao=id_,
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(codigos=frozenset({codigo})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )


def _questao_saida(item) -> QuestaoAlocacaoSaida:
    return QuestaoAlocacaoSaida(
        id=item.id,
        evidencias=item.evidencias,
        recursos=item.recursos,
        opcoes=tuple(_opcao_saida(opcao) for opcao in item.opcoes),
        completa=item.completa,
        auto_resolvivel=item.auto_resolvivel,
        motivo=item.motivo,
    )


def _opcao_saida(item) -> OpcaoAlocacaoSaida:
    decisoes = tuple(
        DecisaoAlocacaoSaida(
            evidencia_id=decisao.evidencia_id,
            requisito_id=decisao.requisito_ids[0],
        )
        for decisao in item.decisoes
    )
    impactos = tuple(
        ImpactoRequisitoSaida(
            requisito_id=impacto.requisito_id,
            estado_antes=(
                impacto.estado_antes.value
                if impacto.estado_antes is not None
                else None
            ),
            estado_depois=(
                impacto.estado_depois.value
                if impacto.estado_depois is not None
                else None
            ),
            valor_antes=impacto.valor_antes,
            valor_depois=impacto.valor_depois,
        )
        for impacto in item.impactos
    )
    return OpcaoAlocacaoSaida(
        id=item.id,
        decisoes=decisoes,
        evidencias_usadas=item.evidencias_usadas,
        requisitos_destino=item.requisitos_destino,
        recursos_consumidos=item.recursos_consumidos,
        impactos=impactos,
        estado_modelo_depois=(
            item.estado_modelo_depois.value
            if item.estado_modelo_depois is not None
            else None
        ),
        pendencias_restantes=item.pendencias_restantes,
        bloqueios_restantes=item.bloqueios_restantes,
    )
