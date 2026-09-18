from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .alocacao_evidencias import ConjuntoEvidencias, EvidenciaAcademica
from .historico import STATUS_CONCLUIDOS
from .modelos import RegistroHistorico, SituacaoAcademica
from .requisitos_curriculares import UnidadeRequisito


_ORIGEM_CONSOLIDADA = "historico_consolidado"
_UNIDADES_SUPORTADAS = frozenset(
    {
        UnidadeRequisito.CREDITOS,
        UnidadeRequisito.COMPONENTES,
        UnidadeRequisito.HORAS_CARGA_HORARIA,
        UnidadeRequisito.HORAS_EXTENSAO,
    }
)
_UNIDADES_QUANTITATIVAS_NAO_TRANSFERIVEIS = frozenset(
    {
        UnidadeRequisito.CREDITOS,
        UnidadeRequisito.HORAS_CARGA_HORARIA,
        UnidadeRequisito.HORAS_EXTENSAO,
    }
)


@dataclass(frozen=True)
class MetadadosCodigoEvidencia:
    """Classificação explícita de um código reconhecido academicamente.

    Nada aqui é inferido do nome da disciplina ou de categoria_original do
    SIGAA. O chamador só deve preencher classificações validadas para a matriz
    analisada.
    """

    categorias: frozenset[str] = frozenset()
    tipos: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    origens: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PendenciaReconhecimentoHistorico:
    codigo_destino: str
    codigos_origem: tuple[str, ...]
    unidades_afetadas: frozenset[UnidadeRequisito]
    motivo: str


@dataclass(frozen=True)
class ConflitoQuantidadeHistorico:
    codigo_origem: str
    unidade: UnidadeRequisito
    valores_encontrados: tuple[int, ...]
    motivo: str


@dataclass(frozen=True)
class ResultadoConversaoHistorico:
    conjunto: ConjuntoEvidencias
    pendencias: tuple[PendenciaReconhecimentoHistorico, ...] = ()
    conflitos: tuple[ConflitoQuantidadeHistorico, ...] = ()
    unidades_solicitadas_completas: frozenset[UnidadeRequisito] = frozenset()

    @property
    def unidades_bloqueadas(self) -> frozenset[UnidadeRequisito]:
        bloqueadas: set[UnidadeRequisito] = set()
        for item in self.pendencias:
            bloqueadas.update(item.unidades_afetadas)
        for item in self.conflitos:
            bloqueadas.add(item.unidade)
        return frozenset(bloqueadas)

    @property
    def rastreabilidade_completa(self) -> bool:
        return not self.pendencias and not self.conflitos


def converter_historico_consolidado_em_evidencias(
    situacao: SituacaoAcademica,
    *,
    metadados_por_codigo: Mapping[str, MetadadosCodigoEvidencia] | None = None,
    unidades_completas: frozenset[UnidadeRequisito] = frozenset(),
) -> ResultadoConversaoHistorico:
    """Converte conclusões consolidadas em evidências sem duplicar reconhecimentos.

    A coluna carga_horaria do histórico e a coluna carga_extensao são
    representadas em unidades diferentes. HORAS continua sendo uma unidade
    genérica do modelo e não é preenchida automaticamente a partir do histórico.

    Reconhecimentos com uma única origem podem representar o componente de
    destino sem criar uma segunda conclusão. Quantidades da origem -- créditos,
    carga horária e horas extensionistas -- não são transferidas automaticamente
    para o código equivalente. Reconhecimentos compostos também não são
    materializados automaticamente.
    """

    metadados = dict(metadados_por_codigo or {})
    desconhecidas = set(unidades_completas) - _UNIDADES_SUPORTADAS
    if desconhecidas:
        nomes = ", ".join(sorted(item.value for item in desconhecidas))
        raise ValueError(
            "A conversão do histórico não certifica estas unidades: "
            f"{nomes}. Use as unidades específicas do histórico."
        )

    concluidas = set(situacao.concluidas)
    reconhecimentos_simples: dict[str, set[str]] = {}
    pendencias: list[PendenciaReconhecimentoHistorico] = []

    for destino in sorted(concluidas):
        origens = frozenset(situacao.origens_conclusao.get(destino, {destino}))
        if not origens:
            pendencias.append(
                PendenciaReconhecimentoHistorico(
                    codigo_destino=destino,
                    codigos_origem=(),
                    unidades_afetadas=_UNIDADES_SUPORTADAS,
                    motivo="Conclusão consolidada sem origem rastreável.",
                )
            )
            continue

        if len(origens) == 1:
            origem = next(iter(origens))
            if destino != origem:
                reconhecimentos_simples.setdefault(origem, set()).add(destino)
                pendencias.append(
                    PendenciaReconhecimentoHistorico(
                        codigo_destino=destino,
                        codigos_origem=(origem,),
                        unidades_afetadas=_UNIDADES_QUANTITATIVAS_NAO_TRANSFERIVEIS,
                        motivo=(
                            "O código reconhecido pode representar o componente, "
                            "mas quantidades do destino não são inferidas da origem."
                        ),
                    )
                )
            continue

        pendencias.append(
            PendenciaReconhecimentoHistorico(
                codigo_destino=destino,
                codigos_origem=tuple(sorted(origens)),
                unidades_afetadas=_UNIDADES_SUPORTADAS,
                motivo=(
                    "Reconhecimento composto exige todas as origens em conjunto e "
                    "não pode ser reduzido a um alias de uma única evidência."
                ),
            )
        )

    registros_concluidos: dict[str, list[RegistroHistorico]] = {}
    for codigo, tentativas in situacao.tentativas.items():
        aprovadas = [item for item in tentativas if item.situacao in STATUS_CONCLUIDOS]
        if aprovadas:
            registros_concluidos[codigo] = aprovadas

    origens_necessarias = {
        origem
        for codigo in concluidas
        for origem in situacao.origens_conclusao.get(codigo, {codigo})
    }
    conflitos: list[ConflitoQuantidadeHistorico] = []
    evidencias: list[EvidenciaAcademica] = []

    for origem in sorted(origens_necessarias):
        tentativas = registros_concluidos.get(origem, [])
        if not tentativas:
            pendencias.append(
                PendenciaReconhecimentoHistorico(
                    codigo_destino=origem,
                    codigos_origem=(origem,),
                    unidades_afetadas=_UNIDADES_SUPORTADAS,
                    motivo=(
                        "A origem declarada pela consolidação não possui registro "
                        "concluído rastreável entre as tentativas disponíveis."
                    ),
                )
            )
            continue

        aliases = reconhecimentos_simples.get(origem, set())
        codigos_componente = frozenset({origem, *aliases})
        meta_componente = _combinar_metadados(codigos_componente, metadados)
        evidencias.append(
            EvidenciaAcademica(
                id=f"historico:{origem}:componente",
                codigos=codigos_componente,
                categorias=meta_componente.categorias,
                tipos=meta_componente.tipos,
                tags=meta_componente.tags,
                origens=frozenset({_ORIGEM_CONSOLIDADA, *meta_componente.origens}),
                quantidades={UnidadeRequisito.COMPONENTES: 1},
                observacoes=(
                    "Conclusão consolidada; reconhecimentos simples compartilham "
                    "esta mesma evidência de componente.",
                ),
            )
        )

        meta_quantidade = metadados.get(origem, MetadadosCodigoEvidencia())
        _adicionar_quantidade(
            evidencias,
            conflitos,
            origem=origem,
            tentativas=tentativas,
            unidade=UnidadeRequisito.CREDITOS,
            sufixo_id="creditos",
            extrair=lambda item: item.creditos,
            metadados=meta_quantidade,
            observacao=(
                "Créditos preservados do componente de origem concluído; "
                "não transferidos automaticamente para códigos equivalentes."
            ),
        )
        _adicionar_quantidade(
            evidencias,
            conflitos,
            origem=origem,
            tentativas=tentativas,
            unidade=UnidadeRequisito.HORAS_CARGA_HORARIA,
            sufixo_id="horas_carga_horaria",
            extrair=lambda item: item.carga_horaria,
            metadados=meta_quantidade,
            observacao=(
                "Carga horária preservada da coluna própria do histórico; "
                "não inclui inferência a partir de créditos ou extensão."
            ),
        )
        _adicionar_quantidade(
            evidencias,
            conflitos,
            origem=origem,
            tentativas=tentativas,
            unidade=UnidadeRequisito.HORAS_EXTENSAO,
            sufixo_id="horas_extensao",
            extrair=lambda item: item.carga_extensao,
            metadados=meta_quantidade,
            observacao=(
                "Horas extensionistas preservadas da coluna própria do histórico; "
                "não são somadas à carga horária como nova conclusão."
            ),
        )

    bloqueadas: set[UnidadeRequisito] = set()
    for item in pendencias:
        bloqueadas.update(item.unidades_afetadas)
    for item in conflitos:
        bloqueadas.add(item.unidade)

    efetivamente_completas = frozenset(
        unidade for unidade in unidades_completas if unidade not in bloqueadas
    )
    return ResultadoConversaoHistorico(
        conjunto=ConjuntoEvidencias(
            evidencias=tuple(evidencias),
            unidades_completas=efetivamente_completas,
        ),
        pendencias=tuple(pendencias),
        conflitos=tuple(conflitos),
        unidades_solicitadas_completas=unidades_completas,
    )


def _adicionar_quantidade(
    evidencias: list[EvidenciaAcademica],
    conflitos: list[ConflitoQuantidadeHistorico],
    *,
    origem: str,
    tentativas: list[RegistroHistorico],
    unidade: UnidadeRequisito,
    sufixo_id: str,
    extrair,
    metadados: MetadadosCodigoEvidencia,
    observacao: str,
) -> None:
    valores = tuple(sorted({extrair(item) for item in tentativas}))
    if len(valores) > 1:
        conflitos.append(
            ConflitoQuantidadeHistorico(
                codigo_origem=origem,
                unidade=unidade,
                valores_encontrados=valores,
                motivo=(
                    "Tentativas concluídas do mesmo código têm quantidades "
                    f"divergentes em {unidade.value}; nenhum valor foi escolhido."
                ),
            )
        )
        return

    quantidade = valores[0]
    if quantidade <= 0:
        return

    evidencias.append(
        EvidenciaAcademica(
            id=f"historico:{origem}:{sufixo_id}",
            codigos=frozenset({origem}),
            categorias=metadados.categorias,
            tipos=metadados.tipos,
            tags=metadados.tags,
            origens=frozenset({_ORIGEM_CONSOLIDADA, *metadados.origens}),
            quantidades={unidade: quantidade},
            observacoes=(observacao,),
        )
    )


def _combinar_metadados(
    codigos: frozenset[str],
    metadados: Mapping[str, MetadadosCodigoEvidencia],
) -> MetadadosCodigoEvidencia:
    categorias: set[str] = set()
    tipos: set[str] = set()
    tags: set[str] = set()
    origens: set[str] = set()
    for codigo in codigos:
        item = metadados.get(codigo)
        if item is None:
            continue
        categorias.update(item.categorias)
        tipos.update(item.tipos)
        tags.update(item.tags)
        origens.update(item.origens)
    return MetadadosCodigoEvidencia(
        categorias=frozenset(categorias),
        tipos=frozenset(tipos),
        tags=frozenset(tags),
        origens=frozenset(origens),
    )
