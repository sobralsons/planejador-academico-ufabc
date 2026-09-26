from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planejador.academico import auditoria_integralizacao
from planejador.historico import consolidar_historico, ler_historico_sigaa
from planejador.integracao_motor_curricular import (
    ResultadoSombraBCT,
    avaliar_bct_2015_em_modo_sombra,
)
from planejador.multicurso import carregar_registro_curriculos, resolver_curriculo


def executar_comparacao(
    caminho_historico: Path,
    *,
    base: Path = ROOT,
    pacote_piloto_confirmado: bool = False,
    aplicabilidade_confirmada: bool | None = None,
    classificacoes_validadas: bool = False,
) -> ResultadoSombraBCT:
    registro = carregar_registro_curriculos(base)["bct_2015"]
    metadados, curriculo, equivalencias, compostas = resolver_curriculo(
        base, registro
    )
    registros, convalidacoes, resumo = ler_historico_sigaa(caminho_historico)
    situacao = consolidar_historico(
        registros,
        equivalencias,
        compostas,
        convalidacoes,
        resumo,
    )
    confirmadas = situacao.conclusoes_confiaveis()
    legado = auditoria_integralizacao(
        metadados,
        curriculo,
        situacao,
        confirmadas,
        cumpridas_confirmadas=confirmadas,
    )
    resultado = avaliar_bct_2015_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        pacote_piloto_confirmado=pacote_piloto_confirmado,
        aplicabilidade_confirmada=aplicabilidade_confirmada,
        classificacoes_validadas=classificacoes_validadas,
        resultado_legado=legado,
    )
    if resultado is None:
        raise ValueError("O pacote carregado não corresponde ao piloto BC&T 2015.")
    return resultado


def resumir(resultado: ResultadoSombraBCT) -> dict:
    return {
        "modo": resultado.modo,
        "autoridade": resultado.autoridade,
        "publicavel": resultado.publicavel,
        "proveniencia_regras_suficiente": resultado.proveniencia_regras_suficiente,
        "curriculo_id": resultado.curriculo_id,
        "aplicabilidade": resultado.aplicabilidade,
        "estado": resultado.estado,
        "divergencias": {
            requisito_id: asdict(item)
            for requisito_id, item in resultado.divergencias.items()
        },
        "avisos": list(resultado.avisos),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compara internamente o legado com o motor genérico para BC&T 2015."
    )
    parser.add_argument("historico", type=Path, help="Histórico SIGAA em PDF.")
    parser.add_argument(
        "--confirmar-pacote-piloto",
        action="store_true",
        required=True,
        help="Confirma o uso controlado do pacote piloto BC&T 2015.",
    )
    parser.add_argument(
        "--confirmar-aplicabilidade",
        action="store_true",
        help="Confirma que o histórico pertence à matriz BC&T 2015.",
    )
    parser.add_argument(
        "--confirmar-classificacoes",
        action="store_true",
        help="Confirma as classificações curriculares do pacote carregado.",
    )
    parser.add_argument("--base", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    resultado = executar_comparacao(
        args.historico,
        base=args.base,
        pacote_piloto_confirmado=args.confirmar_pacote_piloto,
        aplicabilidade_confirmada=True if args.confirmar_aplicabilidade else None,
        classificacoes_validadas=args.confirmar_classificacoes,
    )
    print(json.dumps(resumir(resultado), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
