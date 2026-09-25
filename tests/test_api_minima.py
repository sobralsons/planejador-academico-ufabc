import asyncio

import httpx2

from api.app import app


async def _request_async(method: str, path: str, **kwargs):
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


def _request(method: str, path: str, **kwargs):
    return asyncio.run(_request_async(method, path, **kwargs))


def _get(path: str, **kwargs):
    return _request("GET", path, **kwargs)


def _post(path: str, **kwargs):
    return _request("POST", path, **kwargs)


def _cenario_composto():
    return {
        "componentes": [
            {"codigo": "A"},
            {"codigo": "B"},
        ],
        "equivalencias_compostas": [
            {"origens": ["A", "B"], "destino": "C"},
        ],
        "requisitos": [
            {"id": "usar_a", "codigo": "A"},
            {"id": "usar_b", "codigo": "B"},
            {"id": "usar_c", "codigo": "C"},
        ],
    }


def test_health_nao_declara_publicacao_academica():
    resposta = _get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "status": "ok",
        "servico": "planejador-academico-ufabc-api",
        "versao_api": "0.1",
        "publicacao_academica_habilitada": False,
    }


def test_capacidades_deixam_limites_de_privacidade_explicitos():
    resposta = _get("/v1/capabilities")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "modo": "desenvolvimento_sintetico",
        "aceita_dados_pessoais": False,
        "aceita_uploads": False,
        "persistencia_habilitada": False,
        "autenticacao_habilitada": False,
        "autenticacao_local_disponivel": True,
        "contratos_academicos_via_nucleo_python": True,
    }


def test_documentacao_interativa_e_openapi_nao_ficam_expostos_por_padrao():
    assert _get("/docs").status_code == 404
    assert _get("/redoc").status_code == 404
    assert _get("/openapi.json").status_code == 404


def test_endpoint_sintetico_expoe_ab_ou_c_sem_escolher_automaticamente():
    resposta = _post(
        "/v1/synthetic/component-allocation/options",
        json=_cenario_composto(),
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["modo"] == "sintetico"
    assert corpo["resultado_academico_oficial"] is False
    assert corpo["persistencia"] is False
    assert corpo["estado_inicial"] == "indeterminado"
    assert len(corpo["questoes"]) == 1

    questao = corpo["questoes"][0]
    assert questao["completa"] is True
    assert questao["auto_resolvivel"] is False
    assert len(questao["opcoes"]) == 2

    evidencias = {
        frozenset(opcao["evidencias_usadas"])
        for opcao in questao["opcoes"]
    }
    assert evidencias == {
        frozenset({"historico:A:componente", "historico:B:componente"}),
        frozenset({"historico:equivalencia_composta:C:componente"}),
    }


def test_campos_extras_sao_rejeitados_sem_ecoar_valor_enviado():
    payload = _cenario_composto()
    payload["segredo_que_nao_deve_voltar"] = "VALOR-SENSIVEL-DE-TESTE"

    resposta = _post(
        "/v1/synthetic/component-allocation/options",
        json=payload,
    )

    assert resposta.status_code == 422
    corpo_texto = resposta.text
    assert "request_invalido" in corpo_texto
    assert "segredo_que_nao_deve_voltar" in corpo_texto
    assert "VALOR-SENSIVEL-DE-TESTE" not in corpo_texto


def test_codigo_invalido_e_rejeitado_sem_ecoar_payload():
    payload = _cenario_composto()
    payload["componentes"][0]["codigo"] = "A COM ESPACO E DADO SENSIVEL"

    resposta = _post(
        "/v1/synthetic/component-allocation/options",
        json=payload,
    )

    assert resposta.status_code == 422
    assert "request_invalido" in resposta.text
    assert "A COM ESPACO E DADO SENSIVEL" not in resposta.text


def test_limite_de_componentes_impede_payload_estruturalmente_excessivo():
    payload = {
        "componentes": [{"codigo": f"C{i}"} for i in range(31)],
        "equivalencias_compostas": [],
        "requisitos": [{"id": "r", "codigo": "C0"}],
    }

    resposta = _post(
        "/v1/synthetic/component-allocation/options",
        json=payload,
    )

    assert resposta.status_code == 422
    assert "request_invalido" in resposta.text


def test_equivalencia_com_origem_ausente_falha_sem_expor_detalhe_interno():
    payload = {
        "componentes": [{"codigo": "A"}],
        "equivalencias_compostas": [
            {"origens": ["A", "B"], "destino": "C"},
        ],
        "requisitos": [{"id": "r", "codigo": "C"}],
    }

    resposta = _post(
        "/v1/synthetic/component-allocation/options",
        json=payload,
    )

    assert resposta.status_code == 422
    assert resposta.json() == {
        "detail": {
            "code": "origem_inexistente",
            "message": (
                "Equivalência composta referencia origem não presente no cenário."
            ),
        }
    }


def test_api_nao_habilita_cors_globalmente():
    resposta = _get(
        "/health",
        headers={"Origin": "https://origem-nao-autorizada.example"},
    )

    assert resposta.status_code == 200
    assert "access-control-allow-origin" not in resposta.headers
