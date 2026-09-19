from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Protocol


_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_CODIGO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
_MAX_COMPONENTES_PLANEJADOS = 200


class ClassePersistencia(str, Enum):
    PUBLICO_REFERENCIA = "publico_referencia"
    USUARIO_ISOLADO = "usuario_isolado"
    TEMPORARIO = "temporario"
    PROIBIDO = "proibido"


@dataclass(frozen=True)
class PoliticaDado:
    chave: str
    classe: ClassePersistencia
    persistir_por_padrao: bool
    motivo: str


_POLITICAS = {
    "fontes_curriculares_publicas": PoliticaDado(
        chave="fontes_curriculares_publicas",
        classe=ClassePersistencia.PUBLICO_REFERENCIA,
        persistir_por_padrao=True,
        motivo="Dados acadêmicos públicos e versionados podem compor o catálogo.",
    ),
    "rascunho_planejamento": PoliticaDado(
        chave="rascunho_planejamento",
        classe=ClassePersistencia.USUARIO_ISOLADO,
        persistir_por_padrao=True,
        motivo=(
            "Planejamentos salvos pertencem a um único usuário e exigem "
            "isolamento por proprietário."
        ),
    ),
    "preferencias_planejamento": PoliticaDado(
        chave="preferencias_planejamento",
        classe=ClassePersistencia.USUARIO_ISOLADO,
        persistir_por_padrao=True,
        motivo="Preferências salvas devem ficar vinculadas ao proprietário.",
    ),
    "arquivo_historico_bruto": PoliticaDado(
        chave="arquivo_historico_bruto",
        classe=ClassePersistencia.TEMPORARIO,
        persistir_por_padrao=False,
        motivo=(
            "O arquivo do SIGAA pode conter dados pessoais e deve ser processado "
            "temporariamente por padrão."
        ),
    ),
    "registros_historico_detalhados": PoliticaDado(
        chave="registros_historico_detalhados",
        classe=ClassePersistencia.TEMPORARIO,
        persistir_por_padrao=False,
        motivo=(
            "Tentativas, conceitos, turmas e docentes não são necessários para "
            "persistir um rascunho de planejamento."
        ),
    ),
    "evidencias_academicas_derivadas": PoliticaDado(
        chave="evidencias_academicas_derivadas",
        classe=ClassePersistencia.TEMPORARIO,
        persistir_por_padrao=False,
        motivo=(
            "Evidências derivadas do histórico continuam vinculadas à situação "
            "acadêmica individual e não são persistidas nesta etapa."
        ),
    ),
    "credenciais_tokens_sessoes": PoliticaDado(
        chave="credenciais_tokens_sessoes",
        classe=ClassePersistencia.PROIBIDO,
        persistir_por_padrao=False,
        motivo="Credenciais, tokens e sessões nunca pertencem às tabelas da aplicação.",
    ),
    "ra_nome_email_em_tabela_de_dominio": PoliticaDado(
        chave="ra_nome_email_em_tabela_de_dominio",
        classe=ClassePersistencia.PROIBIDO,
        persistir_por_padrao=False,
        motivo=(
            "Tabelas de domínio usam apenas identificador opaco do provedor de "
            "autenticação; identidade não é duplicada sem necessidade."
        ),
    ),
}


def politica_dados() -> tuple[PoliticaDado, ...]:
    return tuple(_POLITICAS[chave] for chave in sorted(_POLITICAS))


@dataclass(frozen=True)
class RascunhoPlanejamentoPersistivel:
    """Contrato mínimo que um futuro banco poderá persistir.

    Não contém histórico bruto, conceitos, docentes, RA, nome, e-mail ou tokens.
    O identificador do proprietário deve ser opaco e vir da camada autenticada.
    """

    planejamento_id: str
    proprietario_id: str
    curso_id: str
    matriz_id: str
    versao_regras: str
    titulo: str
    componentes_planejados: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        _validar_id(self.planejamento_id, "planejamento_id")
        _validar_id(self.proprietario_id, "proprietario_id")
        _validar_id(self.curso_id, "curso_id")
        _validar_id(self.matriz_id, "matriz_id")
        _validar_id(self.versao_regras, "versao_regras")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("schema_version deve ser exatamente 1.")
        titulo = self.titulo.strip()
        if not titulo or len(titulo) > 120:
            raise ValueError("Título do planejamento deve ter entre 1 e 120 caracteres.")
        if len(self.componentes_planejados) > _MAX_COMPONENTES_PLANEJADOS:
            raise ValueError("Planejamento excede o limite de componentes persistíveis.")
        if len(set(self.componentes_planejados)) != len(self.componentes_planejados):
            raise ValueError("Planejamento não pode repetir o mesmo componente.")
        for codigo in self.componentes_planejados:
            if not isinstance(codigo, str) or not _CODIGO_RE.fullmatch(codigo):
                raise ValueError("Código de componente persistido é inválido.")


def _validar_id(valor: str, campo: str) -> None:
    if not isinstance(valor, str) or not _ID_RE.fullmatch(valor):
        raise ValueError(f"{campo} deve ser um identificador opaco válido.")


class RepositorioPlanejamentos(Protocol):
    def salvar(
        self,
        ator_id: str,
        planejamento: RascunhoPlanejamentoPersistivel,
    ) -> RascunhoPlanejamentoPersistivel: ...

    def obter(
        self,
        ator_id: str,
        planejamento_id: str,
    ) -> RascunhoPlanejamentoPersistivel | None: ...

    def listar(
        self,
        ator_id: str,
    ) -> tuple[RascunhoPlanejamentoPersistivel, ...]: ...

    def renomear(
        self,
        ator_id: str,
        planejamento_id: str,
        titulo: str,
    ) -> RascunhoPlanejamentoPersistivel | None: ...

    def excluir(self, ator_id: str, planejamento_id: str) -> bool: ...

    def excluir_todos(self, ator_id: str) -> int: ...
