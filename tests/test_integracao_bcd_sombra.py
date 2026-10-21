from planejador.academico import auditoria_integralizacao
from planejador.curriculo import carregar_curriculo
from planejador.historico import consolidar_historico
from planejador.integracao_motor_curricular import avaliar_bcd_2023_em_modo_sombra
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


def test_bcd_2023_executa_segunda_familia_no_mesmo_contrato_fail_closed():
    metadados, curriculo_completo = carregar_curriculo(
        "dados/curriculos/bcd_2023.json"
    )
    tcc = curriculo_completo["MCBD008-23"]
    obrigatoria_regular = next(
        item
        for item in curriculo_completo.values()
        if item.categoria == Categoria.OBRIGATORIA and item.codigo != tcc.codigo
    )
    curriculo = {tcc.codigo: tcc, obrigatoria_regular.codigo: obrigatoria_regular}
    metadados = {
        **metadados,
        "creditos_obrigatorios": obrigatoria_regular.creditos,
        "creditos_opcao_limitada": 0,
        "creditos_livres": 0,
        "atividades_complementares_horas": 0,
        "trabalho_final_creditos": tcc.creditos,
    }
    situacao = consolidar_historico(
        [
            _registro(tcc.codigo, tcc.creditos),
            _registro(obrigatoria_regular.codigo, obrigatoria_regular.creditos),
        ],
        {},
        resumo=ResumoHistorico(),
    )
    legado = auditoria_integralizacao(
        metadados, curriculo, situacao, set(situacao.concluidas)
    )

    sombra = avaliar_bcd_2023_em_modo_sombra(
        metadados,
        curriculo,
        situacao,
        resultado_legado=legado,
        pacote_piloto_confirmado=True,
        aplicabilidade_confirmada=True,
        classificacoes_validadas=True,
    )

    assert sombra.curriculo_id == "bcd_2023"
    assert sombra.autoridade == "legado"
    assert sombra.publicavel is False
    assert sombra.proveniencia_regras_suficiente is False
    assert sombra.corte_autoridade.curriculo_id == "bcd_2023"
    assert sombra.corte_autoridade.autoridade.value == sombra.autoridade == "legado"
    assert "fontes_versionadas" in sombra.corte_autoridade.bloqueios
    assert "revisao_humana_registrada" in sombra.corte_autoridade.bloqueios
    assert sombra.requisitos["creditos_obrigatorios"].estado.value == "cumprido"
    assert sombra.requisitos["extensao"].estado.value == "indeterminado"
    assert sombra.requisitos["trabalho_final"].estado.value == "indeterminado"
    assert sombra.divergencias["extensao"].classificacao == "nao_comparavel"
    assert sombra.divergencias["extensao"].decisao == "nao_promover"


def test_bcd_2023_exige_confirmacao_explicita_do_pacote():
    metadados, curriculo = carregar_curriculo("dados/curriculos/bcd_2023.json")
    situacao = consolidar_historico([], {})

    try:
        avaliar_bcd_2023_em_modo_sombra(metadados, curriculo, situacao)
    except ValueError as erro:
        assert "confirmação explícita" in str(erro)
    else:
        raise AssertionError("O BCD 2023 não pode executar sem confirmação do piloto.")
