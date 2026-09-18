import pytest

from planejador.alocacao_evidencias import avaliar_modelo_com_evidencias
from planejador.avaliador_requisitos import EstadoAvaliacao
from planejador.evidencias_historico import (
    MetadadosCodigoEvidencia,
    converter_historico_consolidado_em_evidencias,
)
from planejador.historico import consolidar_historico
from planejador.modelos import RegistroHistorico, SituacaoAcademica
from planejador.requisitos_curriculares import (
    LimiteQuantitativo,
    ModeloRequisitosCurriculares,
    RequisitoQuantitativo,
    SeletorComponentes,
    TipoIntegralizador,
    UnidadeRequisito,
)


def _registro(
    codigo,
    *,
    situacao="APR",
    creditos=4,
    carga_horaria=48,
    carga_extensao=0,
    categoria="Categoria livre do SIGAA",
    nome="Nome que não deve classificar a evidência",
    docentes="Docente Sintético",
):
    return RegistroHistorico(
        periodo="2026.1",
        categoria_original=categoria,
        codigo=codigo,
        nome=nome,
        creditos=creditos,
        carga_horaria=carga_horaria,
        carga_extensao=carga_extensao,
        turma="A",
        conceito="A",
        situacao=situacao,
        docentes=docentes,
    )


def _modelo(codigo, unidade, minimo):
    requisito = RequisitoQuantitativo(
        id="r",
        descricao="Requisito sintético",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(codigos=frozenset({codigo})),
        limite=LimiteQuantitativo(unidade, minimo),
    )
    return ModeloRequisitosCurriculares("curso", "2026", (requisito,))


def test_conclusao_direta_vira_creditos_e_componente_sem_contar_reprovacao():
    situacao = consolidar_historico(
        [_registro("A"), _registro("B", situacao="REP")],
        {},
    )

    resultado = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset(
            {UnidadeRequisito.CREDITOS, UnidadeRequisito.COMPONENTES}
        ),
    )
    por_id = resultado.conjunto.por_id

    assert set(por_id) == {
        "historico:A:creditos",
        "historico:A:componente",
        "historico:A:horas_carga_horaria",
    }
    assert por_id["historico:A:creditos"].quantidade(UnidadeRequisito.CREDITOS) == 4
    assert por_id["historico:A:componente"].quantidade(UnidadeRequisito.COMPONENTES) == 1
    assert (
        por_id["historico:A:horas_carga_horaria"].quantidade(
            UnidadeRequisito.HORAS_CARGA_HORARIA
        )
        == 48
    )
    assert all("B" not in evidencia.codigos for evidencia in por_id.values())
    assert resultado.conjunto.unidades_completas == frozenset(
        {UnidadeRequisito.CREDITOS, UnidadeRequisito.COMPONENTES}
    )


def test_integracao_com_alocador_e_avaliador_cumpre_requisito_direto():
    situacao = consolidar_historico([_registro("A")], {})
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset({UnidadeRequisito.CREDITOS}),
    )

    resultado = avaliar_modelo_com_evidencias(
        _modelo("A", UnidadeRequisito.CREDITOS, 4),
        conversao.conjunto,
    )

    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.CUMPRIDO
    assert resultado.avaliacao.por_id["r"].valor_considerado == 4


def test_tentativas_concluidas_repetidas_nao_somam_creditos_nem_componentes():
    situacao = consolidar_historico(
        [_registro("A"), _registro("A", situacao="DISP")],
        {},
    )

    resultado = converter_historico_consolidado_em_evidencias(situacao)
    por_id = resultado.conjunto.por_id

    assert por_id["historico:A:creditos"].quantidade(UnidadeRequisito.CREDITOS) == 4
    assert por_id["historico:A:componente"].quantidade(UnidadeRequisito.COMPONENTES) == 1


def test_creditos_divergentes_na_mesma_conclusao_falham_fechado_sem_perder_componente():
    situacao = consolidar_historico(
        [_registro("A", creditos=4), _registro("A", situacao="DISP", creditos=5)],
        {},
    )

    resultado = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset(
            {UnidadeRequisito.CREDITOS, UnidadeRequisito.COMPONENTES}
        ),
    )

    assert "historico:A:creditos" not in resultado.conjunto.por_id
    assert "historico:A:componente" in resultado.conjunto.por_id
    assert len(resultado.conflitos) == 1
    assert resultado.conflitos[0].valores_encontrados == (4, 5)
    assert UnidadeRequisito.CREDITOS not in resultado.conjunto.unidades_completas
    assert UnidadeRequisito.COMPONENTES in resultado.conjunto.unidades_completas


def test_equivalencia_simples_reconhece_componente_sem_inventar_creditos_do_destino():
    situacao = consolidar_historico([_registro("A")], {"A": "B"})

    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset(
            {UnidadeRequisito.CREDITOS, UnidadeRequisito.COMPONENTES}
        ),
    )
    componente = conversao.conjunto.por_id["historico:A:componente"]
    creditos = conversao.conjunto.por_id["historico:A:creditos"]

    assert componente.codigos == frozenset({"A", "B"})
    assert creditos.codigos == frozenset({"A"})
    assert UnidadeRequisito.COMPONENTES in conversao.conjunto.unidades_completas
    assert UnidadeRequisito.CREDITOS not in conversao.conjunto.unidades_completas

    avalia_componente = avaliar_modelo_com_evidencias(
        _modelo("B", UnidadeRequisito.COMPONENTES, 1),
        conversao.conjunto,
    )
    assert avalia_componente.avaliacao is not None
    assert avalia_componente.avaliacao.estado == EstadoAvaliacao.CUMPRIDO

    avalia_creditos = avaliar_modelo_com_evidencias(
        _modelo("B", UnidadeRequisito.CREDITOS, 4),
        conversao.conjunto,
    )
    assert avalia_creditos.avaliacao is not None
    assert avalia_creditos.avaliacao.estado == EstadoAvaliacao.INDETERMINADO


def test_equivalencia_composta_permanece_indeterminada_e_nao_vira_alias_parcial():
    situacao = consolidar_historico(
        [_registro("A"), _registro("B")],
        {},
        [({"A", "B"}, "C")],
    )

    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )

    assert any(item.codigo_destino == "C" for item in conversao.pendencias)
    assert all(
        "C" not in evidencia.codigos
        for evidencia in conversao.conjunto.evidencias
    )
    assert UnidadeRequisito.COMPONENTES not in conversao.conjunto.unidades_completas

    avaliacao = avaliar_modelo_com_evidencias(
        _modelo("C", UnidadeRequisito.COMPONENTES, 1),
        conversao.conjunto,
    )
    assert avaliacao.avaliacao is not None
    assert avaliacao.avaliacao.estado == EstadoAvaliacao.INDETERMINADO


def test_categoria_nome_e_docente_do_historico_nao_viram_regra_por_heuristica():
    situacao = consolidar_historico(
        [
            _registro(
                "A",
                categoria="OBRIGATÓRIA",
                nome="Estágio Supervisionado de Extensão",
                docentes="Pessoa Identificável de Teste",
            )
        ],
        {},
    )

    sem_meta = converter_historico_consolidado_em_evidencias(situacao)
    assert all(not item.categorias for item in sem_meta.conjunto.evidencias)
    assert all(not item.tipos for item in sem_meta.conjunto.evidencias)
    assert all(not item.tags for item in sem_meta.conjunto.evidencias)
    assert "Pessoa Identificável de Teste" not in repr(sem_meta.conjunto.evidencias)
    assert "Estágio Supervisionado de Extensão" not in repr(
        sem_meta.conjunto.evidencias
    )

    com_meta = converter_historico_consolidado_em_evidencias(
        situacao,
        metadados_por_codigo={
            "A": MetadadosCodigoEvidencia(
                categorias=frozenset({"obrigatoria"}),
                tags=frozenset({"validado_para_teste"}),
                origens=frozenset({"ppc_sintetico"}),
            )
        },
    )
    assert all("obrigatoria" in item.categorias for item in com_meta.conjunto.evidencias)
    assert all("validado_para_teste" in item.tags for item in com_meta.conjunto.evidencias)
    assert all("ppc_sintetico" in item.origens for item in com_meta.conjunto.evidencias)


def test_origem_consolidada_sem_registro_concluido_bloqueia_completude():
    situacao = SituacaoAcademica(
        concluidas={"A"},
        tentativas={},
        origens_conclusao={"A": {"A"}},
    )

    resultado = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset(
            {UnidadeRequisito.CREDITOS, UnidadeRequisito.COMPONENTES}
        ),
    )

    assert not resultado.conjunto.evidencias
    assert resultado.pendencias
    assert not resultado.conjunto.unidades_completas


def test_horas_genericas_nao_recebem_dados_do_historico_por_atalho():
    situacao = consolidar_historico(
        [_registro("A", carga_horaria=48, carga_extensao=12)],
        {},
    )

    with pytest.raises(ValueError, match="unidades específicas"):
        converter_historico_consolidado_em_evidencias(
            situacao,
            unidades_completas=frozenset({UnidadeRequisito.HORAS}),
        )


def test_carga_horaria_e_extensao_sao_evidencias_distintas_e_nao_se_somam():
    situacao = consolidar_historico(
        [_registro("A", carga_horaria=48, carga_extensao=12)],
        {},
    )
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset(
            {
                UnidadeRequisito.HORAS_CARGA_HORARIA,
                UnidadeRequisito.HORAS_EXTENSAO,
            }
        ),
    )
    por_id = conversao.conjunto.por_id

    assert por_id["historico:A:horas_carga_horaria"].quantidade(
        UnidadeRequisito.HORAS_CARGA_HORARIA
    ) == 48
    assert por_id["historico:A:horas_extensao"].quantidade(
        UnidadeRequisito.HORAS_EXTENSAO
    ) == 12

    total = avaliar_modelo_com_evidencias(
        _modelo("A", UnidadeRequisito.HORAS_CARGA_HORARIA, 48),
        conversao.conjunto,
    )
    extensao = avaliar_modelo_com_evidencias(
        _modelo("A", UnidadeRequisito.HORAS_EXTENSAO, 12),
        conversao.conjunto,
    )
    generico = avaliar_modelo_com_evidencias(
        _modelo("A", UnidadeRequisito.HORAS, 1),
        conversao.conjunto,
    )

    assert total.avaliacao is not None
    assert total.avaliacao.por_id["r"].valor_considerado == 48
    assert total.avaliacao.estado == EstadoAvaliacao.CUMPRIDO
    assert extensao.avaliacao is not None
    assert extensao.avaliacao.por_id["r"].valor_considerado == 12
    assert extensao.avaliacao.estado == EstadoAvaliacao.CUMPRIDO
    assert generico.avaliacao is not None
    assert generico.avaliacao.por_id["r"].valor_considerado == 0
    assert generico.avaliacao.estado == EstadoAvaliacao.INDETERMINADO


def test_divergencia_na_carga_horaria_nao_invalida_extensao_consistente():
    situacao = consolidar_historico(
        [
            _registro("A", carga_horaria=48, carga_extensao=12),
            _registro("A", situacao="DISP", carga_horaria=60, carga_extensao=12),
        ],
        {},
    )
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset(
            {
                UnidadeRequisito.HORAS_CARGA_HORARIA,
                UnidadeRequisito.HORAS_EXTENSAO,
            }
        ),
    )

    assert "historico:A:horas_carga_horaria" not in conversao.conjunto.por_id
    assert conversao.conjunto.por_id["historico:A:horas_extensao"].quantidade(
        UnidadeRequisito.HORAS_EXTENSAO
    ) == 12
    assert UnidadeRequisito.HORAS_CARGA_HORARIA not in (
        conversao.conjunto.unidades_completas
    )
    assert UnidadeRequisito.HORAS_EXTENSAO in conversao.conjunto.unidades_completas
    assert any(
        conflito.unidade == UnidadeRequisito.HORAS_CARGA_HORARIA
        for conflito in conversao.conflitos
    )


def test_equivalencia_simples_nao_transfere_quantidades_de_horas_ao_destino():
    situacao = consolidar_historico(
        [_registro("A", carga_horaria=48, carga_extensao=12)],
        {"A": "B"},
    )
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset(
            {
                UnidadeRequisito.HORAS_CARGA_HORARIA,
                UnidadeRequisito.HORAS_EXTENSAO,
            }
        ),
    )

    assert conversao.conjunto.por_id["historico:A:horas_carga_horaria"].codigos == frozenset(
        {"A"}
    )
    assert conversao.conjunto.por_id["historico:A:horas_extensao"].codigos == frozenset(
        {"A"}
    )
    assert UnidadeRequisito.HORAS_CARGA_HORARIA not in (
        conversao.conjunto.unidades_completas
    )
    assert UnidadeRequisito.HORAS_EXTENSAO not in conversao.conjunto.unidades_completas

    resultado = avaliar_modelo_com_evidencias(
        _modelo("B", UnidadeRequisito.HORAS_CARGA_HORARIA, 48),
        conversao.conjunto,
    )
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.INDETERMINADO

def test_equivalencia_simples_nao_duplica_componente_em_dois_requisitos_independentes():
    situacao = consolidar_historico([_registro("A")], {"A": "B"})
    conversao = converter_historico_consolidado_em_evidencias(
        situacao,
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )

    req_a = RequisitoQuantitativo(
        id="a",
        descricao="A",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(codigos=frozenset({"A"})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    req_b = RequisitoQuantitativo(
        id="b",
        descricao="B",
        integralizador=TipoIntegralizador.COMPONENTES_CURRICULARES,
        seletor=SeletorComponentes(codigos=frozenset({"B"})),
        limite=LimiteQuantitativo(UnidadeRequisito.COMPONENTES, 1),
    )
    modelo = ModeloRequisitosCurriculares("curso", "2026", (req_a, req_b))

    resultado = avaliar_modelo_com_evidencias(modelo, conversao.conjunto)

    assert resultado.alocacao.pendencias
    assert not resultado.alocacao.alocacoes
    assert resultado.avaliacao is not None
    assert resultado.avaliacao.estado == EstadoAvaliacao.INDETERMINADO

