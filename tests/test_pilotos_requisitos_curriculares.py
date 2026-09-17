import json
from pathlib import Path

import pytest

from planejador.requisitos_curriculares import (
    FonteRegra,
    GrupoRequisitos,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorGrupo,
    ReferenciaCursoBase,
    RegraCompartilhamento,
    RequisitoQuantitativo,
    RestricaoContribuicao,
    SeletorComponentes,
    SequenciaRequisitos,
    TipoIntegralizador,
    UnidadeRequisito,
)


BASE = Path(__file__).resolve().parents[1]
PILOTOS = BASE / "dados" / "pilotos_requisitos_curriculares_2026-09-16.json"


def _dados():
    return json.loads(PILOTOS.read_text(encoding="utf-8"))


def _piloto(curso_id: str):
    return next(item for item in _dados()["pilotos"] if item["curso_id"] == curso_id)


def _fonte(item, indice: int = 0):
    return FonteRegra(
        titulo=f"Fonte oficial {item['curso_id']} {item['matriz_id']}",
        url=item["fontes"][indice],
        referencia="regra estrutural validada no piloto",
    )


def _req(
    id_: str,
    integralizador: TipoIntegralizador,
    unidade: UnidadeRequisito,
    minimo: int,
    *,
    maximo: int | None = None,
    codigos=(),
    tags=(),
    origens=(),
    fonte: FonteRegra,
):
    return RequisitoQuantitativo(
        id=id_,
        descricao=id_.replace("_", " "),
        integralizador=integralizador,
        seletor=SeletorComponentes(
            codigos=frozenset(codigos),
            tags=frozenset(tags),
            origens=frozenset(origens),
        ),
        limite=LimiteQuantitativo(unidade, minimo, maximo),
        fontes=(fonte,),
    )


def _contrib(
    id_: str,
    requisito_total: str,
    unidade: UnidadeRequisito,
    minimo: int,
    *,
    maximo: int | None = None,
    codigos=(),
    tags=(),
    origens=(),
    fonte: FonteRegra,
):
    return RestricaoContribuicao(
        id=id_,
        descricao=id_.replace("_", " "),
        requisito_total=requisito_total,
        seletor=SeletorComponentes(
            codigos=frozenset(codigos),
            tags=frozenset(tags),
            origens=frozenset(origens),
        ),
        limite=LimiteQuantitativo(unidade, minimo, maximo),
        fontes=(fonte,),
    )


def test_artefato_pilotos_usa_fontes_oficiais_e_nao_declara_suporte():
    dados = _dados()

    assert dados["avaliado_em"] == "2026-09-16"
    assert len(dados["pilotos"]) == 5
    assert "Não constitui modelagem completa" in dados["escopo"]
    assert {x["id"] for x in dados["lacunas_encontradas_no_modelo_anterior"]} == {
        "composicao_quantitativa",
        "sobreposicao_minima",
    }

    for piloto in dados["pilotos"]:
        assert piloto["fontes"]
        for url in piloto["fontes"]:
            assert url.startswith("https://")
            assert "ufabc.edu.br" in url


def test_bcc_2023_representa_extensao_composta_curso_base_e_tcc_sem_estagio_obrigatorio():
    item = _piloto("ciencia_computacao")
    regras = item["regras_validadas"]
    fonte = _fonte(item)

    requisitos = (
        _req(
            "disciplinas_total",
            TipoIntegralizador.COMPONENTES_CURRICULARES,
            UnidadeRequisito.CREDITOS,
            regras["creditos_disciplinas"],
            tags=("disciplinas_bcc",),
            fonte=fonte,
        ),
        _req(
            "extensao_total",
            TipoIntegralizador.EXTENSAO,
            UnidadeRequisito.HORAS,
            regras["extensao_total_horas"],
            tags=("extensao",),
            fonte=fonte,
        ),
        _req(
            "atividades_complementares",
            TipoIntegralizador.ATIVIDADES_COMPLEMENTARES,
            UnidadeRequisito.HORAS,
            regras["atividades_complementares_bct_horas"],
            origens=("bct_2023",),
            fonte=fonte,
        ),
        _req(
            "tcc",
            TipoIntegralizador.TCC,
            UnidadeRequisito.CREDITOS,
            regras["tcc_creditos"],
            codigos=("MCCC017-23",),
            fonte=fonte,
        ),
    )
    contribuicoes = (
        _contrib(
            "extensao_bct",
            "extensao_total",
            UnidadeRequisito.HORAS,
            regras["extensao_bct_horas"],
            maximo=regras["extensao_bct_horas"],
            origens=("bct_2023",),
            fonte=fonte,
        ),
        _contrib(
            "extensao_bcc",
            "extensao_total",
            UnidadeRequisito.HORAS,
            regras["extensao_bcc_horas"],
            maximo=regras["extensao_bcc_horas"],
            origens=("bcc_2023",),
            fonte=fonte,
        ),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id=item["curso_id"],
        matriz_id=item["matriz_id"],
        requisitos=requisitos,
        contribuicoes=contribuicoes,
        cursos_base=(
            ReferenciaCursoBase(
                curso_id="bct",
                matriz_id="2023",
                requisitos_reutilizados=(
                    "atividades_complementares",
                    "extensao_bct",
                ),
                exigir_conclusao_base=True,
                fontes=(fonte,),
            ),
        ),
        fontes_gerais=(fonte,),
    )

    assert regras["estagio_obrigatorio"] is False
    assert not any(r.integralizador == TipoIntegralizador.ESTAGIO for r in modelo.requisitos)
    assert sum(c.limite.minimo for c in modelo.contribuicoes) == regras["extensao_total_horas"]


def test_engenharia_materiais_2023_representa_estagio_168h_e_tg_multietapas():
    item = _piloto("engenharia_materiais")
    regras = item["regras_validadas"]
    fonte = _fonte(item)

    estagio = _req(
        "estagio",
        TipoIntegralizador.ESTAGIO,
        UnidadeRequisito.HORAS,
        regras["estagio_obrigatorio_horas"],
        tags=("estagio_curricular",),
        fonte=fonte,
    )
    tg = tuple(
        _req(
            f"tg_{n}",
            TipoIntegralizador.TCC,
            UnidadeRequisito.COMPONENTES,
            1,
            tags=(f"tg_{n}",),
            fonte=fonte,
        )
        for n in (1, 2, 3)
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id=item["curso_id"],
        matriz_id=item["matriz_id"],
        requisitos=(estagio, *tg),
        sequencias=(
            SequenciaRequisitos(
                id="tg_multietapas",
                descricao="Trabalho de Graduação em etapas",
                etapas=("tg_1", "tg_2", "tg_3"),
                ordem_obrigatoria=False,
                fontes=(fonte,),
            ),
        ),
        cursos_base=(
            ReferenciaCursoBase(
                curso_id="bct",
                matriz_id="2023",
                requisitos_reutilizados=("atividades_complementares_48h",),
                fontes=(fonte,),
            ),
        ),
    )

    assert modelo.requisitos[0].limite.minimo == 168
    assert modelo.sequencias[0].etapas == ("tg_1", "tg_2", "tg_3")


def test_lec_2024_representa_composicao_dos_400h_e_160h_de_sobreposicao_obrigatoria():
    item = _piloto("lec_ciencias_humanas_sociais")
    regras = item["regras_validadas"]
    fonte = _fonte(item)

    estagio_total = _req(
        "estagio_total",
        TipoIntegralizador.ESTAGIO,
        UnidadeRequisito.HORAS,
        regras["estagio_total_horas"],
        tags=("estagio_supervisionado",),
        fonte=fonte,
    )
    extensao_estagio = _req(
        "extensao_estagio",
        TipoIntegralizador.EXTENSAO,
        UnidadeRequisito.HORAS,
        regras["estagio_extensionista_horas"],
        maximo=regras["estagio_extensionista_horas"],
        tags=("estagio_extensionista",),
        fonte=fonte,
    )
    modulo_iv = _req(
        "modulo_iv",
        TipoIntegralizador.FORMACAO_DOCENTE,
        UnidadeRequisito.COMPONENTES,
        1,
        codigos=("ESTAGIO_CH_IV",),
        fonte=fonte,
    )
    modulo_viii = _req(
        "modulo_viii",
        TipoIntegralizador.FORMACAO_DOCENTE,
        UnidadeRequisito.COMPONENTES,
        1,
        codigos=("ESTAGIO_CH_VIII",),
        fonte=fonte,
    )
    modulo_ix = _req(
        "modulo_ix",
        TipoIntegralizador.FORMACAO_DOCENTE,
        UnidadeRequisito.COMPONENTES,
        1,
        codigos=("ESTAGIO_LEC_IX",),
        fonte=fonte,
    )

    contribuicoes = (
        _contrib(
            "estagios_lch",
            "estagio_total",
            UnidadeRequisito.HORAS,
            regras["estagios_lch_modulos_i_ii_iii_horas"],
            maximo=regras["estagios_lch_modulos_i_ii_iii_horas"],
            origens=("lch",),
            fonte=fonte,
        ),
        _contrib(
            "estagio_historia",
            "estagio_total",
            UnidadeRequisito.HORAS,
            regras["estagio_modulo_iv_ou_viii_horas"],
            maximo=regras["estagio_modulo_iv_ou_viii_horas"],
            codigos=("ESTAGIO_CH_IV", "ESTAGIO_CH_VIII"),
            fonte=fonte,
        ),
        _contrib(
            "estagio_campo",
            "estagio_total",
            UnidadeRequisito.HORAS,
            regras["estagio_modulo_ix_horas"],
            maximo=regras["estagio_modulo_ix_horas"],
            codigos=("ESTAGIO_LEC_IX",),
            fonte=fonte,
        ),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id=item["curso_id"],
        matriz_id=item["matriz_id"],
        requisitos=(estagio_total, extensao_estagio, modulo_iv, modulo_viii, modulo_ix),
        contribuicoes=contribuicoes,
        grupos=(
            GrupoRequisitos(
                id="escolha_historia",
                descricao="Módulo IV ou VIII",
                requisitos=("modulo_iv", "modulo_viii"),
                operador=OperadorGrupo.QUALQUER,
                fontes=(fonte,),
            ),
        ),
        compartilhamentos=(
            RegraCompartilhamento(
                requisito_a="estagio_total",
                requisito_b="extensao_estagio",
                unidade=UnidadeRequisito.HORAS,
                minimo_compartilhavel=regras["estagio_extensionista_horas"],
                maximo_compartilhavel=regras["estagio_extensionista_horas"],
                fontes=(fonte,),
            ),
        ),
        cursos_base=(
            ReferenciaCursoBase(
                curso_id="lch",
                matriz_id="2022",
                requisitos_reutilizados=("estagios_modulos_i_ii_iii",),
                fontes=(fonte,),
            ),
        ),
    )

    assert sum(c.limite.minimo for c in modelo.contribuicoes) == 400
    assert modelo.compartilhamentos[0].minimo_compartilhavel == 160
    assert modelo.compartilhamentos[0].maximo_compartilhavel == 160
    assert modelo.grupos[0].operador == OperadorGrupo.QUALQUER


def test_licenciatura_matematica_2023_representa_as_tres_fontes_das_323h_de_extensao():
    item = _piloto("matematica_licenciatura")
    regras = item["regras_validadas"]
    fonte = _fonte(item, 2)

    extensao = _req(
        "extensao_total",
        TipoIntegralizador.EXTENSAO,
        UnidadeRequisito.HORAS,
        regras["extensao_total_horas"],
        tags=("extensao",),
        fonte=fonte,
    )
    contribuicoes = (
        _contrib(
            "extensao_ingresso",
            "extensao_total",
            UnidadeRequisito.HORAS,
            regras["extensao_curso_ingresso_horas"],
            maximo=regras["extensao_curso_ingresso_horas"],
            origens=("curso_ingresso",),
            fonte=fonte,
        ),
        _contrib(
            "extensao_estagios",
            "extensao_total",
            UnidadeRequisito.HORAS,
            regras["extensao_estagios_horas"],
            maximo=regras["extensao_estagios_horas"],
            tags=("estagio_extensionista",),
            fonte=fonte,
        ),
        _contrib(
            "extensao_outras_fontes",
            "extensao_total",
            UnidadeRequisito.HORAS,
            regras["extensao_outras_fontes_horas"],
            maximo=regras["extensao_outras_fontes_horas"],
            tags=("ol_evento_projeto_curso_acao",),
            fonte=fonte,
        ),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id=item["curso_id"],
        matriz_id=item["matriz_id"],
        requisitos=(extensao,),
        contribuicoes=contribuicoes,
        fontes_gerais=(fonte,),
    )

    assert sum(c.limite.minimo for c in modelo.contribuicoes) == 323
    assert regras["atividades_complementares_ppc_2023"] is False
    assert not any(
        r.integralizador == TipoIntegralizador.ATIVIDADES_COMPLEMENTARES
        for r in modelo.requisitos
    )


def test_bpp_2023_representa_imersao_extensionista_sem_confundir_creditos_com_horas():
    item = _piloto("politicas_publicas")
    regras = item["regras_validadas"]
    fonte = _fonte(item)

    extensao = _req(
        "extensao_total",
        TipoIntegralizador.EXTENSAO,
        UnidadeRequisito.HORAS,
        regras["extensao_total_horas"],
        tags=("extensao",),
        fonte=fonte,
    )
    imersao = _req(
        "imersao",
        TipoIntegralizador.COMPONENTES_CURRICULARES,
        UnidadeRequisito.CREDITOS,
        regras["imersao_creditos"],
        codigos=("IMERSAO_BPP",),
        fonte=fonte,
    )
    tcc = _req(
        "tcc",
        TipoIntegralizador.TCC,
        UnidadeRequisito.CREDITOS,
        regras["tcc_creditos"],
        tags=("tcc_bpp",),
        fonte=fonte,
    )
    contribuicoes = (
        _contrib(
            "atividades_extensao",
            "extensao_total",
            UnidadeRequisito.HORAS,
            regras["extensao_atividades_horas"],
            maximo=regras["extensao_atividades_horas"],
            tags=("atividades_extensao",),
            fonte=fonte,
        ),
        _contrib(
            "imersao_extensionista",
            "extensao_total",
            UnidadeRequisito.HORAS,
            regras["imersao_extensionista_horas"],
            maximo=regras["imersao_extensionista_horas"],
            codigos=("IMERSAO_BPP",),
            fonte=fonte,
        ),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id=item["curso_id"],
        matriz_id=item["matriz_id"],
        requisitos=(extensao, imersao, tcc),
        contribuicoes=contribuicoes,
        cursos_base=(
            ReferenciaCursoBase(
                curso_id="bch",
                matriz_id="2022",
                requisitos_reutilizados=("atividades_complementares_48h",),
                fontes=(fonte,),
            ),
        ),
    )

    assert sum(c.limite.minimo for c in modelo.contribuicoes) == 312
    assert imersao.limite.unidade == UnidadeRequisito.CREDITOS
    assert modelo.contribuicoes[1].limite.unidade == UnidadeRequisito.HORAS
    assert modelo.compartilhamentos == ()


def test_rejeita_contribuicao_inexistente_unidade_incompativel_e_sobreposicao_invalida():
    item = _piloto("lec_ciencias_humanas_sociais")
    fonte = _fonte(item)
    total = _req(
        "total",
        TipoIntegralizador.ESTAGIO,
        UnidadeRequisito.HORAS,
        400,
        tags=("estagio",),
        fonte=fonte,
    )

    inexistente = _contrib(
        "parte",
        "nao_existe",
        UnidadeRequisito.HORAS,
        80,
        tags=("parte",),
        fonte=fonte,
    )
    with pytest.raises(ValueError, match="regras inexistentes"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2024",
            requisitos=(total,),
            contribuicoes=(inexistente,),
        )

    unidade_errada = _contrib(
        "parte",
        "total",
        UnidadeRequisito.CREDITOS,
        4,
        tags=("parte",),
        fonte=fonte,
    )
    with pytest.raises(ValueError, match="mesma unidade"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2024",
            requisitos=(total,),
            contribuicoes=(unidade_errada,),
        )

    with pytest.raises(ValueError, match="Mínimo compartilhável"):
        RegraCompartilhamento(
            requisito_a="a",
            requisito_b="b",
            unidade=UnidadeRequisito.HORAS,
            minimo_compartilhavel=161,
            maximo_compartilhavel=160,
        )

    outro = _req(
        "outro",
        TipoIntegralizador.EXTENSAO,
        UnidadeRequisito.CREDITOS,
        4,
        tags=("extensao",),
        fonte=fonte,
    )
    with pytest.raises(ValueError, match="mesma unidade"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2024",
            requisitos=(total, outro),
            compartilhamentos=(
                RegraCompartilhamento(
                    requisito_a="total",
                    requisito_b="outro",
                    unidade=UnidadeRequisito.HORAS,
                    maximo_compartilhavel=10,
                ),
            ),
        )
