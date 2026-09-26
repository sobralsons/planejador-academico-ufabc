from __future__ import annotations

import math
from dataclasses import dataclass

from .alocacao_evidencias import (
    AvaliacaoComEvidencias,
    ConjuntoEvidencias,
    EvidenciaAcademica,
    avaliar_modelo_com_evidencias,
)
from .avaliador_requisitos import ResultadoRegra
from .evidencias_historico import (
    MetadadosCodigoEvidencia,
    ResultadoConversaoHistorico,
    converter_historico_consolidado_em_evidencias,
)
from .modelos import DisciplinaCurricular, SituacaoAcademica
from .requisitos_curriculares import (
    CondicaoCurricular,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorCondicao,
    RegraAplicabilidade,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


_CURRICULO_PILOTO = "bct_2015"
_CAMPO_APLICABILIDADE = "matriz_bct_2015_confirmada"


@dataclass(frozen=True)
class DivergenciaSombra:
    legado: str | None
    generico: str | None
    valor_legado: int | None
    valor_generico: int | None
    classificacao: str
    motivo: str


@dataclass(frozen=True)
class ResultadoSombraBCT:
    modelo: ModeloRequisitosCurriculares
    conversao: ResultadoConversaoHistorico
    conjunto: ConjuntoEvidencias
    resultado: AvaliacaoComEvidencias
    divergencias: dict[str, DivergenciaSombra]
    fontes_legadas_nao_estruturadas: tuple[str, ...]
    avisos: tuple[str, ...] = ()
    modo: str = "sombra_controlada"
    autoridade: str = "legado"
    curriculo_id: str = _CURRICULO_PILOTO
    publicavel: bool = False
    proveniencia_regras_suficiente: bool = False

    @property
    def aplicabilidade(self) -> str | None:
        avaliacao = self.resultado.avaliacao
        return avaliacao.aplicabilidade.value if avaliacao else None

    @property
    def estado(self) -> str | None:
        avaliacao = self.resultado.avaliacao
        return avaliacao.estado.value if avaliacao and avaliacao.estado else None

    @property
    def requisitos(self) -> dict[str, ResultadoRegra]:
        avaliacao = self.resultado.avaliacao
        if avaliacao is None:
            return {}
        return {
            item.regra_id: item
            for item in avaliacao.resultados
            if item.tipo == "requisito"
        }


def avaliar_bct_2015_em_modo_sombra(
    metadados: dict,
    curriculo: dict[str, DisciplinaCurricular],
    situacao: SituacaoAcademica,
    *,
    pacote_piloto_confirmado: bool = False,
    aplicabilidade_confirmada: bool | None = None,
    classificacoes_validadas: bool = False,
    resultado_legado: dict | None = None,
) -> ResultadoSombraBCT | None:
    """Executa comparação interna explícita sem tocar o fluxo público."""

    if metadados.get("id") != _CURRICULO_PILOTO:
        return None
    if pacote_piloto_confirmado is not True:
        raise ValueError("O modo sombra exige confirmação explícita do pacote piloto.")
    if aplicabilidade_confirmada is not None and type(aplicabilidade_confirmada) is not bool:
        raise ValueError("Aplicabilidade confirmada deve ser booleana ou ausente.")
    if type(classificacoes_validadas) is not bool:
        raise ValueError("A confirmação das classificações deve ser booleana.")

    modelo = _criar_modelo(metadados)
    classificacoes = (
        {
            codigo: MetadadosCodigoEvidencia(
                categorias=frozenset({disciplina.categoria.value}),
                origens=frozenset({"classificacao_curricular_confirmada"}),
            )
            for codigo, disciplina in curriculo.items()
        }
        if classificacoes_validadas
        else {}
    )
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        metadados_por_codigo=classificacoes,
    )

    evidencias = list(conversao.conjunto.evidencias)
    avisos: list[str] = []
    horas = situacao.resumo.atividades_complementares_horas
    if _inteiro_nao_negativo(horas):
        evidencias.append(
            EvidenciaAcademica(
                id="historico:resumo:atividades_complementares",
                tipos=frozenset({"atividades_complementares"}),
                origens=frozenset({"resumo_historico_origem_nao_confirmada"}),
                quantidades={UnidadeRequisito.HORAS: int(horas)},
                observacoes=(
                    "Total presente no resumo; origem e completude não foram inferidas.",
                ),
            )
        )
    elif horas is not None:
        avisos.append(
            "Atividades complementares não foram avaliadas porque o total não é "
            "um número inteiro não negativo."
        )

    conjunto = ConjuntoEvidencias(
        evidencias=tuple(evidencias),
        unidades_completas=conversao.conjunto.unidades_completas,
    )
    resultado = avaliar_modelo_com_evidencias(
        modelo,
        conjunto,
        atributos=(
            {_CAMPO_APLICABILIDADE: aplicabilidade_confirmada}
            if aplicabilidade_confirmada is not None
            else {}
        ),
    )
    requisitos = _requisitos(resultado)
    return ResultadoSombraBCT(
        modelo=modelo,
        conversao=conversao,
        conjunto=conjunto,
        resultado=resultado,
        divergencias=_comparar_com_legado(
            requisitos, resultado_legado, conversao
        ),
        fontes_legadas_nao_estruturadas=tuple(_fontes_legadas(metadados)),
        avisos=tuple(avisos),
    )


def _criar_modelo(metadados: dict) -> ModeloRequisitosCurriculares:
    requisitos = (
        _requisito_creditos(
            "creditos_obrigatorios",
            "Créditos obrigatórios",
            "obrigatoria",
            metadados["creditos_obrigatorios"],
        ),
        _requisito_creditos(
            "creditos_opcao_limitada",
            "Créditos de opção limitada",
            "opcao_limitada",
            metadados["creditos_opcao_limitada"],
        ),
        _requisito_creditos(
            "creditos_livres",
            "Créditos livres",
            "livre",
            metadados["creditos_livres"],
        ),
        RequisitoQuantitativo(
            id="atividades_complementares",
            descricao="Atividades complementares",
            integralizador=TipoIntegralizador.ATIVIDADES_COMPLEMENTARES,
            seletor=SeletorComponentes(
                tipos=frozenset({"atividades_complementares"})
            ),
            limite=LimiteQuantitativo(
                UnidadeRequisito.HORAS,
                metadados["atividades_complementares_horas"],
            ),
        ),
    )
    return ModeloRequisitosCurriculares(
        curso_id=str(metadados["id"]),
        matriz_id=str(metadados["versao"]),
        requisitos=requisitos,
        aplicabilidade=(
            RegraAplicabilidade(
                id="aplicabilidade_bct_2015",
                descricao="Exige confirmação explícita de vínculo à matriz BC&T 2015.",
                condicoes=(
                    CondicaoCurricular(
                        campo=_CAMPO_APLICABILIDADE,
                        operador=OperadorCondicao.IGUAL,
                        valor=True,
                    ),
                ),
            ),
        ),
        metadados=(("modo", "sombra_controlada"),),
    )


def _requisito_creditos(
    id_: str,
    descricao: str,
    categoria: str,
    minimo: int,
) -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id=id_,
        descricao=descricao,
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(categorias=frozenset({categoria})),
        limite=LimiteQuantitativo(UnidadeRequisito.CREDITOS, minimo),
    )


def _requisitos(resultado: AvaliacaoComEvidencias) -> dict[str, ResultadoRegra]:
    avaliacao = resultado.avaliacao
    if avaliacao is None:
        return {}
    return {
        item.regra_id: item
        for item in avaliacao.resultados
        if item.tipo == "requisito"
    }


def _comparar_com_legado(
    requisitos: dict[str, ResultadoRegra],
    resultado_legado: dict | None,
    conversao: ResultadoConversaoHistorico,
) -> dict[str, DivergenciaSombra]:
    if resultado_legado is None:
        return {}

    categorias = {
        "creditos_obrigatorios": "obrigatoria",
        "creditos_opcao_limitada": "opcao_limitada",
        "creditos_livres": "livre",
    }
    legado_por_categoria = resultado_legado.get("por_categoria", {})
    comparacao = {}
    for requisito_id, categoria in categorias.items():
        regra = requisitos.get(requisito_id)
        generico = regra.estado.value if regra else None
        resultado_categoria = legado_por_categoria.get(categoria, {})
        legado = resultado_categoria.get("estado_confirmado")
        valor_generico = regra.valor_observado if regra else None
        valor_legado = None
        if legado is not None:
            valor_legado = resultado_categoria.get("integralizado_confirmado", 0)
            valor_legado += resultado_categoria.get("excedente_confirmado", 0)
        if generico is None or legado is None:
            classificacao = "nao_comparavel"
            motivo = "Um dos motores não produziu estado comparável."
        elif generico == legado and valor_generico == valor_legado:
            classificacao = "concordante"
            motivo = "Estado e total observado coincidem."
        else:
            classificacao = "divergente_requer_revisao"
            causas = []
            if any(
                UnidadeRequisito.CREDITOS in item.unidades_afetadas
                for item in conversao.pendencias
            ):
                causas.append("A conversão do histórico possui pendência em créditos")
            if valor_generico != valor_legado:
                causas.append("os totais observados divergem")
            motivo = "; ".join(causas or ["os estados divergem"]) + "."
        comparacao[requisito_id] = DivergenciaSombra(
            legado=legado,
            generico=generico,
            valor_legado=valor_legado,
            valor_generico=valor_generico,
            classificacao=classificacao,
            motivo=motivo,
        )
    return comparacao


def _inteiro_nao_negativo(valor: object) -> bool:
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
        and valor >= 0
        and float(valor).is_integer()
    )


def _fontes_legadas(metadados: dict) -> list[str]:
    fontes = metadados.get("fontes", {})
    if isinstance(fontes, dict):
        return [str(valor) for valor in fontes.values()]
    if isinstance(fontes, list):
        return [str(valor) for valor in fontes]
    return []
