from __future__ import annotations

import json
from pathlib import Path

from .modelos import Categoria, DisciplinaCurricular
from .utils import garantir_arquivo, limpar_codigo


def carregar_curriculo(caminho: str | Path) -> tuple[dict, dict[str, DisciplinaCurricular]]:
    path = garantir_arquivo(caminho, "Arquivo de currículo")
    with path.open("r", encoding="utf-8") as arquivo:
        bruto = json.load(arquivo)

    disciplinas: dict[str, DisciplinaCurricular] = {}
    for item in bruto.get("disciplinas", []):
        codigo = limpar_codigo(item["codigo"])
        if codigo in disciplinas:
            raise ValueError(f"Código duplicado no currículo: {codigo}")

        disciplinas[codigo] = DisciplinaCurricular(
            codigo=codigo,
            nome=item["nome"],
            categoria=Categoria(item["categoria"]),
            creditos=int(item["creditos"]),
            t=int(item.get("t", 0)),
            p=int(item.get("p", 0)),
            e=int(item.get("e", 0)),
            i=int(item.get("i", 0)),
            quadrimestre_recomendado=(
                int(item["quadrimestre_recomendado"])
                if item.get("quadrimestre_recomendado") is not None
                else None
            ),
            recomendacoes=tuple(limpar_codigo(c) for c in item.get("recomendacoes", [])),
            recomendacao_texto=item.get("recomendacao_texto", ""),
            requisito_manual=item.get("requisito_manual", ""),
            catalogo_codigo_consulta=item.get("catalogo_codigo_consulta"),
            observacoes=tuple(item.get("observacoes", [])),
        )

    return bruto.get("metadados", {}), disciplinas


def carregar_equivalencias(
    caminho: str | Path,
) -> tuple[dict[str, str], list[tuple[set[str], str]]]:
    path = garantir_arquivo(caminho, "Arquivo de equivalências")
    with path.open("r", encoding="utf-8") as arquivo:
        bruto = json.load(arquivo)

    simples: dict[str, str] = {}
    for origem, destino in bruto.get("equivalencias_academicas", {}).items():
        simples[limpar_codigo(origem)] = limpar_codigo(destino)

    compostas: list[tuple[set[str], str]] = []
    for regra in bruto.get("equivalencias_compostas", []):
        origens = {limpar_codigo(c) for c in regra.get("origens", [])}
        destino = limpar_codigo(regra.get("destino", ""))
        if origens and destino:
            compostas.append((origens, destino))
    return simples, compostas


def carregar_aliases_oferta(caminho: str | Path) -> dict[str, str]:
    path = garantir_arquivo(caminho, "Arquivo de aliases de oferta")
    with path.open("r", encoding="utf-8") as arquivo:
        bruto = json.load(arquivo)

    resultado: dict[str, str] = {}
    for codigo_ofertado, info in bruto.get("aliases_oferta", {}).items():
        if isinstance(info, str):
            resultado[limpar_codigo(codigo_ofertado)] = limpar_codigo(info)
            continue
        if info.get("habilitado", False):
            resultado[limpar_codigo(codigo_ofertado)] = limpar_codigo(
                info["codigo_curriculo"]
            )
    return resultado
