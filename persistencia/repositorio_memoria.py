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
        self._itens: dict[tuple[str, str], RascunhoPlanejamentoPersistivel] = {}

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
        self._itens[(ator_id, planejamento.planejamento_id)] = planejamento
        return planejamento

    def obter(
        self,
        ator_id: str,
        planejamento_id: str,
    ) -> RascunhoPlanejamentoPersistivel | None:
        return self._itens.get((ator_id, planejamento_id))

    def listar(self, ator_id: str) -> tuple[RascunhoPlanejamentoPersistivel, ...]:
        return tuple(
            sorted(
                (
                    item
                    for (proprietario_id, _), item in self._itens.items()
                    if proprietario_id == ator_id
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
        self._itens[(ator_id, planejamento_id)] = atualizado
        return atualizado

    def excluir(self, ator_id: str, planejamento_id: str) -> bool:
        chave = (ator_id, planejamento_id)
        if chave not in self._itens:
            return False
        del self._itens[chave]
        return True

    def excluir_todos(self, ator_id: str) -> int:
        chaves = [
            chave
            for chave in self._itens
            if chave[0] == ator_id
        ]
        for chave in chaves:
            del self._itens[chave]
        return len(chaves)

    def quantidade_total_para_testes(self) -> int:
        return len(self._itens)


def _exigir_mesmo_proprietario(ator_id: str, proprietario_id: str) -> None:
    if not ator_id or ator_id != proprietario_id:
        raise ErroAutorizacaoPersistencia(
            "Operação de persistência não autorizada para este proprietário."
        )
