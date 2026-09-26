from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


CodigoComponente = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9_.-]+$",
    ),
]
Identificador = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    ),
]
IdentificadorPersistencia = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    ),
]
TituloPlanejamento = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class ContratoEstrito(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ComponenteSinteticoEntrada(ContratoEstrito):
    codigo: CodigoComponente
    creditos: int = Field(default=4, strict=True, ge=0, le=60)
    carga_horaria: int = Field(default=48, strict=True, ge=0, le=2000)
    carga_extensao: int = Field(default=0, strict=True, ge=0, le=2000)


class EquivalenciaCompostaEntrada(ContratoEstrito):
    origens: tuple[CodigoComponente, ...] = Field(min_length=2, max_length=10)
    destino: CodigoComponente

    @field_validator("origens")
    @classmethod
    def origens_devem_ser_unicas(
        cls,
        valor: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(set(valor)) != len(valor):
            raise ValueError("Origens da equivalência não podem se repetir.")
        return valor

    @model_validator(mode="after")
    def destino_nao_pode_ser_origem(self) -> "EquivalenciaCompostaEntrada":
        if self.destino in self.origens:
            raise ValueError("Destino da equivalência não pode ser uma das origens.")
        return self


class RequisitoComponenteEntrada(ContratoEstrito):
    id: Identificador
    codigo: CodigoComponente


class CenarioSinteticoEntrada(ContratoEstrito):
    componentes: tuple[ComponenteSinteticoEntrada, ...] = Field(
        min_length=1,
        max_length=30,
    )
    equivalencias_compostas: tuple[EquivalenciaCompostaEntrada, ...] = Field(
        default=(),
        max_length=20,
    )
    requisitos: tuple[RequisitoComponenteEntrada, ...] = Field(
        min_length=1,
        max_length=30,
    )

    @model_validator(mode="after")
    def validar_unicidade(self) -> "CenarioSinteticoEntrada":
        codigos = [item.codigo for item in self.componentes]
        if len(codigos) != len(set(codigos)):
            raise ValueError("Códigos de componentes sintéticos devem ser únicos.")

        ids = [item.id for item in self.requisitos]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de requisitos devem ser únicos.")
        return self


class DecisaoAlocacaoSaida(ContratoEstrito):
    evidencia_id: str
    requisito_id: str


class ImpactoRequisitoSaida(ContratoEstrito):
    requisito_id: str
    estado_antes: str | None
    estado_depois: str | None
    valor_antes: int | None
    valor_depois: int | None


class OpcaoAlocacaoSaida(ContratoEstrito):
    id: str
    decisoes: tuple[DecisaoAlocacaoSaida, ...]
    evidencias_usadas: tuple[str, ...]
    requisitos_destino: tuple[str, ...]
    recursos_consumidos: tuple[str, ...]
    impactos: tuple[ImpactoRequisitoSaida, ...]
    estado_modelo_depois: str | None
    pendencias_restantes: int
    bloqueios_restantes: tuple[str, ...]


class QuestaoAlocacaoSaida(ContratoEstrito):
    id: str
    evidencias: tuple[str, ...]
    recursos: tuple[str, ...]
    opcoes: tuple[OpcaoAlocacaoSaida, ...]
    completa: bool
    auto_resolvivel: bool
    motivo: str


class ResultadoOpcoesSinteticas(ContratoEstrito):
    modo: Literal["sintetico"] = "sintetico"
    resultado_academico_oficial: Literal[False] = False
    persistencia: Literal[False] = False
    estado_inicial: str | None
    questoes: tuple[QuestaoAlocacaoSaida, ...]


class RascunhoPlanejamentoEntrada(ContratoEstrito):
    planejamento_id: IdentificadorPersistencia
    curso_id: IdentificadorPersistencia
    matriz_id: IdentificadorPersistencia
    versao_regras: IdentificadorPersistencia
    titulo: TituloPlanejamento
    componentes_planejados: tuple[CodigoComponente, ...] = Field(
        default=(),
        max_length=200,
    )

    @field_validator("componentes_planejados")
    @classmethod
    def componentes_devem_ser_unicos(
        cls,
        valor: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(set(valor)) != len(valor):
            raise ValueError("Planejamento não pode repetir o mesmo componente.")
        return valor


class RenomearPlanejamentoEntrada(ContratoEstrito):
    titulo: TituloPlanejamento


class RascunhoPlanejamentoSaida(ContratoEstrito):
    planejamento_id: str
    curso_id: str
    matriz_id: str
    versao_regras: str
    titulo: str
    componentes_planejados: tuple[str, ...]
    schema_version: Literal[1] = 1


class ListaPlanejamentosSaida(ContratoEstrito):
    itens: tuple[RascunhoPlanejamentoSaida, ...]


class IdentidadeAutenticadaSaida(ContratoEstrito):
    user_id: str
    provedor: Literal["supabase_local"] = "supabase_local"
    dados_identidade_persistidos: Literal[False] = False


class SaudeAPI(ContratoEstrito):
    status: Literal["ok"] = "ok"
    servico: Literal["planejador-academico-ufabc-api"] = (
        "planejador-academico-ufabc-api"
    )
    versao_api: Literal["0.1"] = "0.1"
    publicacao_academica_habilitada: Literal[False] = False


class CapacidadesAPI(ContratoEstrito):
    modo: Literal["desenvolvimento_sintetico"] = "desenvolvimento_sintetico"
    aceita_dados_pessoais: Literal[False] = False
    aceita_uploads: Literal[False] = False
    persistencia_habilitada: Literal[False] = False
    persistencia_local_disponivel: Literal[True] = True
    autenticacao_habilitada: Literal[False] = False
    autenticacao_local_disponivel: Literal[True] = True
    contratos_academicos_via_nucleo_python: Literal[True] = True
