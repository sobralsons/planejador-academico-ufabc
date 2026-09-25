import asyncio
import json
import os
from urllib.error import HTTPError

import httpx2
import pytest

import api.app as api_app
from api import autenticacao as auth


USER_ID = "11111111-1111-1111-1111-111111111111"


async def _request_async(method: str, path: str, **kwargs):
    transport = httpx2.ASGITransport(app=api_app.app)
    async with httpx2.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


def _get(path: str, **kwargs):
    return asyncio.run(_request_async("GET", path, **kwargs))


class _RespostaFake:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _configurar_local(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_teste")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)


def test_endpoint_auth_exige_bearer_sem_ecoar_cabecalho():
    resposta = _get("/v1/dev/auth/me")

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": {"code": "nao_autenticado"}}
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    [
        "",
        "Basic abc",
        "Bearer",
        "Bearer token extra",
    ],
)
def test_endpoint_auth_rejeita_authorization_malformado(authorization):
    resposta = _get(
        "/v1/dev/auth/me",
        headers={"Authorization": authorization},
    )

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": {"code": "nao_autenticado"}}
    if authorization:
        assert authorization not in resposta.text


def test_configuracao_auth_recusa_supabase_remoto(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SUPABASE_URL", "https://projeto.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "nao-deve-ser-usada")

    with pytest.raises(auth.ConfiguracaoAutenticacaoInvalida):
        auth.carregar_configuracao_local()


def test_configuracao_auth_recusa_ambiente_nao_desenvolvimento(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "nao-deve-ser-usada")

    with pytest.raises(auth.ConfiguracaoAutenticacaoInvalida):
        auth.carregar_configuracao_local()


def test_validacao_consulta_auth_server_e_retorna_apenas_uuid(monkeypatch):
    _configurar_local(monkeypatch)
    capturado = {}
    token = "TOKEN-SENSIVEL-DE-TESTE"

    def urlopen_fake(request, timeout):
        capturado["url"] = request.full_url
        capturado["headers"] = {
            chave.lower(): valor
            for chave, valor in request.header_items()
        }
        capturado["timeout"] = timeout
        return _RespostaFake(
            {
                "id": USER_ID,
                "email": "nao-deve-ser-propagado@example.invalid",
                "role": "authenticated",
            }
        )

    monkeypatch.setattr(auth, "urlopen", urlopen_fake)

    identidade = auth.validar_token_supabase_local(token)

    assert identidade == auth.IdentidadeAutenticada(user_id=USER_ID)
    assert capturado["url"] == "http://127.0.0.1:54321/auth/v1/user"
    assert capturado["headers"]["authorization"] == f"Bearer {token}"
    assert capturado["headers"]["apikey"] == "sb_publishable_teste"
    assert capturado["timeout"] == 3.0


def test_token_rejeitado_pelo_auth_server_vira_nao_autenticado(monkeypatch):
    _configurar_local(monkeypatch)

    def urlopen_fake(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(auth, "urlopen", urlopen_fake)

    with pytest.raises(auth.TokenAusenteOuInvalido):
        auth.validar_token_supabase_local("token-invalido")


def test_endpoint_retorna_somente_id_opaco_sem_email_ou_token(monkeypatch):
    token = "TOKEN-SENSIVEL-DE-TESTE"
    monkeypatch.setattr(
        api_app,
        "validar_token_supabase_local",
        lambda recebido: auth.IdentidadeAutenticada(user_id=USER_ID)
        if recebido == token
        else (_ for _ in ()).throw(auth.TokenAusenteOuInvalido()),
    )

    resposta = _get(
        "/v1/dev/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "user_id": USER_ID,
        "provedor": "supabase_local",
        "dados_identidade_persistidos": False,
    }
    assert token not in resposta.text
    assert "email" not in resposta.text.lower()


def test_endpoint_falha_fechado_quando_auth_local_indisponivel(monkeypatch):
    monkeypatch.setattr(
        api_app,
        "validar_token_supabase_local",
        lambda _token: (_ for _ in ()).throw(
            auth.ServicoAutenticacaoIndisponivel()
        ),
    )

    resposta = _get(
        "/v1/dev/auth/me",
        headers={"Authorization": "Bearer token-opaco"},
    )

    assert resposta.status_code == 503
    assert resposta.json() == {
        "detail": {"code": "auth_local_indisponivel"}
    }
    assert "token-opaco" not in resposta.text


def test_launcher_carrega_env_local_sem_sobrescrever_variaveis_existentes(
    tmp_path,
    monkeypatch,
):
    from scripts.executar_api_local import carregar_env_local

    caminho = tmp_path / ".env.local"
    caminho.write_text(
        "# teste\n"
        "APP_ENV=development\n"
        "SUPABASE_URL=http://127.0.0.1:54321\n"
        "SUPABASE_PUBLISHABLE_KEY=chave-local\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_ENV", "development-ja-definido")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)

    carregar_env_local(caminho)

    assert os.environ["APP_ENV"] == "development-ja-definido"
    assert os.environ["SUPABASE_URL"] == "http://127.0.0.1:54321"
    assert os.environ["SUPABASE_PUBLISHABLE_KEY"] == "chave-local"


def test_launcher_rejeita_linha_env_invalida(tmp_path):
    from scripts.executar_api_local import carregar_env_local

    caminho = tmp_path / ".env.local"
    caminho.write_text("linha-sem-igual\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Linha 1 inválida"):
        carregar_env_local(caminho)


def test_launcher_rejeita_host_nao_local(monkeypatch):
    from scripts import executar_api_local as launcher

    monkeypatch.setattr(launcher, "carregar_env_local", lambda _caminho: None)
    monkeypatch.setenv("API_HOST", "0.0.0.0")

    with pytest.raises(RuntimeError, match="só pode escutar"):
        launcher.executar()


def test_bat_executa_launcher_como_modulo_para_preservar_raiz_de_importacao():
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    conteudo = (raiz / "executar_api_windows.bat").read_text(encoding="utf-8")

    assert '-m scripts.executar_api_local' in conteudo
    assert 'scripts\\executar_api_local.py' not in conteudo
