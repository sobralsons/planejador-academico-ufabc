from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from scripts.executar_api_local import carregar_env_local


ROOT = Path(__file__).resolve().parents[1]
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ErroTesteE2ELocal(RuntimeError):
    pass


def _base_local_http(valor: str, nome: str) -> str:
    parsed = urlparse(valor.strip().rstrip("/"))
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOCAL_HOSTS
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ErroTesteE2ELocal(f"{nome} deve apontar somente para HTTP local.")
    return valor.strip().rstrip("/")


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: object | None = None,
) -> tuple[int, object | None]:
    cabecalhos = {"Accept": "application/json", **(headers or {})}
    dados = None
    if body is not None:
        cabecalhos["Content-Type"] = "application/json"
        dados = json.dumps(body, separators=(",", ":")).encode("utf-8")

    request = Request(url, method=method, headers=cabecalhos, data=dados)
    try:
        with urlopen(request, timeout=5.0) as response:
            status = response.status
            conteudo = response.read()
    except HTTPError as exc:
        status = exc.code
        conteudo = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise ErroTesteE2ELocal("Serviço local indisponível durante o teste E2E.") from exc

    if not conteudo:
        return status, None
    try:
        return status, json.loads(conteudo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErroTesteE2ELocal("Serviço local retornou resposta inválida.") from exc


def _exigir_status(status: int, esperado: int, etapa: str) -> None:
    if status != esperado:
        raise ErroTesteE2ELocal(
            f"{etapa} falhou: HTTP {status}; esperado HTTP {esperado}."
        )


def _criar_usuario(supabase_url: str, chave: str) -> tuple[str, str]:
    identificador = uuid4().hex
    status, payload = _request_json(
        "POST",
        f"{supabase_url}/auth/v1/signup",
        headers={"apikey": chave},
        body={
            "email": f"teste-e2e-{identificador}@example.invalid",
            "password": f"TesteLocal!A1-{identificador}",
        },
    )
    _exigir_status(status, 200, "Criação de usuário sintético")
    if not isinstance(payload, dict):
        raise ErroTesteE2ELocal("Signup local não retornou objeto JSON.")
    token = payload.get("access_token")
    user = payload.get("user")
    user_id = user.get("id") if isinstance(user, dict) else None
    try:
        user_id = str(UUID(str(user_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ErroTesteE2ELocal("Signup local não retornou UUID de usuário válido.") from exc
    if not isinstance(token, str) or not token:
        raise ErroTesteE2ELocal(
            "Signup local não retornou access_token; confira a configuração local de Auth."
        )
    return user_id, token


def executar() -> None:
    carregar_env_local(ROOT / ".env.local")

    supabase_url = _base_local_http(
        os.getenv("SUPABASE_URL", ""),
        "SUPABASE_URL",
    )
    api_host = os.getenv("API_HOST", "127.0.0.1").strip()
    api_port = os.getenv("API_PORT", "8000").strip()
    api_url = _base_local_http(
        f"http://{api_host}:{api_port}",
        "API local",
    )
    chave = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    if not chave:
        raise ErroTesteE2ELocal(
            "Configure SUPABASE_PUBLISHABLE_KEY ou SUPABASE_ANON_KEY em .env.local."
        )

    status, _ = _request_json("GET", f"{api_url}/health")
    _exigir_status(status, 200, "Health da API")

    user_a, token_a = _criar_usuario(supabase_url, chave)
    _user_b, token_b = _criar_usuario(supabase_url, chave)
    sufixo = uuid4().hex[:12]
    compartilhado = f"e2e-compartilhado-{sufixo}"
    somente_a = f"e2e-somente-a-{sufixo}"

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    plano_a = {
        "planejamento_id": compartilhado,
        "curso_id": "ciencia_dados",
        "matriz_id": "2023",
        "versao_regras": "v1",
        "titulo": "Plano A",
        "componentes_planejados": ["MCTA001-17", "MCTB002-17"],
    }
    plano_b = {
        **plano_a,
        "titulo": "Plano B",
        "componentes_planejados": ["MCTA003-17"],
    }
    exclusivo_a = {
        **plano_a,
        "planejamento_id": somente_a,
        "titulo": "Somente A",
        "componentes_planejados": ["MCTA004-17"],
    }

    for etapa, headers, plano in (
        ("Salvar plano A", headers_a, plano_a),
        ("Salvar plano B", headers_b, plano_b),
        ("Salvar plano exclusivo de A", headers_a, exclusivo_a),
    ):
        status, _ = _request_json(
            "POST",
            f"{api_url}/v1/dev/plans",
            headers=headers,
            body=plano,
        )
        _exigir_status(status, 200, etapa)

    status, visao_a = _request_json(
        "GET",
        f"{api_url}/v1/dev/plans/{compartilhado}",
        headers=headers_a,
    )
    _exigir_status(status, 200, "Leitura de A")
    status, visao_b = _request_json(
        "GET",
        f"{api_url}/v1/dev/plans/{compartilhado}",
        headers=headers_b,
    )
    _exigir_status(status, 200, "Leitura de B")

    if not isinstance(visao_a, dict) or visao_a.get("titulo") != "Plano A":
        raise ErroTesteE2ELocal("Usuário A não recebeu sua própria versão do plano.")
    if not isinstance(visao_b, dict) or visao_b.get("titulo") != "Plano B":
        raise ErroTesteE2ELocal("Usuário B não recebeu sua própria versão do plano.")

    status_cruzado, _ = _request_json(
        "GET",
        f"{api_url}/v1/dev/plans/{somente_a}",
        headers=headers_b,
    )
    _exigir_status(status_cruzado, 404, "Acesso cruzado B -> A pela API")

    query = urlencode(
        {
            "select": "planejamento_id",
            "proprietario_id": f"eq.{user_a}",
            "planejamento_id": f"eq.{somente_a}",
        }
    )
    status_direto, direto = _request_json(
        "GET",
        f"{supabase_url}/rest/v1/planejamentos_salvos?{query}",
        headers={
            "apikey": chave,
            "Authorization": f"Bearer {token_b}",
        },
    )
    _exigir_status(status_direto, 200, "Consulta direta B -> A pela Data API")
    if not isinstance(direto, list) or direto:
        raise ErroTesteE2ELocal(
            "RLS permitiu que B visse linha pertencente a A pela Data API."
        )

    print("A vê: Plano A")
    print("B vê: Plano B")
    print("B tentando acessar plano exclusivo de A: 404")
    print("Linhas de A visíveis diretamente pelo Data API usando JWT de B: 0")
    print("E2E local: PASS")


def main() -> int:
    try:
        executar()
    except ErroTesteE2ELocal as exc:
        print(f"E2E local: FALHOU - {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
