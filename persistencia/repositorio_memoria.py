from __future__ import annotations

from dataclasses import replace

from .contratos import RascunhoPlanejamentoPersistivel


class ErroAutorizacaoPersistencia(PermissionError):
    pass


class ErroConflitoPersistencia(ValueError):
    pass


class RepositorioPlanejamentosMemoria:
    """Implementação de referência para testar isolamento antes do banco real.

    Não é persistência de produção. O contrato deliberadamente exige o ator em
    toda operação para que um futuro adaptador PostgreSQL/Supabase preserve a
    mesma fronteira de autorização e possa ser protegido por RLS.
    """

    def __init__(self) -> None:
        self._itens: dict[str, RascunhoPlanejamentoPersistivel] = {}

    def salvar(
        self,
        ator_id: str,
        planejamento: RascunhoPlanejamentoPersistivel,
    ) -> RascunhoPlanejamentoPersistivel:
        if not isinstance(planejamento, RascunhoPlanejamentoPersistivel):
            raise TypeError(
                "A fronteira aceita somente RascunhoPlanejamentoPersistivel."
            )
        _exigir_mesmo_proprietario(ator_id, planejamento.proprietario_id)
        existente = self._itens.get(planejamento.planejamento_id)
        if existente is not None and existente.proprietario_id != ator_id:
            raise ErroConflitoPersistencia("Identificador de planejamento indisponível.")
        self._itens[planejamento.planejamento_id] = planejamento
        return planejamento

    def obter(
        self,
        ator_id: str,
        planejamento_id: str,
    ) -> RascunhoPlanejamentoPersistivel | None:
        item = self._itens.get(planejamento_id)
        if item is None or item.proprietario_id != ator_id:
            return None
        return item

    def listar(self, ator_id: str) -> tuple[RascunhoPlanejamentoPersistivel, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._itens.values()
                    if item.proprietario_id == ator_id
                ),
                key=lambda item: item.planejamento_id,
            )
        )

    def renomear(
        self,
        ator_id: str,
        planejamento_id: str,
        titulo: str,
    ) -> RascunhoPlanejamentoPersistivel | None:
        atual = self.obter(ator_id, planejamento_id)
        if atual is None:
            return None
        atualizado = replace(atual, titulo=titulo)
        self._itens[planejamento_id] = atualizado
        return atualizado

    def excluir(self, ator_id: str, planejamento_id: str) -> bool:
        item = self._itens.get(planejamento_id)
        if item is None or item.proprietario_id != ator_id:
            return False
        del self._itens[planejamento_id]
        return True

    def excluir_todos(self, ator_id: str) -> int:
        ids = [
            planejamento_id
            for planejamento_id, item in self._itens.items()
            if item.proprietario_id == ator_id
        ]
        for planejamento_id in ids:
            del self._itens[planejamento_id]
        return len(ids)

    def quantidade_total_para_testes(self) -> int:
        return len(self._itens)


def _exigir_mesmo_proprietario(ator_id: str, proprietario_id: str) -> None:
    if not ator_id or ator_id != proprietario_id:
        raise ErroAutorizacaoPersistencia(
            "Operação de persistência não autorizada para este proprietário."
        )
