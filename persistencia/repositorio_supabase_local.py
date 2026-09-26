from __future__ import annotations

from dataclasses import replace
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from .contratos import RascunhoPlanejamentoPersistivel
from .repositorio_memoria import ErroAutorizacaoPersistencia


_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ErroPersistenciaSupabaseLocal(RuntimeError):
    pass


class AcessoPersistenciaSupabaseNegado(ErroPersistenciaSupabaseLocal):
    pass


class PersistenciaSupabaseRejeitada(ErroPersistenciaSupabaseLocal):
    pass


class PersistenciaSupabaseIndisponivel(ErroPersistenciaSupabaseLocal):
    pass


class RepositorioPlanejamentosSupabaseLocal:
    """Adaptador local da Data API mantendo o JWT do usuário e o RLS ativos."""

    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        access_token: str,
        user_id: str,
        timeout_segundos: float = 3.0,
    ) -> None:
        parsed = urlparse(supabase_url.rstrip("/"))
        if (
            parsed.scheme != "http"
            or parsed.hostname not in _LOCAL_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Supabase local deve usar endpoint HTTP em loopback.")
        if not publishable_key or not access_token:
            raise ValueError("Credenciais locais de acesso são obrigatórias.")
        try:
            self._user_id = str(UUID(user_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("user_id do Supabase deve ser UUID válido.") from exc

        self._supabase_url = supabase_url.rstrip("/")
        self._publishable_key = publishable_key
        self._access_token = access_token
        self._timeout_segundos = timeout_segundos

    def salvar(
        self,
        ator_id: str,
        planejamento: RascunhoPlanejamentoPersistivel,
    ) -> RascunhoPlanejamentoPersistivel:
        if not isinstance(planejamento, RascunhoPlanejamentoPersistivel):
            raise TypeError(
                "A fronteira aceita somente RascunhoPlanejamentoPersistivel."
            )
        self._exigir_ator(ator_id)
        if planejamento.proprietario_id != self._user_id:
            raise ErroAutorizacaoPersistencia(
                "Operação de persistência não autorizada para este proprietário."
            )

        self._request(
            "POST",
            "/rest/v1/rpc/salvar_planejamento_autenticado",
            body={
                "p_planejamento_id": planejamento.planejamento_id,
                "p_curso_id": planejamento.curso_id,
                "p_matriz_id": planejamento.matriz_id,
                "p_versao_regras": planejamento.versao_regras,
                "p_titulo": planejamento.titulo,
                "p_componentes": list(planejamento.componentes_planejados),
            },
        )
        salvo = self.obter(ator_id, planejamento.planejamento_id)
        if salvo is None:
            raise PersistenciaSupabaseIndisponivel(
                "Planejamento salvo não pôde ser relido."
            )
        return salvo

    def obter(
        self,
        ator_id: str,
        planejamento_id: str,
    ) -> RascunhoPlanejamentoPersistivel | None:
        self._exigir_ator(ator_id)
        _validar_id(planejamento_id)
        payload = self._request(
            "GET",
            "/rest/v1/planejamentos_salvos",
            query={
                "select": (
                    "planejamento_id,proprietario_id,curso_id,matriz_id,"
                    "versao_regras,titulo,schema_version,"
                    "planejamento_componentes(codigo_componente,posicao)"
                ),
                "proprietario_id": f"eq.{self._user_id}",
                "planejamento_id": f"eq.{planejamento_id}",
                "limit": "1",
            },
        )
        itens = _exigir_lista(payload)
        if not itens:
            return None
        if len(itens) != 1:
            raise PersistenciaSupabaseIndisponivel(
                "Resposta inesperada da persistência local."
            )
        return self._converter(itens[0])

    def listar(self, ator_id: str) -> tuple[RascunhoPlanejamentoPersistivel, ...]:
        self._exigir_ator(ator_id)
        payload = self._request(
            "GET",
            "/rest/v1/planejamentos_salvos",
            query={
                "select": (
                    "planejamento_id,proprietario_id,curso_id,matriz_id,"
                    "versao_regras,titulo,schema_version,"
                    "planejamento_componentes(codigo_componente,posicao)"
                ),
                "proprietario_id": f"eq.{self._user_id}",
                "order": "planejamento_id.asc",
            },
        )
        return tuple(self._converter(item) for item in _exigir_lista(payload))

    def renomear(
        self,
        ator_id: str,
        planejamento_id: str,
        titulo: str,
    ) -> RascunhoPlanejamentoPersistivel | None:
        self._exigir_ator(ator_id)
        atual = self.obter(ator_id, planejamento_id)
        if atual is None:
            return None
        atualizado = replace(atual, titulo=titulo)
        payload = self._request(
            "PATCH",
            "/rest/v1/planejamentos_salvos",
            query={
                "proprietario_id": f"eq.{self._user_id}",
                "planejamento_id": f"eq.{planejamento_id}",
            },
            body={"titulo": atualizado.titulo},
            prefer="return=representation",
        )
        if not _exigir_lista(payload):
            return None
        return self.obter(ator_id, planejamento_id)

    def excluir(self, ator_id: str, planejamento_id: str) -> bool:
        self._exigir_ator(ator_id)
        _validar_id(planejamento_id)
        payload = self._request(
            "DELETE",
            "/rest/v1/planejamentos_salvos",
            query={
                "proprietario_id": f"eq.{self._user_id}",
                "planejamento_id": f"eq.{planejamento_id}",
            },
            prefer="return=representation",
        )
        return bool(_exigir_lista(payload))

    def excluir_todos(self, ator_id: str) -> int:
        self._exigir_ator(ator_id)
        payload = self._request(
            "DELETE",
            "/rest/v1/planejamentos_salvos",
            query={"proprietario_id": f"eq.{self._user_id}"},
            prefer="return=representation",
        )
        return len(_exigir_lista(payload))

    def _exigir_ator(self, ator_id: str) -> None:
        if ator_id != self._user_id:
            raise ErroAutorizacaoPersistencia(
                "Operação de persistência não autorizada para este proprietário."
            )

    def _converter(self, item: object) -> RascunhoPlanejamentoPersistivel:
        if not isinstance(item, dict):
            raise PersistenciaSupabaseIndisponivel(
                "Resposta inesperada da persistência local."
            )
        try:
            proprietario_id = str(UUID(str(item["proprietario_id"])))
            if proprietario_id != self._user_id:
                raise PersistenciaSupabaseIndisponivel(
                    "Persistência retornou registro de outro proprietário."
                )
            componentes_brutos = item.get("planejamento_componentes") or []
            if not isinstance(componentes_brutos, list):
                raise TypeError
            componentes_ordenados = sorted(
                componentes_brutos,
                key=lambda componente: int(componente["posicao"]),
            )
            componentes = tuple(
                str(componente["codigo_componente"])
                for componente in componentes_ordenados
            )
            return RascunhoPlanejamentoPersistivel(
                planejamento_id=str(item["planejamento_id"]),
                proprietario_id=proprietario_id,
                curso_id=str(item["curso_id"]),
                matriz_id=str(item["matriz_id"]),
                versao_regras=str(item["versao_regras"]),
                titulo=str(item["titulo"]),
                componentes_planejados=componentes,
                schema_version=int(item["schema_version"]),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise PersistenciaSupabaseIndisponivel(
                "Resposta inesperada da persistência local."
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: object | None = None,
        prefer: str | None = None,
    ) -> object | None:
        url = f"{self._supabase_url}{path}"
        if query:
            url += "?" + urlencode(query, safe="(),.*:-")

        headers = {
            "Accept": "application/json",
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {self._access_token}",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        if prefer:
            headers["Prefer"] = prefer

        request = Request(url, method=method, headers=headers, data=data)
        try:
            with urlopen(request, timeout=self._timeout_segundos) as response:
                conteudo = response.read()
                if response.status < 200 or response.status >= 300:
                    raise PersistenciaSupabaseIndisponivel(
                        "Resposta inesperada da persistência local."
                    )
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise AcessoPersistenciaSupabaseNegado(
                    "Acesso à persistência local foi negado."
                ) from exc
            if exc.code in {400, 409, 422}:
                raise PersistenciaSupabaseRejeitada(
                    "Persistência local rejeitou a operação."
                ) from exc
            raise PersistenciaSupabaseIndisponivel(
                "Persistência local indisponível."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PersistenciaSupabaseIndisponivel(
                "Persistência local indisponível."
            ) from exc

        if not conteudo:
            return None
        try:
            return json.loads(conteudo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PersistenciaSupabaseIndisponivel(
                "Resposta inválida da persistência local."
            ) from exc


def _validar_id(valor: str) -> None:
    if not isinstance(valor, str) or not _ID_RE.fullmatch(valor):
        raise ValueError("planejamento_id inválido.")


def _exigir_lista(payload: object | None) -> list[dict]:
    if not isinstance(payload, list):
        raise PersistenciaSupabaseIndisponivel(
            "Resposta inesperada da persistência local."
        )
    return payload
