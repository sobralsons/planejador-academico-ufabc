from __future__ import annotations

import json
from pathlib import Path

from .requisitos_curriculares import (
    FonteRegra,
    GrupoRequisitos,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorGrupo,
    ReferenciaCursoBase,
    RequisitoQuantitativo,
    RestricaoContribuicao,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


_CAMPOS_SUPORTADOS = {
    "schema_version",
    "curso_id",
    "matriz_id",
    "metadados",
    "fontes",
    "requisitos",
    "contribuicoes",
    "grupos",
    "cursos_base",
}


def carregar_modelo_curricular(caminho: str | Path) -> ModeloRequisitosCurriculares:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if dados.get("schema_version") != 1:
        raise ValueError("schema_version de modelo curricular não suportada.")
    desconhecidos = set(dados) - _CAMPOS_SUPORTADOS
    if desconhecidos:
        nomes = ", ".join(sorted(desconhecidos))
        raise ValueError(f"Campos de modelo curricular não suportados: {nomes}.")

    fontes = {
        id_: FonteRegra(**conteudo)
        for id_, conteudo in dados.get("fontes", {}).items()
    }

    def fontes_de(item: dict) -> tuple[FonteRegra, ...]:
        try:
            return tuple(fontes[id_] for id_ in item.get("fontes", ()))
        except KeyError as erro:
            raise ValueError(f"Fonte curricular desconhecida: {erro.args[0]}") from erro

    requisitos = tuple(
        RequisitoQuantitativo(
            id=item["id"],
            descricao=item["descricao"],
            integralizador=TipoIntegralizador(item["integralizador"]),
            seletor=_seletor(item["seletor"]),
            limite=_limite(item["limite"]),
            fontes=fontes_de(item),
            observacoes=tuple(item.get("observacoes", ())),
        )
        for item in dados.get("requisitos", ())
    )
    contribuicoes = tuple(
        RestricaoContribuicao(
            id=item["id"],
            descricao=item["descricao"],
            requisito_total=item["requisito_total"],
            seletor=_seletor(item["seletor"]),
            limite=_limite(item["limite"]),
            fontes=fontes_de(item),
            observacoes=tuple(item.get("observacoes", ())),
        )
        for item in dados.get("contribuicoes", ())
    )
    grupos = tuple(
        GrupoRequisitos(
            id=item["id"],
            descricao=item["descricao"],
            requisitos=tuple(item["requisitos"]),
            operador=OperadorGrupo(item["operador"]),
            minimo_requisitos=item.get("minimo_requisitos"),
            maximo_requisitos=item.get("maximo_requisitos"),
            fontes=fontes_de(item),
        )
        for item in dados.get("grupos", ())
    )
    cursos_base = tuple(
        ReferenciaCursoBase(
            curso_id=item["curso_id"],
            matriz_id=item["matriz_id"],
            requisitos_reutilizados=tuple(item.get("requisitos_reutilizados", ())),
            exigir_conclusao_base=item.get("exigir_conclusao_base", False),
            permitir_reuso_de_componentes=item.get(
                "permitir_reuso_de_componentes", True
            ),
            fontes=fontes_de(item),
        )
        for item in dados.get("cursos_base", ())
    )
    metadados = tuple(
        (str(chave), str(valor)) for chave, valor in dados.get("metadados", {}).items()
    )

    return ModeloRequisitosCurriculares(
        curso_id=dados["curso_id"],
        matriz_id=str(dados["matriz_id"]),
        requisitos=requisitos,
        contribuicoes=contribuicoes,
        grupos=grupos,
        cursos_base=cursos_base,
        fontes_gerais=tuple(fontes.values()),
        metadados=metadados,
    )


def _seletor(dados: dict) -> SeletorComponentes:
    return SeletorComponentes(
        codigos=frozenset(dados.get("codigos", ())),
        categorias=frozenset(dados.get("categorias", ())),
        tipos=frozenset(dados.get("tipos", ())),
        tags=frozenset(dados.get("tags", ())),
        origens=frozenset(dados.get("origens", ())),
        qualquer_componente=dados.get("qualquer_componente", False),
    )


def _limite(dados: dict) -> LimiteQuantitativo:
    return LimiteQuantitativo(
        unidade=UnidadeRequisito(dados["unidade"]),
        minimo=dados["minimo"],
        maximo=dados.get("maximo"),
    )
