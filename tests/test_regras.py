import json
import tempfile
import unittest
from pathlib import Path

from planejador.academico import estimar_quadrimestre_planejado
from planejador.analise import analisar_desempenho_historico, estimar_formatura_por_grade
from planejador.configuracao import PreferenciasConfig, carregar_configuracao
from planejador.modelos import (
    Categoria,
    DiagnosticoDisciplina,
    DisciplinaCurricular,
    Horario,
    Oferta,
    Recorrencia,
    SituacaoAcademica,
    RegistroHistorico,
)
from planejador.ofertas import extrair_horarios, extrair_tpei, horarios_conflitam
from planejador.planejador import (
    ConfiguracaoBusca,
    calcular_logistica,
    diagnosticar_adicoes_grade,
    gerar_planejamento,
    montar_grade_personalizada,
    sugerir_adicoes_grade,
)


class TesteTpei(unittest.TestCase):
    def test_tpi(self):
        self.assertEqual(extrair_tpei("4-2-4")[-1], 6)

    def test_tpei_com_extensao(self):
        self.assertEqual(extrair_tpei("0-14-0-0")[-1], 14)


class TesteHorarios(unittest.TestCase):
    def test_aulas_encostadas_nao_conflitam(self):
        a = Horario(0, 19 * 60, 21 * 60, Recorrencia.SEMANAL, "teoria")
        b = Horario(0, 21 * 60, 23 * 60, Recorrencia.SEMANAL, "teoria")
        self.assertFalse(horarios_conflitam(a, b))

    def test_sobreposicao_conflita(self):
        a = Horario(0, 19 * 60, 21 * 60, Recorrencia.SEMANAL, "teoria")
        b = Horario(0, 20 * 60, 22 * 60, Recorrencia.SEMANAL, "teoria")
        self.assertTrue(horarios_conflitam(a, b))

    def test_quinzenas_diferentes_nao_conflitam(self):
        a = Horario(0, 19 * 60, 21 * 60, Recorrencia.QUINZENAL_I, "teoria")
        b = Horario(0, 19 * 60, 21 * 60, Recorrencia.QUINZENAL_II, "pratica")
        self.assertFalse(horarios_conflitam(a, b))


    def test_diferencia_janela_de_bloco_livre_na_extremidade(self):
        oferta_a = Oferta(
            codigo_ofertado="A", codigo_curriculo="A", nome_turma="A", codigo_turma="TA",
            campus="SA", turno="NOTURNO", creditos=4, t=4, p=0, e=0, i=4,
            horarios=(Horario(0, 21 * 60, 23 * 60, Recorrencia.SEMANAL, "teoria"),),
            docentes=(), tpei_original="4-0-4",
        )
        janelas, permanencia, em_aula, bordas, dias_parciais = calcular_logistica(
            (oferta_a,), 19 * 60, 23 * 60
        )
        self.assertEqual(janelas, 0)
        self.assertEqual(permanencia, 120)
        self.assertEqual(em_aula, 120)
        self.assertEqual(bordas, 120)
        self.assertEqual(dias_parciais, 1)

    def test_janela_entre_duas_aulas(self):
        oferta_a = Oferta(
            codigo_ofertado="A", codigo_curriculo="A", nome_turma="A", codigo_turma="TA",
            campus="SA", turno="NOTURNO", creditos=2, t=2, p=0, e=0, i=2,
            horarios=(Horario(0, 19 * 60, 20 * 60, Recorrencia.SEMANAL, "teoria"),),
            docentes=(), tpei_original="2-0-2",
        )
        oferta_b = Oferta(
            codigo_ofertado="B", codigo_curriculo="B", nome_turma="B", codigo_turma="TB",
            campus="SA", turno="NOTURNO", creditos=2, t=2, p=0, e=0, i=2,
            horarios=(Horario(0, 21 * 60, 22 * 60, Recorrencia.SEMANAL, "teoria"),),
            docentes=(), tpei_original="2-0-2",
        )
        janelas, permanencia, em_aula, bordas, _ = calcular_logistica(
            (oferta_a, oferta_b), 19 * 60, 23 * 60
        )
        self.assertEqual(janelas, 60)
        self.assertEqual(permanencia, 180)
        self.assertEqual(em_aula, 120)
        self.assertEqual(bordas, 60)

    def test_parser_real_da_planilha(self):
        horarios = extrair_horarios(
            "terça das 19:00 às 21:00, quinzenal I; "
            "quinta das 21:00 às 23:00, semanal",
            "teoria",
        )
        self.assertEqual(len(horarios), 2)
        self.assertEqual(horarios[0].inicio, 19 * 60)
        self.assertEqual(horarios[0].recorrencia, Recorrencia.QUINZENAL_I)


class TesteCenarios(unittest.TestCase):
    def test_projecao_personalizada(self):
        s = SituacaoAcademica(
            concluidas={"A"},
            em_andamento={"B", "C"},
        )
        self.assertEqual(s.codigos_projetados("nenhuma"), {"A"})
        self.assertEqual(s.codigos_projetados("todas"), {"A", "B", "C"})
        self.assertEqual(s.codigos_projetados("personalizada", ["C"]), {"A", "C"})

    def test_quadrimestre_estimado(self):
        self.assertEqual(estimar_quadrimestre_planejado("2023.3", "2026.3"), 10)


class TesteConfiguracao(unittest.TestCase):
    def test_mantem_no_minimo_tres_opcoes_padrao(self):
        bruto = {
            "arquivo_ofertas": "a.xlsx",
            "arquivo_historico": "h.pdf",
            "arquivo_curriculo": "c.json",
            "arquivo_equivalencias": "e.json",
            "arquivo_aliases_oferta": "x.json",
            "top_n": 1
        }
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "config.json"
            caminho.write_text(json.dumps(bruto), encoding="utf-8")
            config = carregar_configuracao(caminho)
            self.assertEqual(config.top_n, 3)
            self.assertEqual(config.min_opcoes_padrao, 3)


class TestePlanejamento(unittest.TestCase):
    def _disciplina(self, codigo, q, recomendacoes=()):
        return DisciplinaCurricular(
            codigo=codigo,
            nome=codigo,
            categoria=Categoria.OBRIGATORIA,
            creditos=4,
            t=4,
            p=0,
            e=0,
            i=4,
            quadrimestre_recomendado=q,
            recomendacoes=tuple(recomendacoes),
        )

    def _oferta(self, codigo, dia, inicio):
        return Oferta(
            codigo_ofertado=codigo,
            codigo_curriculo=codigo,
            nome_turma=codigo,
            codigo_turma="T" + codigo,
            campus="SA",
            turno="NOTURNO",
            creditos=4,
            t=4,
            p=0,
            e=0,
            i=4,
            horarios=(Horario(dia, inicio, inicio + 120, Recorrencia.SEMANAL, "teoria"),),
            docentes=(),
            tpei_original="4-0-4",
            vagas_veteranos=20,
        )

    def test_ordem_curricular_prioriza_atrasadas(self):
        curriculo = {
            "A": self._disciplina("A", 4),
            "B": self._disciplina("B", 9),
            "C": self._disciplina("C", 10),
        }
        ofertas = (
            self._oferta("A", 0, 19 * 60),
            self._oferta("B", 1, 19 * 60),
            self._oferta("C", 2, 19 * 60),
        )
        diags = {c: DiagnosticoDisciplina(c, c, True, True, 1) for c in curriculo}
        resultado = gerar_planejamento(
            ofertas,
            curriculo,
            cumpridas_projetadas=set(),
            concluidas_reais=set(),
            configuracao=ConfiguracaoBusca(
                min_creditos=8,
                max_creditos=8,
                creditos_alvo=8,
                top_n=3,
                quadrimestre_planejado=10,
            ),
            diagnosticos=diags,
        )
        self.assertIn("A", resultado.grades_padrao[0].assinatura_disciplinas)


class TesteProjecaoOtimista(unittest.TestCase):
    def _disc(self, codigo, q, recomendacoes=()):
        return DisciplinaCurricular(codigo, codigo, Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, q, tuple(recomendacoes))

    def _oferta(self, codigo, dia):
        return Oferta(codigo, codigo, codigo, "T"+codigo, "SA", "NOTURNO", 4, 4, 0, 0, 4,
                      (Horario(dia, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4")

    def test_aprovacao_projetada_nao_penaliza_ranking_otimista(self):
        curriculo = {
            "X": self._disc("X", 7),
            "B": self._disc("B", 8, ("X",)),
            "C": self._disc("C", 9),
        }
        ofertas = (self._oferta("B", 0), self._oferta("C", 1))
        diags = {c: DiagnosticoDisciplina(c, c, True, True, 1) for c in curriculo}
        resultado = gerar_planejamento(
            ofertas, curriculo, {"X"}, set(),
            ConfiguracaoBusca(
                min_creditos=4, max_creditos=4, creditos_alvo=4, top_n=3,
                quadrimestre_planejado=10,
                preferencias=PreferenciasConfig(considerar_aprovacoes_projetadas_como_cumpridas=True),
            ), diags,
        )
        self.assertEqual(resultado.grades_padrao[0].assinatura_disciplinas, ("B",))
        self.assertEqual(resultado.grades_padrao[0].metricas.dependencias_em_andamento, 1)

    def test_projecao_pode_ser_penalizada_no_perfil_conservador(self):
        curriculo = {
            "X": self._disc("X", 7),
            "B": self._disc("B", 8, ("X",)),
            "C": self._disc("C", 9),
        }
        ofertas = (self._oferta("B", 0), self._oferta("C", 1))
        diags = {c: DiagnosticoDisciplina(c, c, True, True, 1) for c in curriculo}
        resultado = gerar_planejamento(
            ofertas, curriculo, {"X"}, set(),
            ConfiguracaoBusca(
                min_creditos=4, max_creditos=4, creditos_alvo=4, top_n=3,
                quadrimestre_planejado=10,
                preferencias=PreferenciasConfig(considerar_aprovacoes_projetadas_como_cumpridas=False),
            ), diags,
        )
        self.assertEqual(resultado.grades_padrao[0].assinatura_disciplinas, ("C",))


class TesteValidacaoBusca(unittest.TestCase):
    def test_certificado_indica_busca_completa(self):
        d = DisciplinaCurricular("A", "A", Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, 1)
        o = Oferta("A", "A", "A", "TA", "SA", "NOTURNO", 4, 4, 0, 0, 4,
                   (Horario(0, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4")
        r = gerar_planejamento((o,), {"A": d}, set(), set(), ConfiguracaoBusca(4, 4, 4),
                               {"A": DiagnosticoDisciplina("A", "A", True, True, 1)})
        self.assertTrue(r.validacao_busca["busca_completa"])
        self.assertEqual(r.validacao_busca["conjuntos_unicos_validos"], 1)

    def test_limite_pool_nao_interrompe_ranking_padrao(self):
        curriculo = {
            "A": DisciplinaCurricular("A", "A", Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, 1),
            "B": DisciplinaCurricular("B", "B", Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, 9),
        }
        ofertas = (
            Oferta("A", "A", "A", "TA", "SA", "NOTURNO", 4, 4, 0, 0, 4,
                   (Horario(0, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4"),
            Oferta("B", "B", "B", "TB", "SA", "NOTURNO", 4, 4, 0, 0, 4,
                   (Horario(1, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4"),
        )
        diags = {c: DiagnosticoDisciplina(c, c, True, True, 1) for c in curriculo}
        resultado = gerar_planejamento(
            ofertas, curriculo, set(), set(),
            ConfiguracaoBusca(
                min_creditos=4, max_creditos=4, creditos_alvo=4,
                quadrimestre_planejado=10, max_solucoes_pool=1,
            ),
            diags,
        )
        # O ramo B é visitado antes do ramo A. Mesmo com retenção 1, A deve vencer
        # por ser muito mais atrasada no PPC, comprovando que a busca não parou cedo.
        self.assertEqual(resultado.grades_padrao[0].assinatura_disciplinas, ("A",))
        self.assertTrue(resultado.validacao_busca["limite_pool_atingido"])
        self.assertTrue(resultado.validacao_busca["busca_completa"])
        self.assertTrue(resultado.validacao_busca["ranking_padrao_exato"])
        self.assertFalse(resultado.validacao_busca["fronteira_pareto_completa"])
        self.assertEqual(resultado.validacao_busca["conjuntos_unicos_validos"], 2)
        self.assertEqual(resultado.validacao_busca["conjuntos_retidos_no_pool"], 1)

    def test_truncamento_de_candidatas_remove_garantia_global(self):
        curriculo = {
            codigo: DisciplinaCurricular(codigo, codigo, Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, q)
            for codigo, q in (("A", 1), ("B", 2), ("C", 3))
        }
        ofertas = tuple(
            Oferta(c, c, c, "T"+c, "SA", "NOTURNO", 4, 4, 0, 0, 4,
                   (Horario(i, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4")
            for i, c in enumerate(curriculo)
        )
        diags = {c: DiagnosticoDisciplina(c, c, True, True, 1) for c in curriculo}
        resultado = gerar_planejamento(
            ofertas, curriculo, set(), set(),
            ConfiguracaoBusca(
                min_creditos=4, max_creditos=8, creditos_alvo=8,
                quadrimestre_planejado=10, max_disciplinas_candidatas=2,
            ),
            diags,
        )
        self.assertFalse(resultado.validacao_busca["busca_completa"])
        self.assertTrue(resultado.validacao_busca["busca_completa_nos_candidatos_analisados"])
        self.assertTrue(resultado.validacao_busca["ranking_padrao_exato"])
        self.assertFalse(resultado.validacao_busca["ranking_global_garantido"])
        self.assertTrue(resultado.validacao_busca["limite_candidatas_atingido"])


class TesteAnaliseHistorico(unittest.TestCase):
    def test_aprovacoes_reprovacoes_e_recuperacao(self):
        rep = RegistroHistorico("2024.1", "OBR", "A", "A", 4, 48, 0, "T1", "F", "REP", "")
        apr = RegistroHistorico("2024.2", "OBR", "A", "A", 4, 48, 0, "T2", "B", "APR", "")
        situacao = SituacaoAcademica(concluidas={"A"}, tentativas={"A": [rep, apr]})
        analise = analisar_desempenho_historico(situacao)
        self.assertEqual(analise["aprovacoes"], 1)
        self.assertEqual(analise["reprovacoes"], 1)
        self.assertEqual(len(analise["disciplinas_recuperadas_apos_reprovacao"]), 1)


class TesteEstimativaFormatura(unittest.TestCase):
    def test_estimativa_depende_da_grade(self):
        curriculo = {
            c: DisciplinaCurricular(c, c, Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, i+1)
            for i, c in enumerate(("A", "B", "C"))
        }
        oferta = Oferta("A", "A", "A", "TA", "SA", "NOTURNO", 4, 4, 0, 0, 4,
                        (Horario(0, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4")
        grade = gerar_planejamento(
            (oferta,), curriculo, set(), set(), ConfiguracaoBusca(4,4,4),
            {c: DiagnosticoDisciplina(c,c,True,True,1) for c in curriculo}
        ).grade_principal
        auditoria = {"por_categoria": {
            "obrigatoria": {"exigido": 12, "integralizado_confirmado": 0},
            "opcao_limitada": {"exigido": 0, "integralizado_confirmado": 0},
            "livre": {"exigido": 0, "pendente_estimado": 0},
        }}
        est = estimar_formatura_por_grade(grade, curriculo, set(), auditoria, "2026.3", 4, 0)
        self.assertEqual(est["quadrimestres_estimados_incluindo_atual"], 3)
        self.assertEqual(est["periodo_estimado_minimo"], "2027.2")

    def test_tg_e_estagio_sao_paralelos_a_carga_regular(self):
        curriculo = {
            "A": DisciplinaCurricular("A", "A", Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, 10),
            "B": DisciplinaCurricular("B", "B", Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, 11),
            "ESTM902-17": DisciplinaCurricular("ESTM902-17", "Trabalho de Graduação I", Categoria.OBRIGATORIA, 2, 0, 2, 0, 4, 12),
            "ESTM903-17": DisciplinaCurricular("ESTM903-17", "Trabalho de Graduação II", Categoria.OBRIGATORIA, 2, 0, 2, 0, 4, 13),
            "ESTM904-17": DisciplinaCurricular("ESTM904-17", "Trabalho de Graduação III", Categoria.OBRIGATORIA, 2, 0, 2, 0, 4, 14),
            "ESTM905-17": DisciplinaCurricular("ESTM905-17", "Estágio Curricular em Engenharia de Materiais", Categoria.OBRIGATORIA, 14, 0, 14, 0, 0, 13),
        }
        oferta = Oferta("A", "A", "A", "TA", "SA", "NOTURNO", 4, 4, 0, 0, 4,
                        (Horario(0, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4")
        grade = gerar_planejamento(
            (oferta,), curriculo, set(), set(), ConfiguracaoBusca(4,4,4),
            {c: DiagnosticoDisciplina(c,c,True,True,1) for c in curriculo}
        ).grade_principal
        auditoria = {"por_categoria": {
            "obrigatoria": {"exigido": 28, "integralizado_confirmado": 0, "integralizado_estimado": 0},
            "opcao_limitada": {"exigido": 0, "integralizado_confirmado": 0, "integralizado_estimado": 0},
            "livre": {"exigido": 0, "pendente_estimado": 0},
        }}
        est = estimar_formatura_por_grade(
            grade, curriculo, set(), auditoria, "2026.3", 4, 0,
            quadrimestre_planejado=10, estagio_status="nao_iniciado"
        )
        self.assertEqual(est["creditos_regulares_pendentes_apos_grade"], 4)
        self.assertEqual(est["creditos_tg_pendentes_apos_grade"], 6)
        self.assertEqual(est["creditos_estagio_pendentes_apos_grade"], 14)
        self.assertEqual(est["tg_quadrimestres_futuros_minimos"], 4)
        self.assertEqual(est["quadrimestres_estimados_incluindo_atual"], 5)

    def test_estagio_em_andamento_e_retirado_da_pendencia_projetada(self):
        curriculo = {
            "A": DisciplinaCurricular("A", "A", Categoria.OBRIGATORIA, 4, 4, 0, 0, 4, 10),
            "ESTM905-17": DisciplinaCurricular("ESTM905-17", "Estágio Curricular em Engenharia de Materiais", Categoria.OBRIGATORIA, 14, 0, 14, 0, 0, 13),
        }
        oferta = Oferta("A", "A", "A", "TA", "SA", "NOTURNO", 4, 4, 0, 0, 4,
                        (Horario(0, 19*60, 21*60, Recorrencia.SEMANAL, "teoria"),), (), "4-0-4")
        grade = gerar_planejamento(
            (oferta,), curriculo, {"ESTM905-17"}, set(), ConfiguracaoBusca(4,4,4),
            {c: DiagnosticoDisciplina(c,c,True,True,1) for c in curriculo}
        ).grade_principal
        auditoria = {"por_categoria": {
            "obrigatoria": {"exigido": 18, "integralizado_confirmado": 0, "integralizado_estimado": 14},
            "opcao_limitada": {"exigido": 0, "integralizado_confirmado": 0, "integralizado_estimado": 0},
            "livre": {"exigido": 0, "pendente_estimado": 0},
        }}
        est = estimar_formatura_por_grade(
            grade, curriculo, {"ESTM905-17"}, auditoria, "2026.3", 4, 0,
            quadrimestre_planejado=10, estagio_status="em_andamento"
        )
        self.assertEqual(est["creditos_estagio_pendentes_apos_grade"], 0)
        self.assertEqual(est["estagio_quadrimestres_futuros_minimos"], 0)




class TesteAvaliacoesDocentes(unittest.TestCase):
    def test_avaliacao_docente_flexivel_escolhe_melhor_turma(self):
        from planejador.avaliacoes_docentes import AvaliacaoDocente, BaseAvaliacoesDocentes
        from planejador.modelos import Categoria, DisciplinaCurricular, Oferta

        curriculo = {
            "ESTX001-17": DisciplinaCurricular(
                codigo="ESTX001-17", nome="Disciplina Teste", categoria=Categoria.OBRIGATORIA,
                creditos=4, t=4, p=0, e=0, i=4, quadrimestre_recomendado=1,
            )
        }
        oferta_boa = Oferta(
            codigo_ofertado="ESTX001-17", codigo_curriculo="ESTX001-17",
            nome_turma="Disciplina Teste A1", codigo_turma="A1ESTX001-17SA",
            campus="SA", turno="Noturno", creditos=4, t=4, p=0, e=0, i=4,
            horarios=(), docentes=("PROFESSOR BOM",), tpei_original="4-0-4",
        )
        oferta_ruim = Oferta(
            codigo_ofertado="ESTX001-17", codigo_curriculo="ESTX001-17",
            nome_turma="Disciplina Teste A2", codigo_turma="A2ESTX001-17SA",
            campus="SA", turno="Noturno", creditos=4, t=4, p=0, e=0, i=4,
            horarios=(), docentes=("PROFESSOR RUIM",), tpei_original="4-0-4",
        )
        def av(nome, efeito):
            return AvaliacaoDocente(
                professor=nome, professor_normalizado=nome, aliases_normalizados=(),
                codigo_disciplina="ESTX001", nome_disciplina="Disciplina Teste",
                fonte="disciplina", classificacao="favorável" if efeito > 0 else "evitar",
                qualidade_pedagogica="favorável" if efeito > 0 else "mista",
                risco_academico="baixo" if efeito > 0 else "alto", risco_score_0_100=20 if efeito > 0 else 80,
                score_0_100=70 if efeito > 0 else 40, efeito_ranking_original=efeito,
                efeito_ranking_aplicado=efeito, confianca="alta", conceitos=100,
                comentarios=20, taxa_f_ou_o=5 if efeito > 0 else 30,
                cr_professor=2.8 if efeito > 0 else 1.5, cr_medio_disciplina=2.2,
                diferenca_cr=0.6 if efeito > 0 else -0.7,
            )
        base = BaseAvaliacoesDocentes(
            por_professor_disciplina={
                ("PROFESSOR BOM", "ESTX001"): av("PROFESSOR BOM", 5),
                ("PROFESSOR RUIM", "ESTX001"): av("PROFESSOR RUIM", -6),
            },
            geral_por_professor={}, avisos=[],
        )
        cfg = ConfiguracaoBusca(
            min_creditos=4, max_creditos=4, creditos_alvo=4, top_n=3,
            min_opcoes_padrao=3, avaliacoes_docentes=base,
        )
        resultado = gerar_planejamento(
            (oferta_ruim, oferta_boa), curriculo, set(), set(), cfg, {}
        )
        self.assertIsNotNone(resultado.grade_principal)
        self.assertEqual(resultado.grade_principal.ofertas[0].codigo_turma, "A1ESTX001-17SA")
        self.assertGreater(resultado.grade_principal.metricas.ajuste_avaliacao_docente, 0)




class TesteEditorGrade(unittest.TestCase):
    def _disciplina(self, codigo):
        return DisciplinaCurricular(
            codigo=codigo, nome=codigo, categoria=Categoria.OBRIGATORIA,
            creditos=4, t=4, p=0, e=0, i=4, quadrimestre_recomendado=8,
        )

    def _oferta(self, codigo, dia, inicio):
        return Oferta(
            codigo_ofertado=codigo, codigo_curriculo=codigo,
            nome_turma=f"{codigo} A1", codigo_turma=f"T{codigo}",
            campus="SA", turno="NOTURNO", creditos=4,
            t=4, p=0, e=0, i=4,
            horarios=(Horario(dia, inicio, inicio + 120, Recorrencia.SEMANAL, "teoria"),),
            docentes=(), tpei_original="4-0-4",
        )

    def test_sugere_substituicao_compativel(self):
        curriculo = {c: self._disciplina(c) for c in ("A", "B", "C")}
        a = self._oferta("A", 0, 19 * 60)
        b = self._oferta("B", 1, 19 * 60)
        c = self._oferta("C", 2, 19 * 60)
        config = ConfiguracaoBusca(min_creditos=8, max_creditos=8, creditos_alvo=8)
        grade = montar_grade_personalizada((a,), curriculo, set(), set(), config)
        sugestoes = sugerir_adicoes_grade(grade, (a, b, c), curriculo, set(), set(), config)
        self.assertEqual({s.oferta.codigo_curriculo for s in sugestoes}, {"B", "C"})
        self.assertTrue(all(s.grade_resultante.metricas.creditos_totais == 8 for s in sugestoes))

    def test_nao_sugere_turma_em_conflito_e_explica(self):
        curriculo = {c: self._disciplina(c) for c in ("A", "B")}
        a = self._oferta("A", 0, 19 * 60)
        b = self._oferta("B", 0, 20 * 60)
        config = ConfiguracaoBusca(min_creditos=4, max_creditos=8, creditos_alvo=8)
        grade = montar_grade_personalizada((a,), curriculo, set(), set(), config)
        sugestoes = sugerir_adicoes_grade(grade, (a, b), curriculo, set(), set(), config)
        self.assertEqual(sugestoes, [])
        diagnostico = diagnosticar_adicoes_grade(grade, (a, b), curriculo, set(), config)
        self.assertIn("conflita com A", diagnostico["B"])


if __name__ == "__main__":
    unittest.main()
