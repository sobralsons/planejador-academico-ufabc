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
from .autoridade_curricular import (
    DecisaoCorteAutoridade,
    EvidenciasCorteAutoridade,
    decidir_corte_autoridade,
)
from .evidencias_historico import (
    MetadadosCodigoEvidencia,
    ResultadoConversaoHistorico,
    converter_historico_consolidado_em_evidencias,
)
from .modelos import DisciplinaCurricular, SituacaoAcademica, TipoComponente
from .requisitos_curriculares import (
    CondicaoCurricular,
    FonteRegra,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorCondicao,
    RegraAplicabilidade,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


_CAMPOS_APLICABILIDADE = {
    "bct_2015": "matriz_bct_2015_confirmada",
    "bcd_2023": "matriz_bcd_2023_confirmada",
}


@dataclass(frozen=True)
class DivergenciaSombra:
    legado: str | None
    generico: str | None
    valor_legado: int | None
    valor_generico: int | None
    classificacao: str
    causa: str
    decisao: str
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
    curriculo_id: str = ""
    publicavel: bool = False
    proveniencia_regras_suficiente: bool = False

    @property
    def corte_autoridade(self) -> DecisaoCorteAutoridade:
        """Diagnostica o corte; evidências de aprovação não registradas ficam pendentes."""
        return decidir_corte_autoridade(
            self.curriculo_id,
            EvidenciasCorteAutoridade(
                fontes_versionadas=self.proveniencia_regras_suficiente,
                aplicabilidade_resolvida=self.aplicabilidade == "aplicavel",
            ),
        )

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

    return _avaliar_curriculo_piloto_em_modo_sombra(
        "bct_2015",
        metadados,
        curriculo,
        situacao,
        pacote_piloto_confirmado=pacote_piloto_confirmado,
        aplicabilidade_confirmada=aplicabilidade_confirmada,
        classificacoes_validadas=classificacoes_validadas,
        resultado_legado=resultado_legado,
    )


def avaliar_bcd_2023_em_modo_sombra(
    metadados: dict,
    curriculo: dict[str, DisciplinaCurricular],
    situacao: SituacaoAcademica,
    *,
    pacote_piloto_confirmado: bool = False,
    aplicabilidade_confirmada: bool | None = None,
    classificacoes_validadas: bool = False,
    resultado_legado: dict | None = None,
) -> ResultadoSombraBCT | None:
    """Executa o segundo piloto pelo mesmo contrato controlado."""

    return _avaliar_curriculo_piloto_em_modo_sombra(
        "bcd_2023",
        metadados,
        curriculo,
        situacao,
        pacote_piloto_confirmado=pacote_piloto_confirmado,
        aplicabilidade_confirmada=aplicabilidade_confirmada,
        classificacoes_validadas=classificacoes_validadas,
        resultado_legado=resultado_legado,
    )


def _avaliar_curriculo_piloto_em_modo_sombra(
    curriculo_id: str,
    metadados: dict,
    curriculo: dict[str, DisciplinaCurricular],
    situacao: SituacaoAcademica,
    *,
    pacote_piloto_confirmado: bool,
    aplicabilidade_confirmada: bool | None,
    classificacoes_validadas: bool,
    resultado_legado: dict | None,
) -> ResultadoSombraBCT | None:
    campo_aplicabilidade = _CAMPOS_APLICABILIDADE[curriculo_id]

    if metadados.get("id") != curriculo_id:
        return None
    if pacote_piloto_confirmado is not True:
        raise ValueError("O modo sombra exige confirmação explícita do pacote piloto.")
    if aplicabilidade_confirmada is not None and type(aplicabilidade_confirmada) is not bool:
        raise ValueError("Aplicabilidade confirmada deve ser booleana ou ausente.")
    if type(classificacoes_validadas) is not bool:
        raise ValueError("A confirmação das classificações deve ser booleana.")

    modelo = _criar_modelo(metadados, campo_aplicabilidade)
    classificacoes = (
        {
            codigo: MetadadosCodigoEvidencia(
                categorias=frozenset({disciplina.categoria.value}),
                tipos=frozenset({disciplina.tipo_componente.value}),
                tags=(frozenset({"extensao"}) if disciplina.e else frozenset()),
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
            {campo_aplicabilidade: aplicabilidade_confirmada}
            if aplicabilidade_confirmada is not None
            else {}
        ),
    )
    proveniencia_suficiente = _proveniencia_suficiente(modelo)
    if not proveniencia_suficiente:
        avisos.append(
            "As regras do piloto não possuem proveniência estruturada e revisada "
            "suficiente para receber autoridade."
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
        curriculo_id=curriculo_id,
        proveniencia_regras_suficiente=proveniencia_suficiente,
    )


def _criar_modelo(
    metadados: dict, campo_aplicabilidade: str
) -> ModeloRequisitosCurriculares:
    fontes = _fontes_estruturadas(metadados)
    requisitos = [
        _requisito_creditos(
            "creditos_obrigatorios",
            "Créditos obrigatórios",
            "obrigatoria",
            metadados["creditos_obrigatorios"],
            fontes,
        ),
        _requisito_creditos(
            "creditos_opcao_limitada",
            "Créditos de opção limitada",
            "opcao_limitada",
            metadados["creditos_opcao_limitada"],
            fontes,
        ),
        _requisito_creditos(
            "creditos_livres",
            "Créditos livres",
            "livre",
            metadados["creditos_livres"],
            fontes,
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
            fontes=fontes,
        ),
    ]
    if metadados.get("extensao_horas", 0):
        requisitos.append(
            RequisitoQuantitativo(
                id="extensao",
                descricao="Extensão",
                integralizador=TipoIntegralizador.EXTENSAO,
                seletor=SeletorComponentes(tags=frozenset({"extensao"})),
                limite=LimiteQuantitativo(
                    UnidadeRequisito.HORAS_EXTENSAO,
                    metadados["extensao_horas"],
                ),
                fontes=fontes,
            )
        )
    if metadados.get("trabalho_final_creditos", 0):
        requisitos.append(
            RequisitoQuantitativo(
                id="trabalho_final",
                descricao="Trabalho final",
                integralizador=TipoIntegralizador.TCC,
                seletor=SeletorComponentes(
                    tipos=frozenset({TipoComponente.TRABALHO_GRADUACAO.value})
                ),
                limite=LimiteQuantitativo(
                    UnidadeRequisito.CREDITOS,
                    metadados["trabalho_final_creditos"],
                ),
                fontes=fontes,
            )
        )
    return ModeloRequisitosCurriculares(
        curso_id=str(metadados["id"]),
        matriz_id=str(metadados["versao"]),
        requisitos=tuple(requisitos),
        aplicabilidade=(
            RegraAplicabilidade(
                id=f"aplicabilidade_{metadados['id']}",
                descricao="Exige confirmação explícita de vínculo à matriz selecionada.",
                condicoes=(
                    CondicaoCurricular(
                        campo=campo_aplicabilidade,
                        operador=OperadorCondicao.IGUAL,
                        valor=True,
                    ),
                ),
                fontes=fontes,
            ),
        ),
        fontes_gerais=fontes,
        metadados=(("modo", "sombra_controlada"),),
    )


def _requisito_creditos(
    id_: str,
    descricao: str,
    categoria: str,
    minimo: int,
    fontes: tuple[FonteRegra, ...],
) -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id=id_,
        descricao=descricao,
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(categorias=frozenset({categoria})),
        limite=LimiteQuantitativo(UnidadeRequisito.CREDITOS, minimo),
        fontes=fontes,
    )


def _fontes_estruturadas(metadados: dict) -> tuple[FonteRegra, ...]:
    fontes = metadados.get("fontes_regras", {})
    if not isinstance(fontes, dict):
        return ()

    estruturadas = []
    for dados in fontes.values():
        if not isinstance(dados, dict):
            continue
        try:
            estruturadas.append(FonteRegra(**dados))
        except (TypeError, ValueError):
            continue
    return tuple(estruturadas)


def _proveniencia_suficiente(modelo: ModeloRequisitosCurriculares) -> bool:
    regras = (*modelo.requisitos, *modelo.aplicabilidade)
    return bool(regras) and all(
        regra.fontes
        and all(
            fonte.matriz_id == modelo.curso_id
            and fonte.versao == modelo.matriz_id
            and fonte.estado_revisao == "revisada"
            for fonte in regra.fontes
        )
        for regra in regras
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
    comparaveis: dict[str, tuple[str | None, int | None]] = {
        requisito_id: (None, None) for requisito_id in requisitos
    }
    for requisito_id, categoria in categorias.items():
        resultado_categoria = legado_por_categoria.get(categoria, {})
        legado = resultado_categoria.get("estado_confirmado")
        valor_legado = None
        if legado is not None:
            valor_legado = resultado_categoria.get("integralizado_confirmado", 0)
            valor_legado += resultado_categoria.get("excedente_confirmado", 0)
        comparaveis[requisito_id] = (legado, valor_legado)

    regra_atividades = requisitos.get("atividades_complementares")
    horas_legado = resultado_legado.get("atividades_complementares_horas")
    valor_atividades = (
        int(horas_legado) if _inteiro_nao_negativo(horas_legado) else None
    )
    estado_atividades = None
    if (
        regra_atividades is not None
        and regra_atividades.minimo_exigido is not None
        and valor_atividades is not None
    ):
        estado_atividades = (
            "cumprido"
            if valor_atividades >= regra_atividades.minimo_exigido
            else "pendente"
        )
    comparaveis["atividades_complementares"] = (
        estado_atividades,
        valor_atividades,
    )

    comparacao = {}
    for requisito_id, (legado, valor_legado) in comparaveis.items():
        regra = requisitos.get(requisito_id)
        generico = regra.estado.value if regra else None
        valor_generico = regra.valor_observado if regra else None
        if generico is None or legado is None:
            classificacao = "nao_comparavel"
            causa = "estado_ausente"
            decisao = "nao_promover"
            motivo = "Um dos motores não produziu estado comparável."
        elif generico == legado and valor_generico == valor_legado:
            classificacao = "concordante"
            causa = "nenhuma"
            decisao = "manter_sombra"
            motivo = "Estado e total observado coincidem."
        else:
            classificacao = "divergente_requer_revisao"
            causas = []
            conversao_creditos_incompleta = any(
                UnidadeRequisito.CREDITOS in item.unidades_afetadas
                for item in conversao.pendencias
            )
            if conversao_creditos_incompleta:
                causas.append("A conversão do histórico possui pendência em créditos")
            if valor_generico != valor_legado:
                causas.append("os totais observados divergem")
            if conversao_creditos_incompleta:
                causa = "conversao_creditos_incompleta"
                decisao = "revisar_sem_promover"
            elif valor_generico != valor_legado:
                causa = "total_observado_divergente"
                decisao = "revisar_sem_promover"
            elif legado == "pendente" and generico == "indeterminado":
                causa = "completude_nao_certificada"
                decisao = "preservar_indeterminacao"
            else:
                causa = "estado_divergente"
                decisao = "revisar_sem_promover"
            motivo = "; ".join(causas or ["os estados divergem"]) + "."
        comparacao[requisito_id] = DivergenciaSombra(
            legado=legado,
            generico=generico,
            valor_legado=valor_legado,
            valor_generico=valor_generico,
            classificacao=classificacao,
            causa=causa,
            decisao=decisao,
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
