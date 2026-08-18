from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJETO = Path(__file__).resolve().parent.parent
if str(PROJETO) not in sys.path:
    sys.path.insert(0, str(PROJETO))

from planejador.avaliacoes_docentes import gerar_consultas_csv
from planejador.configuracao import carregar_configuracao
from planejador.curriculo import carregar_aliases_oferta, carregar_curriculo, carregar_equivalencias
from planejador.historico import consolidar_historico, ler_historico_sigaa
from planejador.ofertas import ler_ofertas


def resolver(base: Path, caminho: str) -> Path:
    path = Path(caminho)
    return path if path.is_absolute() else base / path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara pares professor–disciplina para o UFABC Next")
    parser.add_argument("--config", type=Path, default=Path("config/config.json"))
    parser.add_argument("--saida", type=Path, default=Path("dados/consultas_ufabc_next.csv"))
    args = parser.parse_args()

    config_path = args.config.resolve()
    base = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent
    config = carregar_configuracao(config_path)
    _, curriculo = carregar_curriculo(resolver(base, config.arquivo_curriculo))
    aliases = carregar_aliases_oferta(resolver(base, config.arquivo_aliases_oferta))
    equivalencias, equivalencias_compostas = carregar_equivalencias(resolver(base, config.arquivo_equivalencias))
    ofertas = ler_ofertas(
        resolver(base, config.arquivo_ofertas),
        codigos_curriculo=set(curriculo),
        nomes_curriculo={c: d.nome for c, d in curriculo.items()},
        aliases_oferta=aliases,
        campus=config.campus,
        turno=config.turno,
        professores_bloqueados=set(),
    )
    codigos_permitidos = None
    caminho_historico = resolver(base, config.arquivo_historico)
    if caminho_historico.exists():
        registros, convalidacoes, resumo = ler_historico_sigaa(caminho_historico)
        situacao = consolidar_historico(
            registros, equivalencias, equivalencias_compostas, convalidacoes, resumo
        )
        cumpridas = situacao.codigos_projetados(
            config.projecao_em_andamento,
            config.disciplinas_em_andamento_assumidas_aprovadas,
        )
        codigos_permitidos = set(curriculo) - set(cumpridas)
    saida = args.saida if args.saida.is_absolute() else base / args.saida
    quantidade = gerar_consultas_csv(
        saida, ofertas.ofertas, curriculo, codigos_permitidos=codigos_permitidos
    )
    print(f"Consultas geradas: {quantidade}")
    print(f"Arquivo: {saida}")
    return 0 if quantidade else 2


if __name__ == "__main__":
    raise SystemExit(main())
