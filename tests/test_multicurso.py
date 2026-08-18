import json
from pathlib import Path

from planejador.historico import consolidar_historico
from planejador.modelos import (
    Categoria, DisciplinaCurricular, Grade, Horario, Oferta, Recorrencia,
    RegistroHistorico, ResumoHistorico, TipoComponente,
)
from planejador.multicurso import (
    analisar_curriculo,
    carregar_registro_curriculos,
    gerar_relatorio_multicurso_html,
    mapear_grade_detalhada_para_curriculo,
    resolver_curriculo,
)

BASE = Path(__file__).resolve().parents[1]


def test_registro_possui_sete_curriculos():
    registro = carregar_registro_curriculos(BASE)
    assert set(registro) == {
        "materiais_2017", "bct_2015", "bcc_2017", "bcc_2023",
        "bcd_2023", "ei_2017", "ei_2023",
    }


def test_totais_obrigatorios_dos_pacotes_batem_com_metadados():
    registro = carregar_registro_curriculos(BASE)
    for id_ in ("bct_2015", "bcc_2017", "bcc_2023", "bcd_2023", "ei_2017", "ei_2023"):
        metadados, curriculo, _, _ = resolver_curriculo(BASE, registro[id_])
        total = sum(d.creditos for d in curriculo.values() if d.categoria == Categoria.OBRIGATORIA)
        assert total == metadados["creditos_obrigatorios"], (id_, total, metadados["creditos_obrigatorios"])
        assert all(d.creditos > 0 for d in curriculo.values()), id_


def test_componentes_especiais_sao_reconhecidos_em_todos_os_cursos():
    tcc = DisciplinaCurricular("MCBD008-23", "Trabalho de Conclusão de Curso em Ciência de Dados", Categoria.OBRIGATORIA, 12, 0, 12, 0, 24)
    projeto = DisciplinaCurricular("MCTA029-17", "Projeto de Graduação em Computação I", Categoria.OBRIGATORIA, 8, 0, 8, 0, 8)
    unificada = DisciplinaCurricular("ESMA001-23", "Soluções para Desafios em Engenharia", Categoria.OBRIGATORIA, 2, 0, 2, 0, 4)
    assert tcc.tipo_componente == TipoComponente.TRABALHO_GRADUACAO
    assert projeto.tipo_componente == TipoComponente.TRABALHO_GRADUACAO
    assert unificada.tipo_componente == TipoComponente.ENGENHARIA_UNIFICADA


def test_equivalencia_bcc_2017_para_2023_integraliza_disciplina():
    registro = carregar_registro_curriculos(BASE)
    _, curriculo, equivalencias, compostas = resolver_curriculo(BASE, registro["bcc_2023"])
    r = RegistroHistorico("2025.1", "OL", "MCTA001-17", "Algoritmos e Estruturas de Dados I", 4, 48, 0, "T", "B", "APR", "")
    situacao = consolidar_historico([r], equivalencias, compostas, {}, ResumoHistorico())
    assert "MCCC001-23" in situacao.concluidas
    assert "MCCC001-23" in curriculo


def test_estagio_opcional_do_bcc_2017_nao_vira_pendencia_obrigatoria():
    registro = carregar_registro_curriculos(BASE)
    analise = analisar_curriculo(
        base=BASE, registro=registro["bcc_2017"], registros_historico=[],
        convalidacoes_historico={}, resumo_historico=ResumoHistorico(periodo_inicial="2023.3"),
        modo_projecao="nenhuma", codigos_personalizados=[], estagio_status="nao_iniciado",
        grade=None, curriculo_origem=None, periodo_planejamento="2026.3", ritmo=16, margem=1,
        quadrimestre_planejado=10,
    )
    assert analise["estimativa_formatura"]["estagio_creditos_pendentes"] == 0
    assert analise["estimativa_formatura"]["tg_creditos_pendentes"] == 24


def test_estagio_em_andamento_da_engenharia_e_retirado_da_projecao():
    registro = carregar_registro_curriculos(BASE)
    analise = analisar_curriculo(
        base=BASE, registro=registro["ei_2023"], registros_historico=[],
        convalidacoes_historico={}, resumo_historico=ResumoHistorico(periodo_inicial="2023.3"),
        modo_projecao="nenhuma", codigos_personalizados=[], estagio_status="em_andamento",
        grade=None, curriculo_origem=None, periodo_planejamento="2026.3", ritmo=16, margem=1,
        quadrimestre_planejado=10,
    )
    assert analise["estimativa_formatura"]["estagio_creditos_pendentes"] == 0


def test_relatorio_multicurso_exibe_previsoes(tmp_path):
    dados = [{
        "rotulo": "Curso Teste", "grupo": "Teste",
        "estimativa_formatura": {
            "periodo_estimado_minimo": "2028.1", "periodo_estimado_prudente": "2028.2",
            "quadrimestres_estimados_incluindo_atual": 5, "quadrimestres_estimados_prudente": 6,
            "percentual_conclusao": 70.0, "gargalos": ["gargalo teste"], "observacao": "estimativa",
        },
        "auditoria": {"por_categoria": {
            "obrigatoria": {"integralizado_estimado": 70, "exigido": 100},
            "opcao_limitada": {"integralizado_estimado": 10, "exigido": 20},
            "livre": {"integralizado_estimado": 10, "exigido": 10},
        }},
    }]
    destino = tmp_path / "multi.html"
    gerar_relatorio_multicurso_html(destino, dados, "2026.3")
    texto = destino.read_text(encoding="utf-8")
    assert "Curso Teste" in texto
    assert "2028.1" in texto
    assert "70.0%" in texto


def test_bcd_usa_codigo_do_rol_oficial_do_tcc_e_aceita_alias_alternativo():
    registro = carregar_registro_curriculos(BASE)
    metadados, curriculo, equivalencias, _ = resolver_curriculo(BASE, registro["bcd_2023"])
    assert "MCBD008-23" in curriculo
    assert curriculo["MCBD008-23"].creditos == 12
    assert curriculo["MCBD008-23"].tipo_componente == TipoComponente.TRABALHO_GRADUACAO
    assert equivalencias["MCZB008-23"] == "MCBD008-23"
    assert metadados["trabalho_final_creditos"] == 12


def test_bcc_2023_usa_programacao_estruturada_do_ppc():
    registro = carregar_registro_curriculos(BASE)
    _, curriculo, _, _ = resolver_curriculo(BASE, registro["bcc_2023"])
    assert "MCTA028-15" in curriculo
    assert "MCCC014-23" not in curriculo


def test_bcc_2023_tcc_considera_inicio_no_q13_e_nao_soma_espera_duas_vezes():
    registro = carregar_registro_curriculos(BASE)
    analise = analisar_curriculo(
        base=BASE, registro=registro["bcc_2023"], registros_historico=[],
        convalidacoes_historico={}, resumo_historico=ResumoHistorico(periodo_inicial="2023.3"),
        modo_projecao="nenhuma", codigos_personalizados=[], estagio_status="nao_iniciado",
        grade=None, curriculo_origem=None, periodo_planejamento="2026.3", ritmo=16, margem=1,
        quadrimestre_planejado=10,
    )
    # Do Q10: espera Q11/Q12 e desenvolve o TCC em Q13/Q14/Q15.
    assert analise["estimativa_formatura"]["quadrimestres_tg"] == 5


def test_ei_2023_distingue_creditos_de_planejamento_do_total_oficial():
    registro = carregar_registro_curriculos(BASE)
    metadados, _, _, _ = resolver_curriculo(BASE, registro["ei_2023"])
    assert metadados["creditos_disciplinas_e_integralizadores"] == 275
    assert metadados["creditos_totais_oficiais"] == 310
    assert metadados["creditos_obrigatorios_regulares"] == 219
    assert metadados["extensao_creditos"] == 31
    assert metadados["atividades_complementares_creditos"] == 4


def test_estimativa_mostra_atividades_complementares_e_extensao_separadamente():
    registro = carregar_registro_curriculos(BASE)
    analise_bct = analisar_curriculo(
        base=BASE, registro=registro["bct_2015"], registros_historico=[],
        convalidacoes_historico={}, resumo_historico=ResumoHistorico(periodo_inicial="2023.3", atividades_complementares_horas=100),
        modo_projecao="nenhuma", codigos_personalizados=[], estagio_status="nao_iniciado",
        grade=None, curriculo_origem=None, periodo_planejamento="2026.3", ritmo=16, margem=1,
        quadrimestre_planejado=10,
    )
    est_bct = analise_bct["estimativa_formatura"]
    assert est_bct["atividades_complementares_pendentes_horas"] == 20

    analise_bcd = analisar_curriculo(
        base=BASE, registro=registro["bcd_2023"], registros_historico=[],
        convalidacoes_historico={}, resumo_historico=ResumoHistorico(periodo_inicial="2023.3"),
        modo_projecao="nenhuma", codigos_personalizados=[], estagio_status="nao_iniciado",
        grade=None, curriculo_origem=None, periodo_planejamento="2026.3", ritmo=16, margem=1,
        quadrimestre_planejado=10,
    )
    est_bcd = analise_bcd["estimativa_formatura"]
    assert est_bcd["extensao_exigida_horas"] == 294
    assert est_bcd["extensao_pendente_maxima_horas"] >= 0


def test_todos_os_curriculos_geram_auditoria_e_previsao_sem_historico():
    registro = carregar_registro_curriculos(BASE)
    for id_, item in registro.items():
        analise = analisar_curriculo(
            base=BASE, registro=item, registros_historico=[],
            convalidacoes_historico={}, resumo_historico=ResumoHistorico(periodo_inicial="2023.3"),
            modo_projecao="nenhuma", codigos_personalizados=[], estagio_status="nao_iniciado",
            grade=None, curriculo_origem=None, periodo_planejamento="2026.3", ritmo=16, margem=1,
            quadrimestre_planejado=10,
        )
        assert analise["auditoria"]["por_categoria"]
        assert analise["estimativa_formatura"]["periodo_estimado_minimo"]
        assert analise["estimativa_formatura"]["quadrimestres_estimados_incluindo_atual"] >= 1


def test_melhor_sobreposicao_prioriza_creditos_e_depois_progresso():
    from planejador.multicurso import selecionar_melhor_sobreposicao

    dados = {
        "A|B": [
            {"creditos_grade_aproveitados": 8, "estimativa_formatura": {"percentual_conclusao": 50}},
            {"creditos_grade_aproveitados": 4, "estimativa_formatura": {"percentual_conclusao": 40}},
        ],
        "C|D": [
            {"creditos_grade_aproveitados": 4, "estimativa_formatura": {"percentual_conclusao": 90}},
            {"creditos_grade_aproveitados": 4, "estimativa_formatura": {"percentual_conclusao": 90}},
        ],
    }
    melhor = selecionar_melhor_sobreposicao(dados)
    assert melhor is not None
    assert melhor["assinatura"] == ["A", "B"]
    assert melhor["creditos_aproveitados_somados"] == 12
    assert melhor["cursos_impactados"] == 2


def test_interface_expoe_comparacao_de_formatura_e_sem_widget_duplicado():
    texto = (BASE / "app.py").read_text(encoding="utf-8")
    assert "Em quanto tempo posso me formar?" in texto
    assert "Grade com maior aproveitamento conjunto" in texto
    assert "Total oficial informado no PPC" in texto
    assert "Máximo de disciplinas candidatas" in texto
    assert "Certificado da busca e exatidão do ranking" in texto
    assert texto.count("Incluir opções limitadas na busca") == 1


def test_equivalencia_na_grade_nao_e_contada_novamente_como_credito_livre():
    curriculo_destino = {
        "NOVO-23": DisciplinaCurricular(
            "NOVO-23", "Disciplina Equivalente", Categoria.OBRIGATORIA,
            4, 4, 0, 0, 4, 5,
        )
    }
    curriculo_origem = {
        "ANTIGO-17": DisciplinaCurricular(
            "ANTIGO-17", "Disciplina Equivalente", Categoria.OBRIGATORIA,
            4, 4, 0, 0, 4, 5,
        )
    }
    oferta = Oferta(
        "ANTIGO-17", "ANTIGO-17", "Disciplina Equivalente A1", "T1",
        "SA", "NOTURNO", 4, 4, 0, 0, 4,
        (Horario(0, 19 * 60, 21 * 60, Recorrencia.SEMANAL, "teoria"),),
        (), "4-0-0-4",
    )
    grade = Grade((oferta,), None, {}, {})
    mapeadas, creditos_nao_mapeados = mapear_grade_detalhada_para_curriculo(
        grade,
        curriculo_destino,
        {"ANTIGO-17": "NOVO-23"},
        curriculo_origem,
    )
    assert mapeadas == {"NOVO-23"}
    assert creditos_nao_mapeados == 0


def test_status_de_estagio_por_curriculo_tem_prioridade_sobre_campo_legado():
    from types import SimpleNamespace
    from main import _status_estagio_principal

    config = SimpleNamespace(
        curriculo_principal_id="materiais_2017",
        estagio_status="nao_iniciado",
        estagios_status={"materiais_2017": "em_andamento"},
    )
    assert _status_estagio_principal(config) == "em_andamento"


def test_curso_especifico_nao_pode_terminar_antes_do_curso_base():
    from planejador.multicurso import _ajustar_previsao_pelo_curso_base

    especifico = {
        "id": "curso",
        "rotulo": "Curso Específico",
        "estimativa_formatura": {
            "quadrimestres_estimados_incluindo_atual": 3,
            "quadrimestres_estimados_prudente": 4,
            "gargalos": [],
        },
    }
    base = {
        "id": "bct_2015",
        "rotulo": "BC&T 2015",
        "estimativa_formatura": {
            "quadrimestres_estimados_incluindo_atual": 5,
            "quadrimestres_estimados_prudente": 6,
        },
    }
    ajustada = _ajustar_previsao_pelo_curso_base(especifico, base, "2026.3")
    est = ajustada["estimativa_formatura"]
    assert est["quadrimestres_estimados_incluindo_atual"] == 5
    assert est["quadrimestres_estimados_prudente"] == 6
    assert est["periodo_estimado_minimo"] == "2028.1"
    assert est["curso_base_id"] == "bct_2015"


def test_impacto_multicurso_conta_apenas_creditos_novos_da_grade():
    from planejador.multicurso import creditos_novos_da_grade

    curriculo = {
        "A": DisciplinaCurricular("A", "A", Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, 1),
        "B": DisciplinaCurricular("B", "B", Categoria.OPCAO_LIMITADA, 2, 2, 0, 0, 2, 2),
    }
    assert creditos_novos_da_grade({"A", "B"}, {"A"}, curriculo) == 2
