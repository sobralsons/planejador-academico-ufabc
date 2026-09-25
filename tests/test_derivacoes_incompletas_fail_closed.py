from planejador.academico import auditoria_integralizacao
from planejador.historico import consolidar_historico
from planejador.modelos import Categoria, DisciplinaCurricular, RegistroHistorico
from planejador.relatorio import _secao_auditoria


def _registro(codigo: str) -> RegistroHistorico:
    return RegistroHistorico(
        periodo="2026.1",
        categoria_original="Sintética",
        codigo=codigo,
        nome=f"Componente {codigo}",
        creditos=4,
        carga_horaria=48,
        carga_extensao=0,
        turma="A",
        conceito="A",
        situacao="APR",
        docentes="Docente sintético",
    )


def _disciplina(codigo: str) -> DisciplinaCurricular:
    return DisciplinaCurricular(
        codigo=codigo,
        nome=f"Componente {codigo}",
        categoria=Categoria.OBRIGATORIA,
        creditos=4,
        t=4,
        p=0,
        e=0,
        i=0,
    )


def _situacao_com_derivacao_truncada(registros_extras=()):
    registros = [
        _registro(codigo)
        for indice in range(7)
        for codigo in (f"A{indice}", f"B{indice}")
    ]
    registros.extend(registros_extras)
    equivalencias = {
        **{f"A{indice}": f"X{indice}" for indice in range(7)},
        **{f"B{indice}": f"X{indice}" for indice in range(7)},
    }
    return consolidar_historico(
        registros,
        equivalencias,
        [({*(f"X{indice}" for indice in range(7))}, "Z")],
    )


def test_derivacao_truncada_fica_indeterminada_sem_virar_pendencia_confirmada():
    situacao = _situacao_com_derivacao_truncada()

    assert "Z" in situacao.concluidas
    assert "Z" in situacao.derivacoes_incompletas
    assert "Z" not in situacao.conclusoes_confiaveis()
    assert "Z" not in situacao.codigos_projetados("nenhuma")
    assert "Z" not in situacao.codigos_projetados("todas")

    auditoria = auditoria_integralizacao(
        {"creditos_obrigatorios": 4},
        {"Z": _disciplina("Z")},
        situacao,
        situacao.codigos_projetados("nenhuma"),
    )
    obrigatorias = auditoria["por_categoria"]["obrigatoria"]

    assert obrigatorias["integralizado_confirmado"] == 0
    assert obrigatorias["integralizado_estimado"] == 0
    assert obrigatorias["estado_confirmado"] == "indeterminado"
    assert obrigatorias["estado_estimado"] == "indeterminado"
    assert obrigatorias["pendente_confirmado"] is None
    assert obrigatorias["pendente_estimado"] is None
    assert obrigatorias["componentes_indeterminados"] == ["Z"]
    assert auditoria["componentes_curriculo_concluidos_confirmados"] == 0

    texto = "\n".join(_secao_auditoria(auditoria, situacao))
    assert "indeterminado" in texto.lower()
    assert "(pendentes: 4)" not in texto


def test_derivacao_incompleta_nao_impede_cumprimento_ja_comprovado():
    situacao = _situacao_com_derivacao_truncada([_registro("C")])

    auditoria = auditoria_integralizacao(
        {"creditos_obrigatorios": 4},
        {"C": _disciplina("C"), "Z": _disciplina("Z")},
        situacao,
        situacao.codigos_projetados("nenhuma"),
    )
    obrigatorias = auditoria["por_categoria"]["obrigatoria"]

    assert obrigatorias["integralizado_confirmado"] == 4
    assert obrigatorias["estado_confirmado"] == "cumprido"
    assert obrigatorias["pendente_confirmado"] == 0
    assert obrigatorias["componentes_indeterminados"] == ["Z"]


def test_derivacao_completa_continua_confiavel():
    situacao = consolidar_historico([_registro("A")], {"A": "B"})

    assert "B" in situacao.concluidas
    assert "B" not in situacao.derivacoes_incompletas
    assert "B" in situacao.conclusoes_confiaveis()
    assert "B" in situacao.codigos_projetados("nenhuma")

    auditoria = auditoria_integralizacao(
        {"creditos_obrigatorios": 4},
        {"B": _disciplina("B")},
        situacao,
        situacao.codigos_projetados("nenhuma"),
    )
    obrigatorias = auditoria["por_categoria"]["obrigatoria"]

    assert obrigatorias["integralizado_confirmado"] == 4
    assert obrigatorias["estado_confirmado"] == "cumprido"
    assert obrigatorias["pendente_confirmado"] == 0
