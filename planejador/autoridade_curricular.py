"""Política fail-closed para promover um piloto ao motor curricular genérico."""

from dataclasses import dataclass, fields
from enum import Enum


class AutoridadeCurricular(str, Enum):
    LEGADO = "legado"
    GENERICO = "generico"


class BloqueioCorteAutoridade(str, Enum):
    FONTES_VERSIONADAS = "fontes_versionadas"
    APLICABILIDADE = "aplicabilidade_resolvida"
    CONVERSAO_HISTORICO = "conversao_preserva_incertezas"
    COMPLETUDE_UNIDADES = "completude_unidades_comprovada"
    ALOCACAO_EVIDENCIAS = "ambiguidades_alocacao_tratadas"
    EQUIVALENCIA_DIFERENCIAL = "equivalencia_diferencial_aprovada"
    CASOS_ADVERSARIAIS = "casos_adversariais_aprovados"
    REVISAO_HUMANA = "revisao_humana_registrada"
    FALLBACK_SILENCIOSO = "sem_fallback_silencioso"


@dataclass(frozen=True)
class EvidenciasCorteAutoridade:
    fontes_versionadas: bool = False
    aplicabilidade_resolvida: bool = False
    conversao_preserva_incertezas: bool = False
    completude_unidades_comprovada: bool = False
    ambiguidades_alocacao_tratadas: bool = False
    equivalencia_diferencial_aprovada: bool = False
    casos_adversariais_aprovados: bool = False
    revisao_humana_registrada: bool = False
    sem_fallback_silencioso: bool = False

    def __post_init__(self) -> None:
        if any(type(getattr(self, campo.name)) is not bool for campo in fields(self)):
            raise ValueError("Toda evidência do corte de autoridade deve ser booleana.")


@dataclass(frozen=True)
class DecisaoCorteAutoridade:
    curriculo_id: str
    autoridade: AutoridadeCurricular
    bloqueios: tuple[BloqueioCorteAutoridade, ...]

    @property
    def promovido(self) -> bool:
        return self.autoridade is AutoridadeCurricular.GENERICO


def decidir_corte_autoridade(
    curriculo_id: str,
    evidencias: EvidenciasCorteAutoridade,
) -> DecisaoCorteAutoridade:
    """Decide autoridade para um escopo; qualquer evidência ausente mantém o legado."""

    if not curriculo_id or curriculo_id != curriculo_id.strip():
        raise ValueError("curriculo_id deve ser um identificador não vazio e canônico.")

    bloqueios = tuple(
        bloqueio
        for bloqueio in BloqueioCorteAutoridade
        if not getattr(evidencias, bloqueio.value)
    )
    autoridade = (
        AutoridadeCurricular.LEGADO
        if bloqueios
        else AutoridadeCurricular.GENERICO
    )
    return DecisaoCorteAutoridade(
        curriculo_id=curriculo_id,
        autoridade=autoridade,
        bloqueios=bloqueios,
    )
