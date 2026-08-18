import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_pacotes_batem_com_manifesto_oficial_validado():
    manifesto = json.loads((BASE / "dados" / "validacao_curriculos.json").read_text(encoding="utf-8"))
    for id_, esperado in manifesto["curriculos"].items():
        bruto = json.loads((BASE / esperado["arquivo"]).read_text(encoding="utf-8"))
        for categoria, meta in esperado["categorias"].items():
            itens = [d for d in bruto["disciplinas"] if d["categoria"] == categoria]
            codigos = sorted(d["codigo"] for d in itens)
            assert len(codigos) == meta["quantidade_componentes"], id_
            assert sum(d["creditos"] for d in itens) == meta["soma_creditos_cadastrados"], id_
            assert hashlib.sha256("|".join(codigos).encode()).hexdigest() == meta["sha256_codigos_ordenados"], id_
