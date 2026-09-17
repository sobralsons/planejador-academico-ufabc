from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .avaliador_requisitos import (
    ContextoAvaliacaoCurricular,
    MedicaoRequisito,
    ResultadoAvaliacaoModelo,
    avaliar_modelo_requisitos,
)
from .requisitos_curriculares import (
    ModeloRequisitosCurriculares,
    OperadorSeletor,
    RegraCompartilhamento,
    SeletorComponentes,
    UnidadeRequisito,
    ValorCondicao,
)


@dataclass(frozen=True)
class EvidenciaAcademica:
    """Evidência já reconhecida por uma camada acadêmica anterior.

    ``codigos`` pode conter o código original e códigos reconhecidos por uma
    equivalência explicitamente validada. Este módulo não cria equivalências por
    nome, similaridade ou heurística.
    """

    id: str
    codigos: frozenset[str] = frozenset()
    categorias: frozenset[str] = frozenset()
    tipos: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    origens: frozenset[str] = frozenset()
    quantidades: Mapping[UnidadeRequisito, int] = field(default_factory=dict)
    observacoes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Evidência acadêmica precisa de id.")
        for unidade, valor in self.quantidades.items():
            if not isinstance(unidade, UnidadeRequisito):
                raise ValueError("Quantidade da evidência usa unidade inválida.")
            if type(valor) is not int or valor < 0:
                raise ValueError("Quantidade da evidência deve ser inteiro não negativo.")

    def quantidade(self, unidade: UnidadeRequisito) -> int:
        return int(self.quantidades.get(unidade, 0))


@dataclass(frozen=True)
class ConjuntoEvidencias:
    evidencias: tuple[EvidenciaAcademica, ...]
    unidades_completas: frozenset[UnidadeRequisito] = frozenset()

    def __post_init__(self) -> None:
        ids = [item.id for item in self.evidencias]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de evidências acadêmicas devem ser únicos.")

    @property
    def por_id(self) -> dict[str, EvidenciaAcademica]:
        return {item.id: item for item in self.evidencias}


@dataclass(frozen=True)
class DecisaoAlocacao:
    """Aloca um pedaço da evidência a um ou dois requisitos.

    Dois requisitos representam reutilização da mesma quantidade e só são
    aceitos quando existe ``RegraCompartilhamento`` explícita para o par.
    """

    evidencia_id: str
    unidade: UnidadeRequisito
    requisito_ids: tuple[str, ...]
    quantidade: int

    def __post_init__(self) -> None:
        if not self.evidencia_id.strip():
            raise ValueError("Decisão de alocação precisa indicar evidencia_id.")
        if not isinstance(self.unidade, UnidadeRequisito):
            raise ValueError("Decisão de alocação usa unidade inválida.")
        if len(self.requisito_ids) not in {1, 2}:
            raise ValueError("Alocação deve apontar para um ou dois requisitos.")
        if len(set(self.requisito_ids)) != len(self.requisito_ids):
            raise ValueError("Alocação não pode repetir o mesmo requisito.")
        if any(not item.strip() for item in self.requisito_ids):
            raise ValueError("Alocação contém requisito vazio.")
        if type(self.quantidade) is not int or self.quantidade <= 0:
            raise ValueError("Quantidade alocada deve ser inteiro positivo.")


@dataclass(frozen=True)
class AlocacaoRealizada:
    evidencia_id: str
    unidade: UnidadeRequisito
    requisito_ids: tuple[str, ...]
    quantidade: int
    origem: str

    @property
    def compartilhada(self) -> bool:
        return len(self.requisito_ids) == 2


@dataclass(frozen=True)
class PendenciaAlocacao:
    evidencia_id: str
    unidade: UnidadeRequisito
    quantidade: int
    candidatos: tuple[str, ...]
    motivo: str


@dataclass(frozen=True)
class ResultadoAlocacao:
    alocacoes: tuple[AlocacaoRealizada, ...]
    pendencias: tuple[PendenciaAlocacao, ...]
    evidencias_sem_destino: tuple[tuple[str, UnidadeRequisito, int], ...]
    medicoes: Mapping[str, MedicaoRequisito]
    compartilhamentos_usados: Mapping[frozenset[str], int]
    bloqueios: tuple[str, ...] = ()

    @property
    def pronta_para_avaliacao(self) -> bool:
        return not self.bloqueios


@dataclass(frozen=True)
class AvaliacaoComEvidencias:
    alocacao: ResultadoAlocacao
    avaliacao: ResultadoAvaliacaoModelo | None


def evidencia_atende_seletor(
    evidencia: EvidenciaAcademica,
    seletor: SeletorComponentes,
) -> bool:
    """Aplica somente critérios estruturados; nunca compara nomes."""

    if seletor.qualquer_componente:
        return True

    criterios: list[bool] = []
    if seletor.codigos:
        criterios.append(bool(evidencia.codigos & seletor.codigos))
    if seletor.categorias:
        criterios.append(bool(evidencia.categorias & seletor.categorias))
    if seletor.tipos:
        criterios.append(bool(evidencia.tipos & seletor.tipos))
    if seletor.tags:
        criterios.append(bool(evidencia.tags & seletor.tags))
    if seletor.origens:
        criterios.append(bool(evidencia.origens & seletor.origens))

    if seletor.operador == OperadorSeletor.TODOS_CRITERIOS:
        return all(criterios)
    if seletor.operador == OperadorSeletor.QUALQUER_CRITERIO:
        return any(criterios)
    return False


def requisitos_candidatos(
    modelo: ModeloRequisitosCurriculares,
    evidencia: EvidenciaAcademica,
    unidade: UnidadeRequisito,
) -> tuple[str, ...]:
    return tuple(
        requisito.id
        for requisito in modelo.requisitos
        if requisito.limite.unidade == unidade
        and evidencia_atende_seletor(evidencia, requisito.seletor)
    )


def alocar_evidencias(
    modelo: ModeloRequisitosCurriculares,
    conjunto: ConjuntoEvidencias,
    decisoes: tuple[DecisaoAlocacao, ...] = (),
) -> ResultadoAlocacao:
    """Aloca automaticamente apenas evidências sem ambiguidade.

    Quando uma quantidade pode alimentar mais de um requisito independente, ela
    permanece pendente até existir uma decisão explícita. Uma decisão que reutiliza
    a mesma quantidade em dois requisitos exige compartilhamento cadastrado.
    """

    evidencias = conjunto.por_id
    requisitos = {item.id: item for item in modelo.requisitos}
    contribuicoes_por_total: dict[str, list] = {}
    for contribuicao in modelo.contribuicoes:
        contribuicoes_por_total.setdefault(contribuicao.requisito_total, []).append(
            contribuicao
        )

    decisoes_por_chave: dict[tuple[str, UnidadeRequisito], list[DecisaoAlocacao]] = {}
    for decisao in decisoes:
        if decisao.evidencia_id not in evidencias:
            raise ValueError(
                f"Decisão referencia evidência inexistente: {decisao.evidencia_id}."
            )
        evidencia = evidencias[decisao.evidencia_id]
        if (
            decisao.unidade not in evidencia.quantidades
            or evidencia.quantidade(decisao.unidade) <= 0
        ):
            raise ValueError(
                f"Decisão usa {decisao.unidade.value}, mas a evidência "
                f"{evidencia.id} não possui quantidade positiva nessa unidade."
            )
        decisoes_por_chave.setdefault(
            (decisao.evidencia_id, decisao.unidade), []
        ).append(decisao)

    regras_compartilhamento = {
        regra.par: regra for regra in modelo.compartilhamentos
    }
    compartilhamentos_usados: dict[frozenset[str], int] = {}
    realizadas: list[AlocacaoRealizada] = []
    pendencias: list[PendenciaAlocacao] = []
    sem_destino: list[tuple[str, UnidadeRequisito, int]] = []

    for evidencia in conjunto.evidencias:
        for unidade, disponivel in evidencia.quantidades.items():
            if disponivel <= 0:
                continue
            candidatos = requisitos_candidatos(modelo, evidencia, unidade)
            explicitas = decisoes_por_chave.get((evidencia.id, unidade), [])
            consumido = 0

            for decisao in explicitas:
                if decisao.quantidade + consumido > disponivel:
                    raise ValueError(
                        f"Alocação de {evidencia.id} excede a quantidade disponível "
                        f"em {unidade.value}."
                    )
                inexistentes = set(decisao.requisito_ids) - set(candidatos)
                if inexistentes:
                    raise ValueError(
                        "Decisão tenta alocar evidência a requisito cujo seletor "
                        f"não a reconhece: {', '.join(sorted(inexistentes))}."
                    )
                if len(decisao.requisito_ids) == 2:
                    par = frozenset(decisao.requisito_ids)
                    regra = regras_compartilhamento.get(par)
                    if regra is None or regra.unidade != unidade:
                        raise ValueError(
                            "Reutilização da mesma evidência exige regra explícita "
                            "de compartilhamento na mesma unidade."
                        )
                    novo_total = compartilhamentos_usados.get(par, 0) + decisao.quantidade
                    if novo_total > regra.maximo_compartilhavel:
                        raise ValueError(
                            "Alocação compartilhada excede o máximo permitido pela regra."
                        )
                    compartilhamentos_usados[par] = novo_total
                realizadas.append(
                    AlocacaoRealizada(
                        evidencia.id,
                        unidade,
                        decisao.requisito_ids,
                        decisao.quantidade,
                        "explicita",
                    )
                )
                consumido += decisao.quantidade

            restante = disponivel - consumido
            if restante <= 0:
                continue
            if len(candidatos) == 1:
                realizadas.append(
                    AlocacaoRealizada(
                        evidencia.id,
                        unidade,
                        candidatos,
                        restante,
                        "automatica",
                    )
                )
            elif len(candidatos) > 1:
                pendencias.append(
                    PendenciaAlocacao(
                        evidencia.id,
                        unidade,
                        restante,
                        candidatos,
                        "A evidência atende mais de um requisito; não há escolha "
                        "automática entre destinos acadêmicos concorrentes.",
                    )
                )
            else:
                sem_destino.append((evidencia.id, unidade, restante))

    somas: dict[str, int] = {item.id: 0 for item in modelo.requisitos}
    somas.update({item.id: 0 for item in modelo.contribuicoes})

    for alocacao in realizadas:
        evidencia = evidencias[alocacao.evidencia_id]
        for requisito_id in alocacao.requisito_ids:
            somas[requisito_id] += alocacao.quantidade
            for contribuicao in contribuicoes_por_total.get(requisito_id, []):
                if (
                    contribuicao.limite.unidade == alocacao.unidade
                    and evidencia_atende_seletor(evidencia, contribuicao.seletor)
                ):
                    # Contribuição é uma parcela interna do total e não consome a
                    # evidência uma segunda vez.
                    somas[contribuicao.id] += alocacao.quantidade

    regras_incompletas: set[str] = set()
    for pendencia in pendencias:
        evidencia = evidencias[pendencia.evidencia_id]
        for requisito_id in pendencia.candidatos:
            regras_incompletas.add(requisito_id)
            for contribuicao in contribuicoes_por_total.get(requisito_id, []):
                if (
                    contribuicao.limite.unidade == pendencia.unidade
                    and evidencia_atende_seletor(evidencia, contribuicao.seletor)
                ):
                    regras_incompletas.add(contribuicao.id)

    medicoes: dict[str, MedicaoRequisito] = {}
    for requisito in modelo.requisitos:
        medicoes[requisito.id] = MedicaoRequisito(
            requisito_id=requisito.id,
            unidade=requisito.limite.unidade,
            valor=somas[requisito.id],
            dados_completos=(
                requisito.limite.unidade in conjunto.unidades_completas
                and requisito.id not in regras_incompletas
            ),
        )
    for contribuicao in modelo.contribuicoes:
        medicoes[contribuicao.id] = MedicaoRequisito(
            requisito_id=contribuicao.id,
            unidade=contribuicao.limite.unidade,
            valor=somas[contribuicao.id],
            dados_completos=(
                contribuicao.limite.unidade in conjunto.unidades_completas
                and contribuicao.id not in regras_incompletas
            ),
        )

    bloqueios: list[str] = []
    for regra in modelo.compartilhamentos:
        if regra.minimo_compartilhavel <= 0:
            continue
        usado = compartilhamentos_usados.get(regra.par, 0)
        if usado < regra.minimo_compartilhavel:
            bloqueios.append(
                "Compartilhamento mínimo obrigatório não comprovado entre "
                f"{regra.requisito_a} e {regra.requisito_b}: "
                f"{usado}/{regra.minimo_compartilhavel} {regra.unidade.value}."
            )

    return ResultadoAlocacao(
        alocacoes=tuple(realizadas),
        pendencias=tuple(pendencias),
        evidencias_sem_destino=tuple(sem_destino),
        medicoes=medicoes,
        compartilhamentos_usados=compartilhamentos_usados,
        bloqueios=tuple(bloqueios),
    )


def avaliar_modelo_com_evidencias(
    modelo: ModeloRequisitosCurriculares,
    conjunto: ConjuntoEvidencias,
    decisoes: tuple[DecisaoAlocacao, ...] = (),
    *,
    atributos: Mapping[str, ValorCondicao] | None = None,
    sequencias_confirmadas: Mapping[str, bool | None] | None = None,
    cursos_base_concluidos: Mapping[tuple[str, str], bool | None] | None = None,
) -> AvaliacaoComEvidencias:
    """Liga alocação e avaliador sem ocultar bloqueios de compartilhamento."""

    alocacao = alocar_evidencias(modelo, conjunto, decisoes)
    if not alocacao.pronta_para_avaliacao:
        return AvaliacaoComEvidencias(alocacao=alocacao, avaliacao=None)

    contexto = ContextoAvaliacaoCurricular(
        medicoes=alocacao.medicoes,
        atributos=atributos or {},
        sequencias_confirmadas=sequencias_confirmadas or {},
        cursos_base_concluidos=cursos_base_concluidos or {},
    )
    return AvaliacaoComEvidencias(
        alocacao=alocacao,
        avaliacao=avaliar_modelo_requisitos(modelo, contexto),
    )
