import asyncio

import httpx2

import api.app as api_app
from persistencia import (
    PersistenciaSupabaseIndisponivel,
    RepositorioPlanejamentosMemoria,
)


USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


async def _request_async(method: str, path: str, **kwargs):
    transport = httpx2.ASGITransport(app=api_app.app)
    async with httpx2.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


def _request(method: str, path: str, **kwargs):
    return asyncio.run(_request_async(method, path, **kwargs))


def _plano_payload(titulo="Plano A"):
    return {
        "planejamento_id": "plano-compartilhado",
        "curso_id": "ciencia_dados",
        "matriz_id": "2023",
        "versao_regras": "v1",
        "titulo": titulo,
        "componentes_planejados": ["A", "B"],
    }


def _instalar_contextos(monkeypatch, repo):
    def contexto(request):
        authorization = request.headers.get("authorization")
        if authorization == "Bearer token-a":
            user_id = USER_A
            token = "token-a"
        elif authorization == "Bearer token-b":
            user_id = USER_B
            token = "token-b"
        else:
            return api_app.JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
                content={"detail": {"code": "nao_autenticado"}},
            )
        return api_app._ContextoLocalAutenticado(
            user_id=user_id,
            access_token=token,
            supabase_url="http://127.0.0.1:54321",
            publishable_key="sb_publishable_teste",
        )

    monkeypatch.setattr(api_app, "_contexto_local_autenticado", contexto)
    monkeypatch.setattr(api_app, "_repositorio_local", lambda _contexto: repo)


def test_persistencia_local_exige_autenticacao():
    resposta = _request(
        "POST",
        "/v1/dev/plans",
        json=_plano_payload(),
    )

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": {"code": "nao_autenticado"}}


def test_cliente_nao_pode_enviar_proprietario_id_e_valor_nao_e_ecoado():
    payload = _plano_payload()
    payload["proprietario_id"] = USER_B

    resposta = _request(
        "POST",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer qualquer"},
        json=payload,
    )

    assert resposta.status_code == 422
    assert "proprietario_id" in resposta.text
    assert USER_B not in resposta.text


def test_salvar_deriva_proprietario_do_usuario_e_nao_o_expoe(monkeypatch):
    repo = RepositorioPlanejamentosMemoria()
    _instalar_contextos(monkeypatch, repo)

    resposta = _request(
        "POST",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer token-a"},
        json=_plano_payload(),
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["planejamento_id"] == "plano-compartilhado"
    assert corpo["titulo"] == "Plano A"
    assert "proprietario_id" not in corpo
    assert repo.obter(USER_A, "plano-compartilhado") is not None
    assert repo.obter(USER_B, "plano-compartilhado") is None


def test_mesmo_id_fica_isolado_por_usuario_em_todo_crud(monkeypatch):
    repo = RepositorioPlanejamentosMemoria()
    _instalar_contextos(monkeypatch, repo)

    resposta_a = _request(
        "POST",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer token-a"},
        json=_plano_payload("Plano A"),
    )
    resposta_b = _request(
        "POST",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer token-b"},
        json=_plano_payload("Plano B"),
    )
    assert resposta_a.status_code == 200
    assert resposta_b.status_code == 200

    leitura_a = _request(
        "GET",
        "/v1/dev/plans/plano-compartilhado",
        headers={"Authorization": "Bearer token-a"},
    )
    leitura_b = _request(
        "GET",
        "/v1/dev/plans/plano-compartilhado",
        headers={"Authorization": "Bearer token-b"},
    )
    assert leitura_a.json()["titulo"] == "Plano A"
    assert leitura_b.json()["titulo"] == "Plano B"

    renomeado_b = _request(
        "PATCH",
        "/v1/dev/plans/plano-compartilhado",
        headers={"Authorization": "Bearer token-b"},
        json={"titulo": "Plano B revisado"},
    )
    assert renomeado_b.status_code == 200
    assert renomeado_b.json()["titulo"] == "Plano B revisado"
    assert repo.obter(USER_A, "plano-compartilhado").titulo == "Plano A"

    excluido_b = _request(
        "DELETE",
        "/v1/dev/plans/plano-compartilhado",
        headers={"Authorization": "Bearer token-b"},
    )
    assert excluido_b.status_code == 204
    assert repo.obter(USER_B, "plano-compartilhado") is None
    assert repo.obter(USER_A, "plano-compartilhado").titulo == "Plano A"


def test_usuario_b_nao_encontra_planejamento_exclusivo_de_a(monkeypatch):
    repo = RepositorioPlanejamentosMemoria()
    _instalar_contextos(monkeypatch, repo)

    assert _request(
        "POST",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer token-a"},
        json=_plano_payload(),
    ).status_code == 200

    for method, kwargs in (
        ("GET", {}),
        ("PATCH", {"json": {"titulo": "Ataque"}}),
        ("DELETE", {}),
    ):
        resposta = _request(
            method,
            "/v1/dev/plans/plano-compartilhado",
            headers={"Authorization": "Bearer token-b"},
            **kwargs,
        )
        assert resposta.status_code == 404

    assert repo.obter(USER_A, "plano-compartilhado").titulo == "Plano A"


def test_listagem_retorna_somente_planos_do_usuario(monkeypatch):
    repo = RepositorioPlanejamentosMemoria()
    _instalar_contextos(monkeypatch, repo)

    for token, titulo in (("token-a", "Plano A"), ("token-b", "Plano B")):
        assert _request(
            "POST",
            "/v1/dev/plans",
            headers={"Authorization": f"Bearer {token}"},
            json=_plano_payload(titulo),
        ).status_code == 200

    resposta = _request(
        "GET",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer token-a"},
    )

    assert resposta.status_code == 200
    assert [item["titulo"] for item in resposta.json()["itens"]] == ["Plano A"]
    assert USER_A not in resposta.text
    assert USER_B not in resposta.text


def test_erro_interno_de_persistencia_nao_vaza_detalhe(monkeypatch):
    class RepoFalho:
        def listar(self, _ator_id):
            raise PersistenciaSupabaseIndisponivel(
                "DETALHE-SENSIVEL-DO-BANCO"
            )

    _instalar_contextos(monkeypatch, RepoFalho())

    resposta = _request(
        "GET",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer token-a"},
    )

    assert resposta.status_code == 503
    assert resposta.json() == {
        "detail": {"code": "persistencia_local_indisponivel"}
    }
    assert "DETALHE-SENSIVEL-DO-BANCO" not in resposta.text


def test_componentes_duplicados_sao_rejeitados_antes_da_persistencia():
    payload = _plano_payload()
    payload["componentes_planejados"] = ["A", "A"]

    resposta = _request(
        "POST",
        "/v1/dev/plans",
        headers={"Authorization": "Bearer qualquer"},
        json=payload,
    )

    assert resposta.status_code == 422
    assert "request_invalido" in resposta.text
