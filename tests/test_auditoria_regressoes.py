"""Auditoria independente do ZIP UFABC de setembro/2026.

Execute com o projeto original no PYTHONPATH. Os testes expressam os
comportamentos esperados; falhas demonstram as divergencias descritas no relato.
Somente dados sinteticos sao utilizados. O teste do PDF simula a saida do
pdfplumber; o teste Excel grava e le uma planilha real temporaria.
"""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from planejador.academico import auditoria_integralizacao
from planejador.configuracao import RestricoesConfig
from planejador.historico import consolidar_historico, ler_historico_sigaa
from planejador.modelos import (
    Categoria, DisciplinaCurricular, Horario, Oferta,
    PerfilPlanejamento, Recorrencia, RegistroHistorico,
)
from planejador.ofertas import COLUNAS_DOCENTES, _ler_ofertas_excel
from planejador.planejador import (
    ConfiguracaoBusca, _domina, chave_ordenacao,
    gerar_planejamento, montar_grade_personalizada,
)
from planejador.trajetorias import _criar_tarefas_e_flexiveis, _simular_roadmap


def disc(code, *, name=None, q=1, individual=4):
    return DisciplinaCurricular(
        code, name or code, Categoria.OBRIGATORIA,
        4, 4, 0, 0, individual, q,
    )


def offer(code, section=None, *, day=0, start=19, individual=4):
    return Oferta(
        code, code, code, section or code, 'SA', 'NOTURNO',
        4, 4, 0, 0, individual,
        (Horario(day, start*60, (start+2)*60, Recorrencia.SEMANAL, 'teoria'),),
        (), f'4-0-0-{individual}',
    )


def record(code):
    return RegistroHistorico(
        '2025.1', 'OBR', code, code, 4, 48, 0, 'T1', 'A', 'APR', '',
    )


def test_R01_equivalencia_no_historico_nao_duplica_creditos_livres():
    state = consolidar_historico([record('ANTIGO-17')], {'ANTIGO-17': 'NOVO-23'})
    result = auditoria_integralizacao(
        {'creditos_obrigatorios': 4, 'creditos_opcao_limitada': 0, 'creditos_livres': 4},
        {'NOVO-23': disc('NOVO-23')}, state, state.concluidas,
    )
    groups = result['por_categoria']
    print('R01', {k: v['integralizado_estimado'] for k, v in groups.items()})
    assert groups['obrigatoria']['integralizado_estimado'] == 4
    assert groups['livre']['integralizado_estimado'] == 0


def test_R02_ordem_das_equivalencias_nao_altera_resultado():
    # Mesmo conjunto de regras, mesmo escopo sintetico, apenas ordem diferente.
    a = consolidar_historico([record('A')], {'A': 'B', 'B': 'C'})
    b = consolidar_historico([record('A')], {'B': 'C', 'A': 'B'})
    print('R02', sorted(a.concluidas), sorted(b.concluidas))
    assert a.concluidas == b.concluidas


def test_R03_perfil_compacto_retem_a_melhor_combinacao_de_turmas():
    curriculum = {c: disc(c) for c in ('A', 'B')}
    a = offer('A', 'A_SEG', day=0, start=17)
    b_compact = offer('B', 'B_SEG', day=0, start=21)
    b_no_gap = offer('B', 'B_TER', day=1, start=19)
    cfg = ConfiguracaoBusca(8, 8, 8, perfis_gerados=(PerfilPlanejamento.COMPACTA,))
    result = gerar_planejamento((a, b_compact, b_no_gap), curriculum, set(), set(), cfg, {})
    returned = result.grades_por_perfil[PerfilPlanejamento.COMPACTA]
    alternative = montar_grade_personalizada((a, b_compact), curriculum, set(), set(), cfg)
    key = lambda g: chave_ordenacao(g, 8, PerfilPlanejamento.COMPACTA, cfg.preferencias)
    print('R03', {'returned_days': returned.metricas.dias_com_aula,
                  'alternative_days': alternative.metricas.dias_com_aula,
                  'perfis_exatos': result.validacao_busca['perfis_exatos']})
    assert key(returned) <= key(alternative)


def test_R04_certificado_pareto_nao_omite_truncamento_de_apresentacao():
    # Nove vetores diferentes: maior atraso atendido implica maior carga.
    curriculum = {f'D{i}': disc(f'D{i}', q=10-i, individual=i) for i in range(1, 10)}
    offerings = tuple(offer(f'D{i}', individual=i) for i in range(1, 10))
    cfg = ConfiguracaoBusca(4, 4, 4, quadrimestre_planejado=10)
    result = gerar_planejamento(offerings, curriculum, set(), set(), cfg, {})
    pool = result.grades_pool
    assert len(pool) == 9
    assert not any(_domina(a, b, 4) for a in pool for b in pool if a is not b)
    print('R04', {'nondominated': len(pool), 'returned': len(result.fronteira_pareto),
                  'complete': result.validacao_busca['fronteira_pareto_completa']})
    assert not result.validacao_busca['fronteira_pareto_completa'] or len(result.fronteira_pareto) == len(pool)


def test_R05_disciplina_forcada_nao_e_excluida_pelo_corte_de_candidatas():
    curriculum = {'A': disc('A', q=1), 'B': disc('B', q=2)}
    offerings = (offer('A'), offer('B', day=1))
    cfg = ConfiguracaoBusca(
        4, 4, 4, max_disciplinas_candidatas=1,
        restricoes=RestricoesConfig(disciplinas_obrigatorias_na_grade=('B',)),
    )
    result = gerar_planejamento(offerings, curriculum, set(), set(), cfg, {})
    control = gerar_planejamento(offerings, curriculum, set(), set(), replace(cfg, max_disciplinas_candidatas=2), {})
    assert control.grades_padrao
    print('R05', {'plans': len(result.grades_padrao), 'control_plans': len(control.grades_padrao), 'warnings': result.avisos})
    assert result.grades_padrao


def course_data(*, extension=0, complementary=0, curriculum=None):
    return {
        'registro': SimpleNamespace(rotulo='Curso sintetico'),
        'curriculo': curriculum or {},
        'cumpridas': set(),
        'metadados': {},
        'analise': {'estimativa_formatura': {
            'opcao_limitada_pendente': 0, 'livres_pendentes': 0,
            'quadrimestres_cadeia': 0, 'quadrimestres_tg': 0, 'quadrimestres_estagio': 0,
            'extensao_pendente_maxima_horas': extension,
            'atividades_complementares_pendentes_horas': complementary,
        }},
    }


def test_R06_sem_tarefa_que_cumpra_extensao_nao_ha_marco_incondicional():
    courses = {'c': course_data(extension=240, complementary=48)}
    roadmap, milestones = _simular_roadmap([], courses, ['c'], 'simultanea', 16, '2026.3')
    print('R06', {'milestones': milestones, 'roadmap': roadmap})
    assert 'c' not in milestones


def test_R07_limite_de_horizonte_nao_declara_tarefas_restantes_concluidas():
    tasks = [
        {'chave': f'D{i}', 'nome': f'D{i}', 'creditos': 4, 'quadrimestre': 1,
         'obrigatoria_em': {'c': {'codigo': f'D{i}', 'creditos': 4}}, 'flexivel_em': {}}
        for i in range(61)
    ]
    roadmap, milestones = _simular_roadmap(tasks, {'c': course_data()}, ['c'], 'simultanea', 4, '2026.3')
    scheduled = sum(len(r['focos']) for r in roadmap)
    print('R07', {'tasks': len(tasks), 'scheduled': scheduled, 'milestones': milestones})
    assert 'c' not in milestones or scheduled == len(tasks)


def test_R08_historico_com_linha_incompleta_nao_e_aceito_silenciosamente(tmp_path):
    pdf = tmp_path / 'synthetic.pdf'
    pdf.write_bytes(b'%PDF-placeholder')
    header = ['Ano/Período', 'Categoria', 'Codigo', 'Nome', 'Cr', 'CH', 'E', 'Turma', 'Conceito', 'Situação', 'Docente']
    good = ['2025.1', 'OBR', 'A-17', 'A', '4', '48', '0', 'T1', 'A', 'APR', '']
    incomplete = ['2025.1', 'OBR', 'B-17', 'B', '4', '48', '0', 'T1', 'A', 'APR']
    page = SimpleNamespace(extract_text=lambda: '', extract_tables=lambda: [[header, good, incomplete]])
    context = SimpleNamespace(pages=[page])
    with patch('planejador.historico.pdfplumber.open') as opened:
        opened.return_value.__enter__.return_value = context
        with pytest.raises(ValueError):
            result, _, _ = ler_historico_sigaa(pdf)
            print('R08', {'table_rows': 2, 'accepted_records': len(result)})


def test_R09_pratica_nao_interpretada_nao_pode_sumir_da_oferta(tmp_path):
    row = {name: '' for name in COLUNAS_DOCENTES}
    row.update({
        'CÓDIGO DE TURMA': 'TA-17', 'TURMA': 'A', 'turma': 'A-17',
        'TEORIA': 'segunda das 19:00 as 21:00, semanal',
        'PRÁTICA': 'quarta-feira 19h-21h',
        'CAMPUS': 'SA', 'TURNO': 'NOTURNO', 'TPEI': '2-2-0-4',
    })
    path = tmp_path / 'offerings.xlsx'
    pd.DataFrame([row]).to_excel(path, index=False)
    result = _ler_ofertas_excel(path, {'A-17'}, {'A-17': 'A'}, {}, 'SA', 'NOTURNO', set())
    print('R09', {'accepted_offers': len(result.ofertas), 'warnings': result.avisos,
                  'meetings': [[h.tipo for h in o.horarios] for o in result.ofertas]})
    assert not result.ofertas or result.avisos or any(
        h.tipo == 'pratica' for o in result.ofertas for h in o.horarios
    )


def test_R10_nome_igual_sem_regra_nao_basta_para_fundir_componentes():
    courses = {
        'a': course_data(curriculum={'X': disc('X', name='Projeto integrado')}),
        'b': course_data(curriculum={'Y': disc('Y', name='Projeto integrado')}),
    }
    tasks, *_ = _criar_tarefas_e_flexiveis(courses, ['a', 'b'])
    print('R10', {'distinct_codes': ['X', 'Y'], 'tasks': len(tasks),
                  'unique_credits': sum(t['creditos'] for t in tasks)})
    assert len(tasks) == 2
