from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .autenticacao import (
    ConfiguracaoAutenticacaoInvalida,
    ServicoAutenticacaoIndisponivel,
    TokenAusenteOuInvalido,
    carregar_configuracao_local,
    extrair_bearer,
    validar_token_supabase_local,
)
from .contratos import (
    CapacidadesAPI,
    CenarioSinteticoEntrada,
    IdentidadeAutenticadaSaida,
    IdentificadorPersistencia,
    ListaPlanejamentosSaida,
    RenomearPlanejamentoEntrada,
    RascunhoPlanejamentoEntrada,
    RascunhoPlanejamentoSaida,
    ResultadoOpcoesSinteticas,
    SaudeAPI,
)
from persistencia import (
    AcessoPersistenciaSupabaseNegado,
    ErroAutorizacaoPersistencia,
    PersistenciaSupabaseIndisponivel,
    PersistenciaSupabaseRejeitada,
    RascunhoPlanejamentoPersistivel,
    RepositorioPlanejamentosSupabaseLocal,
)

from .servicos import ErroCenarioSintetico, gerar_opcoes_sinteticas


app = FastAPI(
    title="Planejador Acadêmico UFABC API",
    version="0.1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.exception_handler(RequestValidationError)
async def tratar_validacao(
    _request: Request,
    erro: RequestValidationError,
) -> JSONResponse:
    """Não ecoa valores submetidos pelo cliente em erros de validação."""

    erros = []
    for item in erro.errors():
        erros.append(
            {
                "loc": [str(parte) for parte in item.get("loc", ())],
                "type": item.get("type", "validation_error"),
                "msg": item.get("msg", "Entrada inválida."),
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "request_invalido",
                "errors": erros,
            }
        },
    )


@app.get("/health", response_model=SaudeAPI)
def health() -> SaudeAPI:
    return SaudeAPI()


@app.get("/v1/capabilities", response_model=CapacidadesAPI)
def capabilities() -> CapacidadesAPI:
    return CapacidadesAPI()


@dataclass(frozen=True)
class _ContextoLocalAutenticado:
    user_id: str
    access_token: str
    supabase_url: str
    publishable_key: str


def _contexto_local_autenticado(
    request: Request,
) -> _ContextoLocalAutenticado | JSONResponse:
    try:
        token = extrair_bearer(request.headers.get("authorization"))
        configuracao = carregar_configuracao_local()
        identidade = validar_token_supabase_local(token, configuracao)
    except TokenAusenteOuInvalido:
        return JSONResponse(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            content={"detail": {"code": "nao_autenticado"}},
        )
    except (
        ConfiguracaoAutenticacaoInvalida,
        ServicoAutenticacaoIndisponivel,
    ):
        return JSONResponse(
            status_code=503,
            content={"detail": {"code": "auth_local_indisponivel"}},
        )

    return _ContextoLocalAutenticado(
        user_id=identidade.user_id,
        access_token=token,
        supabase_url=configuracao.supabase_url,
        publishable_key=configuracao.supabase_publishable_key,
    )


def _repositorio_local(
    contexto: _ContextoLocalAutenticado,
) -> RepositorioPlanejamentosSupabaseLocal:
    return RepositorioPlanejamentosSupabaseLocal(
        supabase_url=contexto.supabase_url,
        publishable_key=contexto.publishable_key,
        access_token=contexto.access_token,
        user_id=contexto.user_id,
    )


def _resposta_plano(
    plano: RascunhoPlanejamentoPersistivel,
) -> RascunhoPlanejamentoSaida:
    return RascunhoPlanejamentoSaida(
        planejamento_id=plano.planejamento_id,
        curso_id=plano.curso_id,
        matriz_id=plano.matriz_id,
        versao_regras=plano.versao_regras,
        titulo=plano.titulo,
        componentes_planejados=plano.componentes_planejados,
        schema_version=1,
    )


def _erro_persistencia(erro: Exception) -> JSONResponse:
    if isinstance(
        erro,
        (ErroAutorizacaoPersistencia, AcessoPersistenciaSupabaseNegado),
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": {"code": "persistencia_nao_autorizada"}},
        )
    if isinstance(erro, PersistenciaSupabaseRejeitada):
        return JSONResponse(
            status_code=409,
            content={"detail": {"code": "persistencia_rejeitada"}},
        )
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": "persistencia_local_indisponivel"}},
    )


@app.get(
    "/v1/dev/auth/me",
    response_model=IdentidadeAutenticadaSaida,
)
def auth_me_local(request: Request) -> IdentidadeAutenticadaSaida | JSONResponse:
    contexto = _contexto_local_autenticado(request)
    if isinstance(contexto, JSONResponse):
        return contexto
    return IdentidadeAutenticadaSaida(user_id=contexto.user_id)


@app.post(
    "/v1/dev/plans",
    response_model=RascunhoPlanejamentoSaida,
)
def salvar_planejamento_local(
    entrada: RascunhoPlanejamentoEntrada,
    request: Request,
) -> RascunhoPlanejamentoSaida | JSONResponse:
    contexto = _contexto_local_autenticado(request)
    if isinstance(contexto, JSONResponse):
        return contexto
    plano = RascunhoPlanejamentoPersistivel(
        planejamento_id=entrada.planejamento_id,
        proprietario_id=contexto.user_id,
        curso_id=entrada.curso_id,
        matriz_id=entrada.matriz_id,
        versao_regras=entrada.versao_regras,
        titulo=entrada.titulo,
        componentes_planejados=entrada.componentes_planejados,
    )
    try:
        salvo = _repositorio_local(contexto).salvar(contexto.user_id, plano)
    except (
        ErroAutorizacaoPersistencia,
        AcessoPersistenciaSupabaseNegado,
        PersistenciaSupabaseRejeitada,
        PersistenciaSupabaseIndisponivel,
    ) as erro:
        return _erro_persistencia(erro)
    return _resposta_plano(salvo)


@app.get(
    "/v1/dev/plans",
    response_model=ListaPlanejamentosSaida,
)
def listar_planejamentos_locais(
    request: Request,
) -> ListaPlanejamentosSaida | JSONResponse:
    contexto = _contexto_local_autenticado(request)
    if isinstance(contexto, JSONResponse):
        return contexto
    try:
        itens = _repositorio_local(contexto).listar(contexto.user_id)
    except (
        ErroAutorizacaoPersistencia,
        AcessoPersistenciaSupabaseNegado,
        PersistenciaSupabaseRejeitada,
        PersistenciaSupabaseIndisponivel,
    ) as erro:
        return _erro_persistencia(erro)
    return ListaPlanejamentosSaida(
        itens=tuple(_resposta_plano(item) for item in itens)
    )


@app.get(
    "/v1/dev/plans/{planejamento_id}",
    response_model=RascunhoPlanejamentoSaida,
)
def obter_planejamento_local(
    planejamento_id: IdentificadorPersistencia,
    request: Request,
) -> RascunhoPlanejamentoSaida | JSONResponse:
    contexto = _contexto_local_autenticado(request)
    if isinstance(contexto, JSONResponse):
        return contexto
    try:
        plano = _repositorio_local(contexto).obter(
            contexto.user_id,
            planejamento_id,
        )
    except (
        ErroAutorizacaoPersistencia,
        AcessoPersistenciaSupabaseNegado,
        PersistenciaSupabaseRejeitada,
        PersistenciaSupabaseIndisponivel,
    ) as erro:
        return _erro_persistencia(erro)
    if plano is None:
        return JSONResponse(
            status_code=404,
            content={"detail": {"code": "planejamento_nao_encontrado"}},
        )
    return _resposta_plano(plano)


@app.patch(
    "/v1/dev/plans/{planejamento_id}",
    response_model=RascunhoPlanejamentoSaida,
)
def renomear_planejamento_local(
    planejamento_id: IdentificadorPersistencia,
    entrada: RenomearPlanejamentoEntrada,
    request: Request,
) -> RascunhoPlanejamentoSaida | JSONResponse:
    contexto = _contexto_local_autenticado(request)
    if isinstance(contexto, JSONResponse):
        return contexto
    try:
        plano = _repositorio_local(contexto).renomear(
            contexto.user_id,
            planejamento_id,
            entrada.titulo,
        )
    except (
        ErroAutorizacaoPersistencia,
        AcessoPersistenciaSupabaseNegado,
        PersistenciaSupabaseRejeitada,
        PersistenciaSupabaseIndisponivel,
    ) as erro:
        return _erro_persistencia(erro)
    if plano is None:
        return JSONResponse(
            status_code=404,
            content={"detail": {"code": "planejamento_nao_encontrado"}},
        )
    return _resposta_plano(plano)


@app.delete(
    "/v1/dev/plans/{planejamento_id}",
    status_code=204,
    response_model=None,
)
def excluir_planejamento_local(
    planejamento_id: IdentificadorPersistencia,
    request: Request,
) -> Response | JSONResponse:
    contexto = _contexto_local_autenticado(request)
    if isinstance(contexto, JSONResponse):
        return contexto
    try:
        excluido = _repositorio_local(contexto).excluir(
            contexto.user_id,
            planejamento_id,
        )
    except (
        ErroAutorizacaoPersistencia,
        AcessoPersistenciaSupabaseNegado,
        PersistenciaSupabaseRejeitada,
        PersistenciaSupabaseIndisponivel,
    ) as erro:
        return _erro_persistencia(erro)
    if not excluido:
        return JSONResponse(
            status_code=404,
            content={"detail": {"code": "planejamento_nao_encontrado"}},
        )
    return Response(status_code=204)


@app.post(
    "/v1/synthetic/component-allocation/options",
    response_model=ResultadoOpcoesSinteticas,
)
def synthetic_component_allocation_options(
    entrada: CenarioSinteticoEntrada,
) -> ResultadoOpcoesSinteticas | JSONResponse:
    try:
        return gerar_opcoes_sinteticas(entrada)
    except ErroCenarioSintetico as erro:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": erro.codigo,
                    "message": erro.mensagem,
                }
            },
        )
