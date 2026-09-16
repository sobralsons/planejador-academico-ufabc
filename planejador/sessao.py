"""Arquivos temporários de uma sessão local da interface."""
from pathlib import Path
from tempfile import TemporaryDirectory


class ArquivosSessao:
    def __init__(self):
        self._temporario = TemporaryDirectory(prefix="ufabc-planner-")
        self.raiz = Path(self._temporario.name)
        self.entradas = self.raiz / "entradas"
        self.saidas = self.raiz / "saidas"
        self.dados = self.raiz / "dados"
        self.configuracao = self.raiz / "config_interface.json"
        for pasta in (self.entradas, self.saidas, self.dados):
            pasta.mkdir()

    def limpar(self):
        self._temporario.cleanup()
