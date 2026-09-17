from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .requisitos_curriculares import (
    CondicaoCurricular,
    GrupoRequisitos,
    ModeloRequisitosCurriculares,
    OperadorCondicao,
    OperadorGrupo,
    RegraCondicional,
    RestricaoContribuicao,
    SequenciaRequisitos,
    UnidadeRequisito,
    ValorCondicao,
)


class EstadoAvaliacao(str, Enum):
    CUMPRIDO = "cumprido"
    PENDENTE = "pendente"
    INDETERMINADO = "indeterminado"


class EstadoAplicabilidade(str, Enum):
    APLICAVEL = "aplicavel"
    NAO_APLICAVEL = "nao_aplicavel"
    INDETERMINADA = "indeterminada"


@dataclass(frozen=True)
class MedicaoRequisito:
    """Quantidade já atribuída a uma regra curricular.

    O reconhecimento e a alocação de evidências acontecem antes deste módulo.
    O avaliador, portanto, não inventa equivalências nem compartilha carga por
    conta própria.
    """

    requisito_id: str
    unidade: UnidadeRequisito
    valor: int | None
    dados_completos: bool = True
    observacoes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.requisito_id.strip():
            raise ValueError("Medição precisa indicar requisito_id.")
        if self.valor is not None:
            if type(self.valor) is not int:
                raise ValueError("Valor medido deve ser inteiro ou None.")
            if self.valor < 0:
                raise ValueError("Valor medido não pode ser negativo.")


@dataclass(frozen=True)
class ContextoAvaliacaoCurricular:
    medicoes: Mapping[str, MedicaoRequisito] = field(default_factory=dict)
    atributos: Mapping[str, ValorCondicao] = field(default_factory=dict)
    sequencias_confirmadas: Mapping[str, bool | None] = field(default_factory=dict)
    cursos_base_concluidos: Mapping[tuple[str, str], bool | None] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ResultadoRegra:
    regra_id: str
    tipo: str
    estado: EstadoAvaliacao
    motivos: tuple[str, ...] = ()
    valor_observado: int | None = None
    valor_considerado: int | None = None
    minimo_exigido: int | None = None
    maximo_consideravel: int | None = None
    unidade: UnidadeRequisito | None = None


@dataclass(frozen=True)
class ResultadoAvaliacaoModelo:
    curso_id: str
    matriz_id: str
    aplicabilidade: EstadoAplicabilidade
    estado: EstadoAvaliacao | None
    resultados: tuple[ResultadoRegra, ...]
    regras_raiz: tuple[str, ...]
    motivos: tuple[str, ...] = ()

    @property
    def por_id(self) -> dict[str, ResultadoRegra]:
        return {item.regra_id: item for item in self.resultados}


def avaliar_modelo_requisitos(
    modelo: ModeloRequisitosCurriculares,
    contexto: ContextoAvaliacaoCurricular,
) -> ResultadoAvaliacaoModelo:
    """Avalia regras sem converter ausência de dados em pendência."""

    aplicabilidade = _avaliar_aplicabilidade(modelo, contexto)
    if aplicabilidade == EstadoAplicabilidade.NAO_APLICAVEL:
        return ResultadoAvaliacaoModelo(
            modelo.curso_id,
            modelo.matriz_id,
            aplicabilidade,
            None,
            (),
            (),
            ("O modelo não se aplica ao contexto informado.",),
        )
    if aplicabilidade == EstadoAplicabilidade.INDETERMINADA:
        return ResultadoAvaliacaoModelo(
            modelo.curso_id,
            modelo.matriz_id,
            aplicabilidade,
            EstadoAvaliacao.INDETERMINADO,
            (),
            (),
            ("Faltam dados para decidir a aplicabilidade do modelo.",),
        )

    requisitos = {item.id: item for item in modelo.requisitos}
    grupos = {item.id: item for item in modelo.grupos}
    condicionais = {item.id: item for item in modelo.condicionais}
    sequencias = {item.id: item for item in modelo.sequencias}
    contribuicoes_por_total: dict[str, list[RestricaoContribuicao]] = {}
    for item in modelo.contribuicoes:
        contribuicoes_por_total.setdefault(item.requisito_total, []).append(item)

    resultados: dict[str, ResultadoRegra] = {}

    def avaliar_regra(regra_id: str) -> ResultadoRegra:
        if regra_id in resultados:
            return resultados[regra_id]

        if regra_id in requisitos:
            requisito = requisitos[regra_id]
            base = _avaliar_medicao(
                regra_id=requisito.id,
                tipo="requisito",
                unidade=requisito.limite.unidade,
                minimo=requisito.limite.minimo,
                maximo=requisito.limite.maximo,
                contexto=contexto,
            )
            parcelas = []
            for contribuicao in contribuicoes_por_total.get(regra_id, []):
                parcial = _avaliar_contribuicao(contribuicao, contexto)
                resultados[contribuicao.id] = parcial
                if contribuicao.limite.minimo > 0:
                    parcelas.append(parcial)
            if parcelas:
                estado = _combinar_todos(
                    [base.estado, *(item.estado for item in parcelas)]
                )
                base = ResultadoRegra(
                    regra_id=base.regra_id,
                    tipo=base.tipo,
                    estado=estado,
                    motivos=(
                        *base.motivos,
                        "As restrições mínimas de composição também foram avaliadas.",
                    ),
                    valor_observado=base.valor_observado,
                    valor_considerado=base.valor_considerado,
                    minimo_exigido=base.minimo_exigido,
                    maximo_consideravel=base.maximo_consideravel,
                    unidade=base.unidade,
                )
            resultado = base
        elif regra_id in grupos:
            resultado = _avaliar_grupo(grupos[regra_id], avaliar_regra)
        elif regra_id in sequencias:
            resultado = _avaliar_sequencia(
                sequencias[regra_id], avaliar_regra, contexto
            )
        elif regra_id in condicionais:
            resultado = _avaliar_condicional(
                condicionais[regra_id], avaliar_regra, contexto
            )
        else:
            raise ValueError(f"Regra curricular inexistente: {regra_id}")

        resultados[regra_id] = resultado
        return resultado

    referencias = _ids_referenciados(modelo)
    candidatos_raiz = [
        *(item.id for item in modelo.requisitos),
        *(item.id for item in modelo.grupos),
        *(item.id for item in modelo.condicionais),
        *(item.id for item in modelo.sequencias),
    ]
    regras_raiz = [item for item in candidatos_raiz if item not in referencias]

    estados_finais = [avaliar_regra(item).estado for item in regras_raiz]

    curso_base_ids: list[str] = []
    for referencia in modelo.cursos_base:
        if not referencia.exigir_conclusao_base:
            continue
        regra_id = f"curso_base:{referencia.curso_id}:{referencia.matriz_id}"
        conclusao = contexto.cursos_base_concluidos.get(
            (referencia.curso_id, referencia.matriz_id)
        )
        if conclusao is True:
            estado = EstadoAvaliacao.CUMPRIDO
            motivos = ("Conclusão do curso-base confirmada no contexto.",)
        elif conclusao is False:
            estado = EstadoAvaliacao.PENDENTE
            motivos = ("Conclusão obrigatória do curso-base ainda não ocorreu.",)
        else:
            estado = EstadoAvaliacao.INDETERMINADO
            motivos = ("Não há confirmação sobre a conclusão do curso-base.",)
        resultados[regra_id] = ResultadoRegra(
            regra_id=regra_id,
            tipo="curso_base",
            estado=estado,
            motivos=motivos,
        )
        curso_base_ids.append(regra_id)
        estados_finais.append(estado)

    if not estados_finais:
        estado = EstadoAvaliacao.INDETERMINADO
        motivos_modelo = ("Modelo sem regras avaliáveis no nível raiz.",)
    else:
        estado = _combinar_todos(estados_finais)
        motivos_modelo = ()

    return ResultadoAvaliacaoModelo(
        curso_id=modelo.curso_id,
        matriz_id=modelo.matriz_id,
        aplicabilidade=aplicabilidade,
        estado=estado,
        resultados=tuple(resultados.values()),
        regras_raiz=tuple([*regras_raiz, *curso_base_ids]),
        motivos=motivos_modelo,
    )


def avaliar_condicao(
    condicao: CondicaoCurricular,
    atributos: Mapping[str, ValorCondicao],
) -> bool | None:
    if condicao.campo not in atributos:
        return None
    atual = atributos[condicao.campo]
    esperado = condicao.valor

    if condicao.operador == OperadorCondicao.IGUAL:
        return atual == esperado
    if condicao.operador == OperadorCondicao.DIFERENTE:
        return atual != esperado
    if condicao.operador == OperadorCondicao.CONTEM:
        if not isinstance(atual, (str, tuple, list, set, frozenset)):
            return None
        try:
            if isinstance(esperado, tuple):
                return all(item in atual for item in esperado)
            return esperado in atual
        except TypeError:
            return None
    if condicao.operador in {
        OperadorCondicao.MAIOR_OU_IGUAL,
        OperadorCondicao.MENOR_OU_IGUAL,
    }:
        if isinstance(atual, bool) or isinstance(esperado, bool):
            return None
        try:
            if condicao.operador == OperadorCondicao.MAIOR_OU_IGUAL:
                return atual >= esperado
            return atual <= esperado
        except TypeError:
            return None
    return None


def _avaliar_aplicabilidade(
    modelo: ModeloRequisitosCurriculares,
    contexto: ContextoAvaliacaoCurricular,
) -> EstadoAplicabilidade:
    if not modelo.aplicabilidade:
        return EstadoAplicabilidade.APLICAVEL

    valores: list[bool | None] = []
    for regra in modelo.aplicabilidade:
        valores.extend(
            avaliar_condicao(condicao, contexto.atributos)
            for condicao in regra.condicoes
        )
    if any(valor is False for valor in valores):
        return EstadoAplicabilidade.NAO_APLICAVEL
    if any(valor is None for valor in valores):
        return EstadoAplicabilidade.INDETERMINADA
    return EstadoAplicabilidade.APLICAVEL


def _avaliar_medicao(
    *,
    regra_id: str,
    tipo: str,
    unidade: UnidadeRequisito,
    minimo: int,
    maximo: int | None,
    contexto: ContextoAvaliacaoCurricular,
) -> ResultadoRegra:
    if minimo == 0:
        return ResultadoRegra(
            regra_id=regra_id,
            tipo=tipo,
            estado=EstadoAvaliacao.CUMPRIDO,
            motivos=("O requisito não exige quantidade mínima.",),
            valor_observado=0,
            valor_considerado=0,
            minimo_exigido=0,
            maximo_consideravel=maximo,
            unidade=unidade,
        )

    medicao = contexto.medicoes.get(regra_id)
    if medicao is None:
        return ResultadoRegra(
            regra_id=regra_id,
            tipo=tipo,
            estado=EstadoAvaliacao.INDETERMINADO,
            motivos=("Não há medição para este requisito.",),
            minimo_exigido=minimo,
            maximo_consideravel=maximo,
            unidade=unidade,
        )
    if medicao.requisito_id != regra_id:
        raise ValueError(
            f"Medição registrada em {regra_id} declara id {medicao.requisito_id}."
        )
    if medicao.unidade != unidade:
        raise ValueError(
            f"Medição de {regra_id} usa {medicao.unidade.value}, "
            f"mas a regra exige {unidade.value}."
        )
    if medicao.valor is None:
        return ResultadoRegra(
            regra_id=regra_id,
            tipo=tipo,
            estado=EstadoAvaliacao.INDETERMINADO,
            motivos=("A quantidade deste requisito ainda não foi determinada.",),
            minimo_exigido=minimo,
            maximo_consideravel=maximo,
            unidade=unidade,
        )

    considerado = medicao.valor if maximo is None else min(medicao.valor, maximo)
    if considerado >= minimo:
        estado = EstadoAvaliacao.CUMPRIDO
        motivos = ("Quantidade mínima comprovada.",)
    elif medicao.dados_completos:
        estado = EstadoAvaliacao.PENDENTE
        motivos = ("Quantidade comprovada abaixo do mínimo exigido.",)
    else:
        estado = EstadoAvaliacao.INDETERMINADO
        motivos = (
            "Quantidade conhecida abaixo do mínimo, mas os dados estão incompletos.",
        )

    if maximo is not None and medicao.valor > maximo:
        motivos = (*motivos, "Valor excedente foi desconsiderado pelo teto da regra.")

    return ResultadoRegra(
        regra_id=regra_id,
        tipo=tipo,
        estado=estado,
        motivos=motivos,
        valor_observado=medicao.valor,
        valor_considerado=considerado,
        minimo_exigido=minimo,
        maximo_consideravel=maximo,
        unidade=unidade,
    )


def _avaliar_contribuicao(
    contribuicao: RestricaoContribuicao,
    contexto: ContextoAvaliacaoCurricular,
) -> ResultadoRegra:
    return _avaliar_medicao(
        regra_id=contribuicao.id,
        tipo="contribuicao",
        unidade=contribuicao.limite.unidade,
        minimo=contribuicao.limite.minimo,
        maximo=contribuicao.limite.maximo,
        contexto=contexto,
    )


def _avaliar_grupo(grupo: GrupoRequisitos, avaliar_regra) -> ResultadoRegra:
    filhos = [avaliar_regra(item) for item in grupo.requisitos]
    minimo = _minimo_grupo(grupo)
    cumpridos = sum(item.estado == EstadoAvaliacao.CUMPRIDO for item in filhos)
    indeterminados = sum(
        item.estado == EstadoAvaliacao.INDETERMINADO for item in filhos
    )

    if cumpridos >= minimo:
        estado = EstadoAvaliacao.CUMPRIDO
        motivo = f"{cumpridos} requisito(s) confirmado(s); mínimo {minimo}."
    elif cumpridos + indeterminados < minimo:
        estado = EstadoAvaliacao.PENDENTE
        motivo = (
            f"Mesmo resolvendo todas as incertezas, o grupo não alcança o mínimo {minimo}."
        )
    else:
        estado = EstadoAvaliacao.INDETERMINADO
        motivo = f"O grupo depende de {indeterminados} resultado(s) indeterminado(s)."

    return ResultadoRegra(
        regra_id=grupo.id,
        tipo="grupo",
        estado=estado,
        motivos=(motivo,),
        valor_observado=cumpridos,
        valor_considerado=cumpridos,
        minimo_exigido=minimo,
        unidade=UnidadeRequisito.COMPONENTES,
    )


def _avaliar_condicional(
    regra: RegraCondicional,
    avaliar_regra,
    contexto: ContextoAvaliacaoCurricular,
) -> ResultadoRegra:
    valor = avaliar_condicao(regra.condicao, contexto.atributos)

    def estado_ramo(ids: tuple[str, ...]) -> EstadoAvaliacao:
        return _combinar_todos([avaliar_regra(item).estado for item in ids])

    if valor is True:
        estado = estado_ramo(regra.requisitos_se_verdadeira)
        motivo = "Condição verdadeira; somente o ramo verdadeiro foi exigido."
    elif valor is False:
        estado = estado_ramo(regra.requisitos_se_falsa)
        motivo = "Condição falsa; somente o ramo falso foi exigido."
    else:
        estado_verdadeiro = estado_ramo(regra.requisitos_se_verdadeira)
        estado_falso = estado_ramo(regra.requisitos_se_falsa)
        if estado_verdadeiro == estado_falso:
            estado = estado_verdadeiro
            motivo = "Condição não determinada, mas os dois ramos têm o mesmo estado."
        else:
            estado = EstadoAvaliacao.INDETERMINADO
            motivo = "Condição curricular sem dado suficiente para selecionar o ramo."

    return ResultadoRegra(
        regra_id=regra.id,
        tipo="condicional",
        estado=estado,
        motivos=(motivo,),
    )


def _avaliar_sequencia(
    sequencia: SequenciaRequisitos,
    avaliar_regra,
    contexto: ContextoAvaliacaoCurricular,
) -> ResultadoRegra:
    estado_etapas = _combinar_todos(
        [avaliar_regra(item).estado for item in sequencia.etapas]
    )
    if estado_etapas != EstadoAvaliacao.CUMPRIDO or not sequencia.ordem_obrigatoria:
        return ResultadoRegra(
            regra_id=sequencia.id,
            tipo="sequencia",
            estado=estado_etapas,
            motivos=("Estado derivado das etapas da sequência.",),
        )

    confirmada = contexto.sequencias_confirmadas.get(sequencia.id)
    if confirmada is True:
        estado = EstadoAvaliacao.CUMPRIDO
        motivo = "Etapas e ordem obrigatória foram confirmadas."
    elif confirmada is False:
        estado = EstadoAvaliacao.PENDENTE
        motivo = "As etapas existem, mas a ordem obrigatória não foi cumprida."
    else:
        estado = EstadoAvaliacao.INDETERMINADO
        motivo = "As etapas existem, mas não há evidência sobre a ordem obrigatória."
    return ResultadoRegra(
        regra_id=sequencia.id,
        tipo="sequencia",
        estado=estado,
        motivos=(motivo,),
    )


def _ids_referenciados(modelo: ModeloRequisitosCurriculares) -> set[str]:
    referencias: set[str] = set()
    for grupo in modelo.grupos:
        referencias.update(grupo.requisitos)
    for regra in modelo.condicionais:
        referencias.update(regra.requisitos_se_verdadeira)
        referencias.update(regra.requisitos_se_falsa)
    for sequencia in modelo.sequencias:
        referencias.update(sequencia.etapas)
    return referencias


def _minimo_grupo(grupo: GrupoRequisitos) -> int:
    if grupo.operador == OperadorGrupo.TODOS:
        return len(grupo.requisitos)
    if grupo.operador == OperadorGrupo.QUALQUER:
        return 1
    assert grupo.minimo_requisitos is not None
    return grupo.minimo_requisitos


def _combinar_todos(estados: list[EstadoAvaliacao]) -> EstadoAvaliacao:
    if not estados:
        return EstadoAvaliacao.CUMPRIDO
    if EstadoAvaliacao.PENDENTE in estados:
        return EstadoAvaliacao.PENDENTE
    if EstadoAvaliacao.INDETERMINADO in estados:
        return EstadoAvaliacao.INDETERMINADO
    return EstadoAvaliacao.CUMPRIDO
