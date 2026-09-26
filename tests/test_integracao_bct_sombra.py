from planejador.academico import auditoria_integralizacao
from planejador.curriculo import carregar_curriculo
from planejador.historico import consolidar_historico
from planejador.integracao_motor_curricular import avaliar_bct_2015_em_modo_sombra
from planejador.modelos import Categoria, RegistroHistorico, ResumoHistorico


def _registro(codigo: str, creditos: int) -> RegistroHistorico:
    return RegistroHistorico(
        periodo="2026.1",
        categoria_original="Sintética",
        codigo=codigo,
        nome=f"Disciplina {codigo}",
        creditos=creditos,
        carga_horaria=creditos * 12,
        carga_extensao=0,
        turma="A",
        conceito="A",
        situacao="APR",
        docentes="Docente Sintético",
    )


def _cenario_bct():
    metadados, curriculo = carregar_curriculo("dados/curriculos/bct_2015.json")
    obrigatorias = [
        disciplina
        for disciplina in curriculo.values()
        if disciplina.categoria == Categoria.OBRIGATORIA
    ]
    situacao = consolidar_historico(
        [_registro(item.codigo, item.creditos) for item in obrigatorias],
        {},
        resumo=ResumoHistorico(atividades_complementares_horas=120),
    )
    return metadados, curriculo, situacao


def test_bct_2015_executa_comparacao_controlada_sem_expor_no_legado():
    metadados, curriculo, situacao = _cenario_bct()

    auditoria = auditoria_integralizacao(
        metadados,
        curriculo,
        situacao,
        set(situacao.concluidas),
    )

    assert auditoria["por_categoria"]["obrigatoria"]["estado_confirmado"] == "cumprido"
    assert "motor_generico_sombra" not in auditoria

    sombra = avaliar_bct_2015_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        resultado_legado=auditoria,
        pacote_piloto_confirmado=True,
        aplicabilidade_confirmada=True,
        classificacoes_validadas=True,
    )

    assert sombra.modo == "sombra_controlada"
    assert sombra.autoridade == "legado"
    assert sombra.curriculo_id == "bct_2015"
    assert sombra.proveniencia_regras_suficiente is False
    assert sombra.publicavel is False
    assert sombra.requisitos["creditos_obrigatorios"].estado.value == "cumprido"
    assert sombra.requisitos["atividades_complementares"].estado.value == "cumprido"
    assert sombra.requisitos["creditos_opcao_limitada"].estado.value == "indeterminado"
    assert sombra.requisitos["creditos_livres"].estado.value == "indeterminado"
    assert sombra.conjunto.evidencias
    assert sombra.resultado.alocacao.alocacoes
    assert sombra.divergencias["creditos_obrigatorios"].classificacao == "concordante"
    assert all(unidade.value != "horas" for unidade in sombra.conjunto.unidades_completas)


def test_aplicabilidade_nao_confirmada_bloqueia_conclusoes_do_piloto():
    metadados, curriculo, situacao = _cenario_bct()

    sombra = avaliar_bct_2015_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        pacote_piloto_confirmado=True,
        classificacoes_validadas=True,
    )

    assert sombra.aplicabilidade == "indeterminada"
    assert sombra.estado == "indeterminado"
    assert sombra.requisitos == {}


def test_classificacoes_nao_validadas_nao_produzem_creditos_por_categoria():
    metadados, curriculo, situacao = _cenario_bct()

    sombra = avaliar_bct_2015_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        pacote_piloto_confirmado=True,
        aplicabilidade_confirmada=True,
    )

    assert sombra.requisitos["creditos_obrigatorios"].estado.value == "indeterminado"
    assert sombra.resultado.alocacao.alocacoes
    assert all(
        item.requisito_ids == ("atividades_complementares",)
        for item in sombra.resultado.alocacao.alocacoes
    )


def test_motor_generico_sombra_rejeita_outro_curriculo():
    metadados, curriculo = carregar_curriculo("dados/curriculos/bcd_2023.json")
    situacao = consolidar_historico([], {})

    assert avaliar_bct_2015_em_modo_sombra(metadados, curriculo, situacao) is None


def test_equivalencia_nao_transfere_creditos_e_registra_motivo_da_divergencia():
    metadados, curriculo = carregar_curriculo("dados/curriculos/bct_2015.json")
    destino = next(
        item for item in curriculo.values() if item.categoria == Categoria.OBRIGATORIA
    )
    metadados = {
        **metadados,
        "creditos_obrigatorios": destino.creditos,
        "creditos_opcao_limitada": 0,
        "creditos_livres": 0,
        "atividades_complementares_horas": 0,
    }
    curriculo = {destino.codigo: destino}
    situacao = consolidar_historico(
        [_registro("ANTIGO-SINTETICO", destino.creditos)],
        {"ANTIGO-SINTETICO": destino.codigo},
    )
    legado = auditoria_integralizacao(
        metadados, curriculo, situacao, set(situacao.concluidas)
    )

    sombra = avaliar_bct_2015_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        resultado_legado=legado,
        pacote_piloto_confirmado=True,
        aplicabilidade_confirmada=True,
        classificacoes_validadas=True,
    )

    assert legado["por_categoria"]["obrigatoria"]["estado_confirmado"] == "cumprido"
    assert sombra.requisitos["creditos_obrigatorios"].estado.value == "indeterminado"
    divergencia = sombra.divergencias["creditos_obrigatorios"]
    assert divergencia.classificacao == "divergente_requer_revisao"
    assert "conversão" in divergencia.motivo.lower()


def test_comparacao_detecta_dupla_contagem_mesmo_com_estados_iguais():
    metadados, curriculo_completo = carregar_curriculo(
        "dados/curriculos/bct_2015.json"
    )
    origem, destino = [
        item
        for item in curriculo_completo.values()
        if item.categoria == Categoria.OBRIGATORIA
    ][:2]
    metadados = {
        **metadados,
        "creditos_obrigatorios": origem.creditos,
        "creditos_opcao_limitada": 0,
        "creditos_livres": 0,
        "atividades_complementares_horas": 0,
    }
    curriculo = {origem.codigo: origem, destino.codigo: destino}
    situacao = consolidar_historico(
        [_registro(origem.codigo, origem.creditos)],
        {origem.codigo: destino.codigo},
    )
    legado = auditoria_integralizacao(
        metadados, curriculo, situacao, set(situacao.concluidas)
    )

    sombra = avaliar_bct_2015_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        resultado_legado=legado,
        pacote_piloto_confirmado=True,
        aplicabilidade_confirmada=True,
        classificacoes_validadas=True,
    )

    divergencia = sombra.divergencias["creditos_obrigatorios"]
    assert divergencia.legado == divergencia.generico == "cumprido"
    assert divergencia.valor_legado == origem.creditos + destino.creditos
    assert divergencia.valor_generico == origem.creditos
    assert divergencia.classificacao == "divergente_requer_revisao"
