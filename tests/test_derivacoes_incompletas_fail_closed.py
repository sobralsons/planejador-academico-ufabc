from planejador.academico import auditoria_integralizacao
from planejador.historico import consolidar_historico
from planejador.modelos import Categoria, DisciplinaCurricular, RegistroHistorico


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


def _situacao_com_derivacao_truncada():
    registros = [
        _registro(codigo)
        for indice in range(7)
        for codigo in (f"A{indice}", f"B{indice}")
    ]
    equivalencias = {
        **{f"A{indice}": f"X{indice}" for indice in range(7)},
        **{f"B{indice}": f"X{indice}" for indice in range(7)},
    }
    return consolidar_historico(
        registros,
        equivalencias,
        [({*(f"X{indice}" for indice in range(7))}, "Z")],
    )


def test_derivacao_truncada_nao_sustenta_planejamento_ou_integralizacao():
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
    assert obrigatorias["pendente_confirmado"] == 4
    assert obrigatorias["pendente_estimado"] == 4
    assert auditoria["componentes_curriculo_concluidos_confirmados"] == 0


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
    assert obrigatorias["pendente_confirmado"] == 0
