from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import product
from typing import Iterable

from .alocacao_evidencias import (
    AvaliacaoComEvidencias,
    ConjuntoEvidencias,
    DecisaoAlocacao,
    avaliar_modelo_com_evidencias,
)
from .avaliador_requisitos import EstadoAvaliacao
from .requisitos_curriculares import ModeloRequisitosCurriculares, UnidadeRequisito


_MAX_EVIDENCIAS_POR_QUESTAO = 10
_MAX_OPCOES_POR_QUESTAO = 64


@dataclass(frozen=True)
class ImpactoRequisitoAlocacao:
    requisito_id: str
    estado_antes: EstadoAvaliacao | None
    estado_depois: EstadoAvaliacao | None
    valor_antes: int | None
    valor_depois: int | None


@dataclass(frozen=True)
class OpcaoAlocacaoComponentes:
    id: str
    decisoes: tuple[DecisaoAlocacao, ...]
    evidencias_usadas: tuple[str, ...]
    requisitos_destino: tuple[str, ...]
    recursos_consumidos: tuple[str, ...]
    impactos: tuple[ImpactoRequisitoAlocacao, ...]
    estado_modelo_depois: EstadoAvaliacao | None
    pendencias_restantes: int
    bloqueios_restantes: tuple[str, ...]


@dataclass(frozen=True)
class QuestaoAlocacaoComponentes:
    id: str
    evidencias: tuple[str, ...]
    recursos: tuple[str, ...]
    opcoes: tuple[OpcaoAlocacaoComponentes, ...]
    completa: bool
    motivo: str

    @property
    def auto_resolvivel(self) -> bool:
        return self.completa and len(self.opcoes) == 1


@dataclass(frozen=True)
class PlanoOpcoesAlocacao:
    questoes: tuple[QuestaoAlocacaoComponentes, ...]

    @property
    def decisoes_univocas(self) -> tuple[DecisaoAlocacao, ...]:
        decisoes: list[DecisaoAlocacao] = []
        for questao in self.questoes:
            if questao.auto_resolvivel:
                decisoes.extend(questao.opcoes[0].decisoes)
        return tuple(decisoes)

    def opcao_por_id(self, opcao_id: str) -> OpcaoAlocacaoComponentes:
        encontradas = [
            opcao
            for questao in self.questoes
            for opcao in questao.opcoes
            if opcao.id == opcao_id
        ]
        if len(encontradas) != 1:
            raise ValueError(f"Opção de alocação inexistente ou ambígua: {opcao_id}.")
        return encontradas[0]


def gerar_opcoes_alocacao_componentes(
    modelo: ModeloRequisitosCurriculares,
    conjunto: ConjuntoEvidencias,
    decisoes_base: tuple[DecisaoAlocacao, ...] = (),
    *,
    max_evidencias_por_questao: int = _MAX_EVIDENCIAS_POR_QUESTAO,
    max_opcoes_por_questao: int = _MAX_OPCOES_POR_QUESTAO,
) -> PlanoOpcoesAlocacao:
    """Expõe alternativas atômicas sem escolher uma política acadêmica.

    O escopo é deliberadamente restrito a componentes com quantidade 1.
    Créditos e horas podem exigir divisão quantitativa e permanecem fora desta
    etapa. Em A + B -> C, por exemplo, o plano apresenta usar A e B ou usar C.
    Nenhuma opção recebe preferência por ordem, código ou efeito no resultado.
    """

    if max_evidencias_por_questao < 1 or max_opcoes_por_questao < 1:
        raise ValueError("Limites de geração de opções devem ser positivos.")

    baseline = avaliar_modelo_com_evidencias(modelo, conjunto, decisoes_base)
    evidencias = conjunto.por_id
    pendencias_componentes = {
        item.evidencia_id: item
        for item in baseline.alocacao.pendencias
        if item.unidade == UnidadeRequisito.COMPONENTES
        and item.quantidade == 1
        and item.evidencia_id in evidencias
    }

    ids = sorted(pendencias_componentes)
    componentes = _componentes_conectados(ids, evidencias)
    questoes: list[QuestaoAlocacaoComponentes] = []

    for grupo in componentes:
        recursos = tuple(sorted(set().union(*(
            evidencias[eid].recursos_componentes for eid in grupo
        ))))
        questao_id = _id_estavel("questao", (*grupo, *recursos))

        if len(grupo) > max_evidencias_por_questao:
            questoes.append(
                QuestaoAlocacaoComponentes(
                    id=questao_id,
                    evidencias=grupo,
                    recursos=recursos,
                    opcoes=(),
                    completa=False,
                    motivo=(
                        "Conflito de componentes excede o limite seguro de análise "
                        f"({len(grupo)}/{max_evidencias_por_questao}). "
                        "Nenhuma escolha automática foi feita."
                    ),
                )
            )
            continue

        conjuntos = _conjuntos_maximos_compativeis(grupo, evidencias)
        especificacoes: list[tuple[tuple[str, str], ...]] = []
        excedeu = False

        for conjunto_ids in conjuntos:
            candidatos = [
                tuple(sorted(pendencias_componentes[eid].candidatos))
                for eid in conjunto_ids
            ]
            if any(not itens for itens in candidatos):
                continue
            for escolha in product(*candidatos):
                especificacao = tuple(sorted(zip(conjunto_ids, escolha)))
                especificacoes.append(especificacao)
                if len(especificacoes) > max_opcoes_por_questao:
                    excedeu = True
                    break
            if excedeu:
                break

        if excedeu:
            questoes.append(
                QuestaoAlocacaoComponentes(
                    id=questao_id,
                    evidencias=grupo,
                    recursos=recursos,
                    opcoes=(),
                    completa=False,
                    motivo=(
                        "Número de alternativas excede o limite seguro de análise "
                        f"({max_opcoes_por_questao}). Nenhuma escolha automática "
                        "foi feita."
                    ),
                )
            )
            continue

        opcoes = tuple(
            _construir_opcao(
                modelo,
                conjunto,
                baseline,
                decisoes_base,
                especificacao,
                evidencias,
            )
            for especificacao in sorted(set(especificacoes))
        )
        questoes.append(
            QuestaoAlocacaoComponentes(
                id=questao_id,
                evidencias=grupo,
                recursos=recursos,
                opcoes=opcoes,
                completa=True,
                motivo=(
                    "As alternativas usam componentes ou recursos acadêmicos "
                    "concorrentes. A ordem das opções é estável, mas não expressa "
                    "preferência acadêmica."
                ),
            )
        )

    return PlanoOpcoesAlocacao(tuple(sorted(questoes, key=lambda item: item.id)))


def aplicar_opcao_alocacao_componentes(
    modelo: ModeloRequisitosCurriculares,
    conjunto: ConjuntoEvidencias,
    opcao: OpcaoAlocacaoComponentes,
    decisoes_base: tuple[DecisaoAlocacao, ...] = (),
) -> AvaliacaoComEvidencias:
    """Aplica uma opção já gerada, preservando as validações do alocador."""

    return avaliar_modelo_com_evidencias(
        modelo,
        conjunto,
        decisoes=(*decisoes_base, *opcao.decisoes),
    )


def _componentes_conectados(
    ids: list[str],
    evidencias: dict,
) -> tuple[tuple[str, ...], ...]:
    restantes = set(ids)
    grupos: list[tuple[str, ...]] = []

    while restantes:
        inicio = min(restantes)
        pilha = [inicio]
        grupo: set[str] = set()
        while pilha:
            atual = pilha.pop()
            if atual in grupo:
                continue
            grupo.add(atual)
            recursos = evidencias[atual].recursos_componentes
            vizinhos = {
                outro
                for outro in restantes
                if outro != atual
                and recursos
                and recursos & evidencias[outro].recursos_componentes
            }
            pilha.extend(sorted(vizinhos, reverse=True))
        restantes -= grupo
        grupos.append(tuple(sorted(grupo)))

    return tuple(grupos)


def _conjuntos_maximos_compativeis(
    grupo: tuple[str, ...],
    evidencias: dict,
) -> tuple[tuple[str, ...], ...]:
    """Enumera conjuntos maximais sem sobreposição de recursos."""

    n = len(grupo)
    independentes: list[tuple[str, ...]] = []

    for mascara in range(1, 1 << n):
        selecionados = tuple(
            grupo[indice] for indice in range(n) if mascara & (1 << indice)
        )
        if not _compativeis(selecionados, evidencias):
            continue

        restantes = tuple(item for item in grupo if item not in selecionados)
        if any(
            _compativeis((*selecionados, candidato), evidencias)
            for candidato in restantes
        ):
            continue
        independentes.append(selecionados)

    return tuple(sorted(set(independentes)))


def _compativeis(ids: Iterable[str], evidencias: dict) -> bool:
    usados: set[str] = set()
    for evidencia_id in ids:
        recursos = set(evidencias[evidencia_id].recursos_componentes)
        if usados & recursos:
            return False
        usados.update(recursos)
    return True


def _construir_opcao(
    modelo: ModeloRequisitosCurriculares,
    conjunto: ConjuntoEvidencias,
    baseline: AvaliacaoComEvidencias,
    decisoes_base: tuple[DecisaoAlocacao, ...],
    especificacao: tuple[tuple[str, str], ...],
    evidencias: dict,
) -> OpcaoAlocacaoComponentes:
    decisoes = tuple(
        DecisaoAlocacao(
            evidencia_id=evidencia_id,
            unidade=UnidadeRequisito.COMPONENTES,
            requisito_ids=(requisito_id,),
            quantidade=1,
        )
        for evidencia_id, requisito_id in especificacao
    )
    resultado = avaliar_modelo_com_evidencias(
        modelo,
        conjunto,
        decisoes=(*decisoes_base, *decisoes),
    )

    requisitos_afetados = tuple(sorted({req for _, req in especificacao}))
    impactos = tuple(
        _impacto_requisito(baseline, resultado, requisito_id)
        for requisito_id in requisitos_afetados
    )
    recursos = tuple(sorted(set().union(*(
        evidencias[eid].recursos_componentes for eid, _ in especificacao
    ))))
    evidencias_usadas = tuple(eid for eid, _ in especificacao)
    requisitos_destino = tuple(req for _, req in especificacao)
    opcao_id = _id_estavel(
        "opcao",
        tuple(f"{eid}->{req}" for eid, req in especificacao),
    )

    return OpcaoAlocacaoComponentes(
        id=opcao_id,
        decisoes=decisoes,
        evidencias_usadas=evidencias_usadas,
        requisitos_destino=requisitos_destino,
        recursos_consumidos=recursos,
        impactos=impactos,
        estado_modelo_depois=(
            resultado.avaliacao.estado if resultado.avaliacao is not None else None
        ),
        pendencias_restantes=len(resultado.alocacao.pendencias),
        bloqueios_restantes=resultado.alocacao.bloqueios,
    )


def _impacto_requisito(
    antes: AvaliacaoComEvidencias,
    depois: AvaliacaoComEvidencias,
    requisito_id: str,
) -> ImpactoRequisitoAlocacao:
    antes_regra = (
        antes.avaliacao.por_id.get(requisito_id)
        if antes.avaliacao is not None
        else None
    )
    depois_regra = (
        depois.avaliacao.por_id.get(requisito_id)
        if depois.avaliacao is not None
        else None
    )
    return ImpactoRequisitoAlocacao(
        requisito_id=requisito_id,
        estado_antes=antes_regra.estado if antes_regra is not None else None,
        estado_depois=depois_regra.estado if depois_regra is not None else None,
        valor_antes=antes_regra.valor_considerado if antes_regra is not None else None,
        valor_depois=depois_regra.valor_considerado if depois_regra is not None else None,
    )


def _id_estavel(prefixo: str, partes: Iterable[str]) -> str:
    carga = "|".join((prefixo, *partes)).encode("utf-8")
    return f"{prefixo}_{sha256(carga).hexdigest()[:16]}"
