import pytest

from scripts import testar_persistencia_e2e_local as e2e


USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def test_base_local_http_rejeita_endpoint_remoto():
    with pytest.raises(e2e.ErroTesteE2ELocal, match="HTTP local"):
        e2e._base_local_http("https://projeto.supabase.co", "teste")


def test_fluxo_e2e_isola_a_e_b_sem_imprimir_tokens(monkeypatch, capsys):
    monkeypatch.setattr(e2e, "carregar_env_local", lambda _path: None)
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "chave-local")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    usuarios = iter(((USER_A, "token-a"), (USER_B, "token-b")))
    monkeypatch.setattr(e2e, "_criar_usuario", lambda *_args: next(usuarios))

    def request_fake(method, url, *, headers=None, body=None):
        if url.endswith("/health"):
            return 200, {"status": "ok"}
        if method == "POST" and url.endswith("/v1/dev/plans"):
            return 200, body
        if method == "GET" and "/v1/dev/plans/e2e-compartilhado-" in url:
            token = (headers or {}).get("Authorization")
            return 200, {"titulo": "Plano A" if token == "Bearer token-a" else "Plano B"}
        if method == "GET" and "/v1/dev/plans/e2e-somente-a-" in url:
            return 404, {"detail": {"code": "planejamento_nao_encontrado"}}
        if method == "GET" and "/rest/v1/planejamentos_salvos?" in url:
            return 200, []
        raise AssertionError((method, url, headers, body))

    monkeypatch.setattr(e2e, "_request_json", request_fake)

    e2e.executar()

    saida = capsys.readouterr().out
    assert "A vê: Plano A" in saida
    assert "B vê: Plano B" in saida
    assert "B tentando acessar plano exclusivo de A: 404" in saida
    assert "Linhas de A visíveis diretamente pelo Data API usando JWT de B: 0" in saida
    assert "E2E local: PASS" in saida
    assert "token-a" not in saida
    assert "token-b" not in saida
    assert "chave-local" not in saida
