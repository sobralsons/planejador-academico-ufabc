from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .autenticacao import (
    ConfiguracaoAutenticacaoInvalida,
    ServicoAutenticacaoIndisponivel,
    TokenAusenteOuInvalido,
    extrair_bearer,
    validar_token_supabase_local,
)
from .contratos import (
    CapacidadesAPI,
    CenarioSinteticoEntrada,
    IdentidadeAutenticadaSaida,
    ResultadoOpcoesSinteticas,
    SaudeAPI,
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


@app.get(
    "/v1/dev/auth/me",
    response_model=IdentidadeAutenticadaSaida,
)
def auth_me_local(request: Request) -> IdentidadeAutenticadaSaida | JSONResponse:
    try:
        token = extrair_bearer(request.headers.get("authorization"))
        identidade = validar_token_supabase_local(token)
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

    return IdentidadeAutenticadaSaida(user_id=identidade.user_id)


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
