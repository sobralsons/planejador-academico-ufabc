"""Fronteira de persistência do Planejador Acadêmico UFABC.

Nenhum adaptador deste pacote deve receber histórico bruto por padrão.
"""

from .contratos import (
    ClassePersistencia,
    PoliticaDado,
    RascunhoPlanejamentoPersistivel,
    politica_dados,
)
from .repositorio_memoria import (
    ErroAutorizacaoPersistencia,
    ErroConflitoPersistencia,
    RepositorioPlanejamentosMemoria,
)

__all__ = [
    "ClassePersistencia",
    "PoliticaDado",
    "RascunhoPlanejamentoPersistivel",
    "politica_dados",
    "ErroAutorizacaoPersistencia",
    "ErroConflitoPersistencia",
    "RepositorioPlanejamentosMemoria",
]
