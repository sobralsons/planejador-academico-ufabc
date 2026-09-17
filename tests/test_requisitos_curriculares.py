import pytest

from planejador.requisitos_curriculares import (
    CondicaoCurricular,
    FonteRegra,
    GrupoRequisitos,
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    OperadorCondicao,
    OperadorGrupo,
    ReferenciaCursoBase,
    RegraAplicabilidade,
    RegraCompartilhamento,
    RegraCondicional,
    RequisitoQuantitativo,
    SeletorComponentes,
    SequenciaRequisitos,
    TipoIntegralizador,
    UnidadeRequisito,
)


FONTE = FonteRegra(
    titulo="Documento oficial UFABC",
    url="https://www.ufabc.edu.br/documento-oficial.pdf",
    referencia="seção de teste",
)


def requisito(
    id_: str,
    integralizador: TipoIntegralizador,
    unidade: UnidadeRequisito,
    minimo: int,
    *,
    codigos: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    maximo: int | None = None,
) -> RequisitoQuantitativo:
    return RequisitoQuantitativo(
        id=id_,
        descricao=f"Regra {id_}",
        integralizador=integralizador,
        seletor=SeletorComponentes(
            codigos=frozenset(codigos),
            tags=frozenset(tags),
        ),
        limite=LimiteQuantitativo(unidade, minimo, maximo),
        fontes=(FONTE,),
    )


def test_representa_estagio_em_horas_e_tcc_em_etapas_sem_acoplar_ao_solver():
    estagio = requisito(
        "estagio",
        TipoIntegralizador.ESTAGIO,
        UnidadeRequisito.HORAS,
        168,
        tags=("estagio",),
    )
    tg1 = requisito(
        "tg1",
        TipoIntegralizador.TCC,
        UnidadeRequisito.COMPONENTES,
        1,
        codigos=("TG1",),
    )
    tg2 = requisito(
        "tg2",
        TipoIntegralizador.TCC,
        UnidadeRequisito.COMPONENTES,
        1,
        codigos=("TG2",),
    )
    tg3 = requisito(
        "tg3",
        TipoIntegralizador.TCC,
        UnidadeRequisito.COMPONENTES,
        1,
        codigos=("TG3",),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id="engenharia_teste",
        matriz_id="2023",
        requisitos=(estagio, tg1, tg2, tg3),
        sequencias=(
            SequenciaRequisitos(
                id="tcc_etapas",
                descricao="Etapas do trabalho de graduação",
                etapas=("tg1", "tg2", "tg3"),
                ordem_obrigatoria=False,
                fontes=(FONTE,),
            ),
        ),
    )

    assert modelo.compartilhamento_padrao_proibido is True
    assert modelo.sequencias[0].etapas == ("tg1", "tg2", "tg3")
    assert modelo.requisitos[0].limite.minimo == 168


def test_representa_licenciatura_com_formacao_docente_grupo_de_escolha_e_estagio():
    estagio = requisito(
        "estagio_docencia",
        TipoIntegralizador.ESTAGIO,
        UnidadeRequisito.HORAS,
        400,
        tags=("estagio_docencia",),
    )
    pratica_a = requisito(
        "pratica_a",
        TipoIntegralizador.FORMACAO_DOCENTE,
        UnidadeRequisito.COMPONENTES,
        1,
        tags=("pratica_ensino_a",),
    )
    pratica_b = requisito(
        "pratica_b",
        TipoIntegralizador.FORMACAO_DOCENTE,
        UnidadeRequisito.COMPONENTES,
        1,
        tags=("pratica_ensino_b",),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id="licenciatura_teste",
        matriz_id="2023",
        requisitos=(estagio, pratica_a, pratica_b),
        grupos=(
            GrupoRequisitos(
                id="escolha_pratica",
                descricao="Escolher ao menos uma prática",
                requisitos=("pratica_a", "pratica_b"),
                operador=OperadorGrupo.MINIMO,
                minimo_requisitos=1,
                fontes=(FONTE,),
            ),
        ),
    )

    assert modelo.grupos[0].minimo_requisitos == 1
    assert estagio.limite.unidade == UnidadeRequisito.HORAS


def test_extensao_admite_multiplas_fontes_limites_e_sobreposicao_somente_explicita():
    extensao_componentes = requisito(
        "extensao_componentes",
        TipoIntegralizador.EXTENSAO,
        UnidadeRequisito.HORAS,
        120,
        tags=("extensao",),
        maximo=240,
    )
    extensao_estagio = requisito(
        "extensao_estagio",
        TipoIntegralizador.EXTENSAO,
        UnidadeRequisito.HORAS,
        40,
        tags=("estagio_extensionista",),
        maximo=80,
    )
    estagio = requisito(
        "estagio",
        TipoIntegralizador.ESTAGIO,
        UnidadeRequisito.HORAS,
        168,
        tags=("estagio",),
    )

    modelo = ModeloRequisitosCurriculares(
        curso_id="curso_extensao_teste",
        matriz_id="2023",
        requisitos=(extensao_componentes, extensao_estagio, estagio),
        compartilhamentos=(
            RegraCompartilhamento(
                requisito_a="extensao_estagio",
                requisito_b="estagio",
                unidade=UnidadeRequisito.HORAS,
                maximo_compartilhavel=80,
                fontes=(FONTE,),
            ),
        ),
    )

    assert modelo.compartilhamento_padrao_proibido
    assert modelo.compartilhamentos[0].maximo_compartilhavel == 80


def test_representa_reuso_de_curso_base_e_regra_condicional_de_oferta_especial():
    optativa_regular = requisito(
        "optativa_regular",
        TipoIntegralizador.GRUPO_ESCOLHA,
        UnidadeRequisito.CREDITOS,
        12,
        tags=("opcao_limitada",),
    )
    optativa_especial = requisito(
        "optativa_especial",
        TipoIntegralizador.GRUPO_ESCOLHA,
        UnidadeRequisito.CREDITOS,
        8,
        tags=("oferta_especial",),
    )

    condicao = CondicaoCurricular(
        campo="modalidade_ingresso",
        operador=OperadorCondicao.IGUAL,
        valor="oferta_especial",
    )
    modelo = ModeloRequisitosCurriculares(
        curso_id="curso_teste",
        matriz_id="2026",
        requisitos=(optativa_regular, optativa_especial),
        condicionais=(
            RegraCondicional(
                id="trilha_oferta_especial",
                descricao="Ativa requisito específico quando comprovadamente aplicável",
                condicao=condicao,
                requisitos_se_verdadeira=("optativa_especial",),
                requisitos_se_falsa=("optativa_regular",),
                fontes=(FONTE,),
            ),
        ),
        cursos_base=(
            ReferenciaCursoBase(
                curso_id="curso_base",
                matriz_id="2023",
                requisitos_reutilizados=("obrigatorias_base", "extensao_base"),
                permitir_reuso_de_componentes=True,
                fontes=(FONTE,),
            ),
        ),
        aplicabilidade=(
            RegraAplicabilidade(
                id="aplicabilidade_oferta",
                descricao="Condição declarada no ato oficial",
                condicoes=(condicao,),
                fontes=(FONTE,),
            ),
        ),
    )

    assert modelo.cursos_base[0].curso_id == "curso_base"
    assert "trilha_oferta_especial" in modelo.ids_regras


def test_rejeita_ids_duplicados_e_referencias_inexistentes():
    r1 = requisito(
        "r1",
        TipoIntegralizador.COMPONENTES_CURRICULARES,
        UnidadeRequisito.CREDITOS,
        4,
        codigos=("A",),
    )

    with pytest.raises(ValueError, match="IDs de regras curriculares"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2023",
            requisitos=(r1,),
            grupos=(
                GrupoRequisitos(
                    id="r1",
                    descricao="ID duplicado",
                    requisitos=("r1",),
                    operador=OperadorGrupo.TODOS,
                ),
            ),
        )

    with pytest.raises(ValueError, match="regras inexistentes"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2023",
            requisitos=(r1,),
            grupos=(
                GrupoRequisitos(
                    id="grupo",
                    descricao="Referência inválida",
                    requisitos=("nao_existe",),
                    operador=OperadorGrupo.TODOS,
                ),
            ),
        )


def test_rejeita_ciclo_entre_grupos():
    r1 = requisito(
        "r1",
        TipoIntegralizador.COMPONENTES_CURRICULARES,
        UnidadeRequisito.CREDITOS,
        4,
        codigos=("A",),
    )
    grupo_a = GrupoRequisitos(
        id="grupo_a",
        descricao="A",
        requisitos=("grupo_b", "r1"),
        operador=OperadorGrupo.QUALQUER,
    )
    grupo_b = GrupoRequisitos(
        id="grupo_b",
        descricao="B",
        requisitos=("grupo_a", "r1"),
        operador=OperadorGrupo.QUALQUER,
    )

    with pytest.raises(ValueError, match="Ciclo detectado"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2023",
            requisitos=(r1,),
            grupos=(grupo_a, grupo_b),
        )


def test_rejeita_compartilhamento_implicito_ou_duplicado():
    a = requisito(
        "a",
        TipoIntegralizador.EXTENSAO,
        UnidadeRequisito.HORAS,
        10,
        tags=("extensao",),
    )
    b = requisito(
        "b",
        TipoIntegralizador.ESTAGIO,
        UnidadeRequisito.HORAS,
        10,
        tags=("estagio",),
    )

    with pytest.raises(ValueError, match="positivo"):
        RegraCompartilhamento(
            requisito_a="a",
            requisito_b="b",
            unidade=UnidadeRequisito.HORAS,
            maximo_compartilhavel=0,
        )

    regra = RegraCompartilhamento(
        requisito_a="a",
        requisito_b="b",
        unidade=UnidadeRequisito.HORAS,
        maximo_compartilhavel=10,
    )
    with pytest.raises(ValueError, match="mesmo par"):
        ModeloRequisitosCurriculares(
            curso_id="curso",
            matriz_id="2023",
            requisitos=(a, b),
            compartilhamentos=(
                regra,
                RegraCompartilhamento(
                    requisito_a="b",
                    requisito_b="a",
                    unidade=UnidadeRequisito.HORAS,
                    maximo_compartilhavel=5,
                ),
            ),
        )


def test_seletor_nao_deixa_semantica_ambigua():
    with pytest.raises(ValueError, match="não pode ser combinado"):
        SeletorComponentes(
            codigos=frozenset({"A"}),
            qualquer_componente=True,
        )

    with pytest.raises(ValueError, match="ao menos um critério"):
        SeletorComponentes()
