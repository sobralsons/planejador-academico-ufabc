from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


ValorCondicao = str | int | float | bool | tuple[str, ...]


class UnidadeRequisito(str, Enum):
    CREDITOS = "creditos"
    HORAS = "horas"
    COMPONENTES = "componentes"


class TipoIntegralizador(str, Enum):
    COMPONENTES_CURRICULARES = "componentes_curriculares"
    GRUPO_ESCOLHA = "grupo_escolha"
    ESTAGIO = "estagio"
    TCC = "tcc"
    EXTENSAO = "extensao"
    ATIVIDADES_COMPLEMENTARES = "atividades_complementares"
    FORMACAO_DOCENTE = "formacao_docente"
    CURSO_BASE = "curso_base"
    OUTRO = "outro"


class OperadorSeletor(str, Enum):
    TODOS_CRITERIOS = "todos_criterios"
    QUALQUER_CRITERIO = "qualquer_criterio"


class OperadorGrupo(str, Enum):
    TODOS = "todos"
    QUALQUER = "qualquer"
    MINIMO = "minimo"


class OperadorCondicao(str, Enum):
    IGUAL = "igual"
    DIFERENTE = "diferente"
    CONTEM = "contem"
    MAIOR_OU_IGUAL = "maior_ou_igual"
    MENOR_OU_IGUAL = "menor_ou_igual"


@dataclass(frozen=True)
class FonteRegra:
    """Proveniência de uma regra curricular.

    ``referencia`` pode guardar artigo, seção, anexo ou página. ``trecho`` deve
    ser curto e serve apenas para auditoria humana; a fonte oficial continua
    sendo a autoridade.
    """

    titulo: str
    url: str
    referencia: str = ""
    trecho: str = ""

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ValueError("Fonte de regra precisa de título.")
        if not self.url.startswith("https://"):
            raise ValueError("Fonte de regra deve usar URL HTTPS.")


@dataclass(frozen=True)
class SeletorComponentes:
    """Descreve quais evidências acadêmicas podem satisfazer um requisito."""

    codigos: frozenset[str] = frozenset()
    categorias: frozenset[str] = frozenset()
    tipos: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    origens: frozenset[str] = frozenset()
    qualquer_componente: bool = False
    operador: OperadorSeletor = OperadorSeletor.TODOS_CRITERIOS

    def __post_init__(self) -> None:
        if self.qualquer_componente and any(
            (self.codigos, self.categorias, self.tipos, self.tags, self.origens)
        ):
            raise ValueError(
                "qualquer_componente=True não pode ser combinado com critérios."
            )
        if not self.qualquer_componente and not any(
            (self.codigos, self.categorias, self.tipos, self.tags, self.origens)
        ):
            raise ValueError(
                "Seletor precisa de ao menos um critério ou qualquer_componente=True."
            )


@dataclass(frozen=True)
class LimiteQuantitativo:
    unidade: UnidadeRequisito
    minimo: int
    maximo: int | None = None

    def __post_init__(self) -> None:
        if self.minimo < 0:
            raise ValueError("Mínimo do requisito não pode ser negativo.")
        if self.maximo is not None:
            if self.maximo < 0:
                raise ValueError("Máximo do requisito não pode ser negativo.")
            if self.maximo < self.minimo:
                raise ValueError("Máximo do requisito não pode ser menor que o mínimo.")


@dataclass(frozen=True)
class RequisitoQuantitativo:
    """Requisito mensurável em créditos, horas ou número de componentes."""

    id: str
    descricao: str
    integralizador: TipoIntegralizador
    seletor: SeletorComponentes
    limite: LimiteQuantitativo
    fontes: tuple[FonteRegra, ...] = ()
    observacoes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validar_id(self.id)
        if not self.descricao.strip():
            raise ValueError(f"Requisito {self.id} precisa de descrição.")


@dataclass(frozen=True)
class GrupoRequisitos:
    """Combina requisitos sem misturar a regra de escolha ao cadastro de disciplinas."""

    id: str
    descricao: str
    requisitos: tuple[str, ...]
    operador: OperadorGrupo
    minimo_requisitos: int | None = None
    maximo_requisitos: int | None = None
    fontes: tuple[FonteRegra, ...] = ()

    def __post_init__(self) -> None:
        _validar_id(self.id)
        if not self.descricao.strip():
            raise ValueError(f"Grupo {self.id} precisa de descrição.")
        if not self.requisitos:
            raise ValueError(f"Grupo {self.id} precisa referenciar requisitos.")
        if len(set(self.requisitos)) != len(self.requisitos):
            raise ValueError(f"Grupo {self.id} contém requisito duplicado.")

        total = len(self.requisitos)
        if self.operador == OperadorGrupo.TODOS:
            minimo = total
        elif self.operador == OperadorGrupo.QUALQUER:
            minimo = 1
        else:
            if self.minimo_requisitos is None:
                raise ValueError(
                    f"Grupo {self.id} com operador mínimo exige minimo_requisitos."
                )
            minimo = self.minimo_requisitos

        if minimo < 1 or minimo > total:
            raise ValueError(f"Mínimo inválido no grupo {self.id}.")
        if self.maximo_requisitos is not None:
            if self.maximo_requisitos < minimo or self.maximo_requisitos > total:
                raise ValueError(f"Máximo inválido no grupo {self.id}.")


@dataclass(frozen=True)
class CondicaoCurricular:
    """Condição declarativa; este módulo não decide como ela é avaliada."""

    campo: str
    operador: OperadorCondicao
    valor: ValorCondicao

    def __post_init__(self) -> None:
        if not self.campo.strip():
            raise ValueError("Condição curricular precisa indicar o campo avaliado.")


@dataclass(frozen=True)
class RegraCondicional:
    id: str
    descricao: str
    condicao: CondicaoCurricular
    requisitos_se_verdadeira: tuple[str, ...]
    requisitos_se_falsa: tuple[str, ...] = ()
    fontes: tuple[FonteRegra, ...] = ()

    def __post_init__(self) -> None:
        _validar_id(self.id)
        if not self.descricao.strip():
            raise ValueError(f"Regra condicional {self.id} precisa de descrição.")
        if not self.requisitos_se_verdadeira and not self.requisitos_se_falsa:
            raise ValueError(
                f"Regra condicional {self.id} precisa ativar ao menos um requisito."
            )


@dataclass(frozen=True)
class SequenciaRequisitos:
    """Relaciona etapas sem presumir que a ordem seja pré-requisito acadêmico."""

    id: str
    descricao: str
    etapas: tuple[str, ...]
    ordem_obrigatoria: bool = False
    fontes: tuple[FonteRegra, ...] = ()

    def __post_init__(self) -> None:
        _validar_id(self.id)
        if not self.descricao.strip():
            raise ValueError(f"Sequência {self.id} precisa de descrição.")
        if len(self.etapas) < 2:
            raise ValueError(f"Sequência {self.id} precisa de ao menos duas etapas.")
        if len(set(self.etapas)) != len(self.etapas):
            raise ValueError(f"Sequência {self.id} contém etapa duplicada.")


@dataclass(frozen=True)
class RegraCompartilhamento:
    """Exceção explícita ao padrão de não contar a mesma evidência duas vezes."""

    requisito_a: str
    requisito_b: str
    unidade: UnidadeRequisito
    maximo_compartilhavel: int
    fontes: tuple[FonteRegra, ...] = ()
    observacao: str = ""

    def __post_init__(self) -> None:
        if self.requisito_a == self.requisito_b:
            raise ValueError("Compartilhamento exige dois requisitos distintos.")
        if self.maximo_compartilhavel <= 0:
            raise ValueError("Máximo compartilhável precisa ser positivo.")

    @property
    def par(self) -> frozenset[str]:
        return frozenset((self.requisito_a, self.requisito_b))


@dataclass(frozen=True)
class ReferenciaCursoBase:
    """Relaciona uma matriz específica a requisitos provenientes de outro curso."""

    curso_id: str
    matriz_id: str
    requisitos_reutilizados: tuple[str, ...] = ()
    exigir_conclusao_base: bool = False
    permitir_reuso_de_componentes: bool = True
    fontes: tuple[FonteRegra, ...] = ()

    def __post_init__(self) -> None:
        if not self.curso_id.strip() or not self.matriz_id.strip():
            raise ValueError("Referência ao curso-base exige curso_id e matriz_id.")
        if len(set(self.requisitos_reutilizados)) != len(self.requisitos_reutilizados):
            raise ValueError("Referência ao curso-base contém requisito duplicado.")


@dataclass(frozen=True)
class RegraAplicabilidade:
    """Restringe quando uma regra/matriz deve ser considerada, sem inferir vigência."""

    id: str
    descricao: str
    condicoes: tuple[CondicaoCurricular, ...]
    fontes: tuple[FonteRegra, ...] = ()

    def __post_init__(self) -> None:
        _validar_id(self.id)
        if not self.descricao.strip():
            raise ValueError(f"Aplicabilidade {self.id} precisa de descrição.")
        if not self.condicoes:
            raise ValueError(f"Aplicabilidade {self.id} precisa de condições.")


@dataclass(frozen=True)
class ModeloRequisitosCurriculares:
    """Contrato genérico de regras curriculares.

    Nesta etapa o objeto apenas representa e valida a estrutura das regras.
    Ele ainda não altera integralização, planejamento, ranking nem solver.
    """

    curso_id: str
    matriz_id: str
    requisitos: tuple[RequisitoQuantitativo, ...]
    grupos: tuple[GrupoRequisitos, ...] = ()
    condicionais: tuple[RegraCondicional, ...] = ()
    sequencias: tuple[SequenciaRequisitos, ...] = ()
    compartilhamentos: tuple[RegraCompartilhamento, ...] = ()
    cursos_base: tuple[ReferenciaCursoBase, ...] = ()
    aplicabilidade: tuple[RegraAplicabilidade, ...] = ()
    fontes_gerais: tuple[FonteRegra, ...] = ()
    compartilhamento_padrao_proibido: bool = True
    metadados: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.curso_id.strip() or not self.matriz_id.strip():
            raise ValueError("Modelo curricular exige curso_id e matriz_id.")

        ids = [
            *(item.id for item in self.requisitos),
            *(item.id for item in self.grupos),
            *(item.id for item in self.condicionais),
            *(item.id for item in self.sequencias),
            *(item.id for item in self.aplicabilidade),
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de regras curriculares devem ser únicos.")

        ids_requisitos = {item.id for item in self.requisitos}
        ids_grupos = {item.id for item in self.grupos}
        ids_sequencias = {item.id for item in self.sequencias}

        for grupo in self.grupos:
            _validar_referencias(
                grupo.id, grupo.requisitos, ids_requisitos | ids_grupos
            )
            if grupo.id in grupo.requisitos:
                raise ValueError(f"Grupo {grupo.id} não pode referenciar a si mesmo.")
        _validar_ciclos_grupos(self.grupos, ids_grupos)

        for condicional in self.condicionais:
            _validar_referencias(
                condicional.id,
                condicional.requisitos_se_verdadeira
                + condicional.requisitos_se_falsa,
                ids_requisitos | ids_grupos | ids_sequencias,
            )

        for sequencia in self.sequencias:
            _validar_referencias(
                sequencia.id, sequencia.etapas, ids_requisitos | ids_grupos
            )

        pares_compartilhamento: set[frozenset[str]] = set()
        for regra in self.compartilhamentos:
            _validar_referencias(
                "compartilhamento",
                (regra.requisito_a, regra.requisito_b),
                ids_requisitos,
            )
            if regra.par in pares_compartilhamento:
                raise ValueError(
                    "Não pode haver duas regras de compartilhamento para o mesmo par."
                )
            pares_compartilhamento.add(regra.par)

        if len(set(self.metadados)) != len(self.metadados):
            raise ValueError("Metadados curriculares não devem conter pares duplicados.")

    @property
    def ids_regras(self) -> frozenset[str]:
        return frozenset(
            [
                *(item.id for item in self.requisitos),
                *(item.id for item in self.grupos),
                *(item.id for item in self.condicionais),
                *(item.id for item in self.sequencias),
                *(item.id for item in self.aplicabilidade),
            ]
        )


def _validar_id(valor: str) -> None:
    if not valor.strip():
        raise ValueError("Regra curricular precisa de id.")


def _validar_referencias(
    origem: str,
    referencias: tuple[str, ...],
    ids_validos: set[str],
) -> None:
    inexistentes = sorted(set(referencias) - ids_validos)
    if inexistentes:
        raise ValueError(
            f"{origem} referencia regras inexistentes: {', '.join(inexistentes)}"
        )


def _validar_ciclos_grupos(
    grupos: tuple[GrupoRequisitos, ...],
    ids_grupos: set[str],
) -> None:
    dependencias = {
        grupo.id: tuple(ref for ref in grupo.requisitos if ref in ids_grupos)
        for grupo in grupos
    }
    visitando: set[str] = set()
    visitados: set[str] = set()

    def visitar(grupo_id: str) -> None:
        if grupo_id in visitados:
            return
        if grupo_id in visitando:
            raise ValueError(f"Ciclo detectado entre grupos a partir de {grupo_id}.")
        visitando.add(grupo_id)
        for dependencia in dependencias.get(grupo_id, ()):
            visitar(dependencia)
        visitando.remove(grupo_id)
        visitados.add(grupo_id)

    for grupo_id in dependencias:
        visitar(grupo_id)
