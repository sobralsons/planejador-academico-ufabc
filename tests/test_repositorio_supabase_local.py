import json
from urllib.error import HTTPError

import pytest

from persistencia import (
    AcessoPersistenciaSupabaseNegado,
    ErroAutorizacaoPersistencia,
    PersistenciaSupabaseIndisponivel,
    RascunhoPlanejamentoPersistivel,
    RepositorioPlanejamentosSupabaseLocal,
)
from persistencia import repositorio_supabase_local as supabase_repo


USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


class _RespostaFake:
    def __init__(self, payload=None, status=200):
        self.status = status
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read(self):
        if self._payload is None:
            return b""
        return json.dumps(self._payload).encode("utf-8")


def _repo(user_id=USER_A):
    return RepositorioPlanejamentosSupabaseLocal(
        supabase_url="http://127.0.0.1:54321",
        publishable_key="sb_publishable_teste",
        access_token="token-usuario",
        user_id=user_id,
    )


def _plano(owner=USER_A):
    return RascunhoPlanejamentoPersistivel(
        planejamento_id="plano-1",
        proprietario_id=owner,
        curso_id="ciencia_dados",
        matriz_id="2023",
        versao_regras="v1",
        titulo="Meu plano",
        componentes_planejados=("A", "B"),
    )


def _row(owner=USER_A, titulo="Meu plano", componentes=None):
    if componentes is None:
        componentes = [
            {"codigo_componente": "A", "posicao": 1},
            {"codigo_componente": "B", "posicao": 2},
        ]
    return {
        "planejamento_id": "plano-1",
        "proprietario_id": owner,
        "curso_id": "ciencia_dados",
        "matriz_id": "2023",
        "versao_regras": "v1",
        "titulo": titulo,
        "schema_version": 1,
        "planejamento_componentes": componentes,
    }


def test_adaptador_recusa_endpoint_supabase_remoto():
    with pytest.raises(ValueError, match="loopback"):
        RepositorioPlanejamentosSupabaseLocal(
            supabase_url="https://projeto.supabase.co",
            publishable_key="publica",
            access_token="token",
            user_id=USER_A,
        )


def test_salvar_usa_rpc_sem_proprietario_no_payload_e_rele_com_mesmo_token(monkeypatch):
    chamadas = []
    respostas = [
        _RespostaFake(status=204),
        _RespostaFake([_row()]),
    ]

    def urlopen_fake(request, timeout):
        chamadas.append((request, timeout))
        return respostas.pop(0)

    monkeypatch.setattr(supabase_repo, "urlopen", urlopen_fake)

    salvo = _repo().salvar(USER_A, _plano())

    assert salvo == _plano()
    primeira, timeout = chamadas[0]
    assert primeira.get_method() == "POST"
    assert primeira.full_url.endswith(
        "/rest/v1/rpc/salvar_planejamento_autenticado"
    )
    payload = json.loads(primeira.data.decode("utf-8"))
    assert "proprietario_id" not in payload
    assert payload["p_planejamento_id"] == "plano-1"
    assert payload["p_componentes"] == ["A", "B"]
    headers = {k.lower(): v for k, v in primeira.header_items()}
    assert headers["authorization"] == "Bearer token-usuario"
    assert headers["apikey"] == "sb_publishable_teste"
    assert timeout == 3.0


def test_adaptador_rejeita_ator_diferente_antes_de_chamar_supabase(monkeypatch):
    monkeypatch.setattr(
        supabase_repo,
        "urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("não deveria acessar Supabase")
        ),
    )

    with pytest.raises(ErroAutorizacaoPersistencia):
        _repo().obter(USER_B, "plano-1")


def test_salvar_rejeita_proprietario_forjado_antes_do_supabase(monkeypatch):
    monkeypatch.setattr(
        supabase_repo,
        "urlopen",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("não deveria acessar Supabase")
        ),
    )

    with pytest.raises(ErroAutorizacaoPersistencia):
        _repo().salvar(USER_A, _plano(owner=USER_B))


def test_leitura_rejeita_registro_de_outro_proprietario_mesmo_se_upstream_vazar(monkeypatch):
    monkeypatch.setattr(
        supabase_repo,
        "urlopen",
        lambda *_a, **_kw: _RespostaFake([_row(owner=USER_B)]),
    )

    with pytest.raises(PersistenciaSupabaseIndisponivel, match="outro proprietário"):
        _repo().obter(USER_A, "plano-1")


def test_componentes_sao_reconstruidos_pela_posicao(monkeypatch):
    linha = _row(
        componentes=[
            {"codigo_componente": "B", "posicao": 2},
            {"codigo_componente": "A", "posicao": 1},
        ]
    )
    monkeypatch.setattr(
        supabase_repo,
        "urlopen",
        lambda *_a, **_kw: _RespostaFake([linha]),
    )

    plano = _repo().obter(USER_A, "plano-1")

    assert plano is not None
    assert plano.componentes_planejados == ("A", "B")


def test_403_da_data_api_vira_erro_generico_sem_ecoar_corpo(monkeypatch):
    segredo = "DETALHE-SQL-SENSIVEL"

    def urlopen_fake(request, timeout):
        raise HTTPError(
            request.full_url,
            403,
            segredo,
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(supabase_repo, "urlopen", urlopen_fake)

    with pytest.raises(AcessoPersistenciaSupabaseNegado) as erro:
        _repo().listar(USER_A)

    assert segredo not in str(erro.value)


def test_excluir_filtra_explicitamente_pelo_usuario_vinculado(monkeypatch):
    capturado = {}

    def urlopen_fake(request, timeout):
        capturado["request"] = request
        return _RespostaFake([_row()])

    monkeypatch.setattr(supabase_repo, "urlopen", urlopen_fake)

    assert _repo().excluir(USER_A, "plano-1") is True
    url = capturado["request"].full_url
    assert "proprietario_id=eq." + USER_A in url
    assert "planejamento_id=eq.plano-1" in url
