"""Fronteira de persistência do Planejador Acadêmico UFABC.

Nenhum adaptador deste pacote deve receber histórico bruto por padrão.
"""

from .contratos import (
    ClassePersistencia,
    PoliticaDado,
    RascunhoPlanejamentoPersistivel,
    RepositorioPlanejamentos,
    politica_dados,
)
from .repositorio_memoria import (
    ErroAutorizacaoPersistencia,
    ErroConflitoPersistencia,
    RepositorioPlanejamentosMemoria,
)
from .repositorio_supabase_local import (
    AcessoPersistenciaSupabaseNegado,
    ErroPersistenciaSupabaseLocal,
    PersistenciaSupabaseIndisponivel,
    PersistenciaSupabaseRejeitada,
    RepositorioPlanejamentosSupabaseLocal,
)

__all__ = [
    "ClassePersistencia",
    "PoliticaDado",
    "RascunhoPlanejamentoPersistivel",
    "RepositorioPlanejamentos",
    "politica_dados",
    "ErroAutorizacaoPersistencia",
    "ErroConflitoPersistencia",
    "RepositorioPlanejamentosMemoria",
    "AcessoPersistenciaSupabaseNegado",
    "ErroPersistenciaSupabaseLocal",
    "PersistenciaSupabaseIndisponivel",
    "PersistenciaSupabaseRejeitada",
    "RepositorioPlanejamentosSupabaseLocal",
]
