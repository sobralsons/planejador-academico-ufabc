from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID


class ErroAutenticacaoLocal(Exception):
    pass


class TokenAusenteOuInvalido(ErroAutenticacaoLocal):
    pass


class ConfiguracaoAutenticacaoInvalida(ErroAutenticacaoLocal):
    pass


class ServicoAutenticacaoIndisponivel(ErroAutenticacaoLocal):
    pass


@dataclass(frozen=True)
class ConfiguracaoAutenticacaoLocal:
    supabase_url: str
    supabase_publishable_key: str
    timeout_segundos: float = 3.0


@dataclass(frozen=True)
class IdentidadeAutenticada:
    user_id: str


def carregar_configuracao_local() -> ConfiguracaoAutenticacaoLocal:
    ambiente = os.getenv("APP_ENV", "").strip().lower()
    if ambiente != "development":
        raise ConfiguracaoAutenticacaoInvalida(
            "Autenticação local só pode operar em ambiente de desenvolvimento."
        )

    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    chave = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    if not url or not chave:
        raise ConfiguracaoAutenticacaoInvalida(
            "Supabase local não está configurado."
        )

    parsed = urlparse(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ConfiguracaoAutenticacaoInvalida(
            "SUPABASE_URL deve apontar somente para o Supabase local."
        )

    return ConfiguracaoAutenticacaoLocal(
        supabase_url=url,
        supabase_publishable_key=chave,
    )


def extrair_bearer(authorization: str | None) -> str:
    if not authorization:
        raise TokenAusenteOuInvalido("Bearer token ausente.")

    partes = authorization.strip().split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise TokenAusenteOuInvalido("Cabeçalho Authorization inválido.")

    token = partes[1]
    if not token or len(token) > 8192 or any(ch.isspace() for ch in token):
        raise TokenAusenteOuInvalido("Bearer token inválido.")
    return token


def validar_token_supabase_local(
    token: str,
    configuracao: ConfiguracaoAutenticacaoLocal | None = None,
) -> IdentidadeAutenticada:
    cfg = configuracao or carregar_configuracao_local()
    request = Request(
        f"{cfg.supabase_url}/auth/v1/user",
        method="GET",
        headers={
            "Accept": "application/json",
            "apikey": cfg.supabase_publishable_key,
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urlopen(request, timeout=cfg.timeout_segundos) as response:
            if response.status != 200:
                raise ServicoAutenticacaoIndisponivel(
                    "Resposta inesperada do Supabase Auth."
                )
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise TokenAusenteOuInvalido("Token rejeitado pelo Supabase Auth.") from exc
        raise ServicoAutenticacaoIndisponivel(
            "Supabase Auth indisponível."
        ) from exc
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ServicoAutenticacaoIndisponivel(
            "Supabase Auth indisponível."
        ) from exc

    if not isinstance(payload, dict):
        raise ServicoAutenticacaoIndisponivel(
            "Resposta inválida do Supabase Auth."
        )

    user_id = payload.get("id")
    try:
        user_uuid = UUID(str(user_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ServicoAutenticacaoIndisponivel(
            "Supabase Auth retornou identidade inválida."
        ) from exc

    return IdentidadeAutenticada(user_id=str(user_uuid))
