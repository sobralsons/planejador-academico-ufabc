from dataclasses import replace
from itertools import product
from pathlib import Path
import json
import random

import pandas as pd
import pytest

from planejador.configuracao import PreferenciasConfig
from planejador.historico import consolidar_historico
from planejador.modelos import PerfilPlanejamento, ResumoHistorico
from planejador.multicurso import _livres_potenciais
from planejador.ofertas import COLUNAS_DOCENTES, _ler_ofertas_excel, ler_ofertas_ajuste_pdf, ler_ofertas_matricula_inicial_completa
from planejador.planejador import ConfiguracaoBusca, chave_ordenacao, gerar_planejamento, montar_grade_personalizada
from planejador.sessao import ArquivosSessao
from planejador.trajetorias import construir_plano_trajetoria, gerar_relatorio_trajetoria_html
from test_auditoria_regressoes import disc, offer, record
from test_trajetorias import _salvar_curriculo, _analise, _disc
from planejador.multicurso import RegistroCurriculo

BASE = Path(__file__).resolve().parents[1]


def test_coleta_autenticada_nao_faz_parte_do_produto():
    app = (BASE / "app.py").read_text(encoding="utf-8")
    requirements = (BASE / "requirements.txt").read_text(encoding="utf-8")
    assert "coletar_avaliacoes_ufabc_next" not in app
    assert "sessao_ufabc_next" not in app
    assert "playwright" not in requirements.lower()
    assert not (BASE / "ferramentas/coletar_avaliacoes_ufabc_next.py").exists()
    assert not (BASE / "config/ufabc_next.json").exists()


def test_reconhecimento_composto_ciclico_preserva_origens_e_direcao():
    registros = [record('A'), record('B')]
    simples = {'C': 'D', 'D': 'C'}
    s = consolidar_historico(registros, simples, [({'A', 'B'}, 'C')])
    inversa = consolidar_historico(registros, dict(reversed(list(simples.items()))), [({'A', 'B'}, 'C')])
    assert s.concluidas == inversa.concluidas == {'A', 'B', 'C', 'D'}
    assert s.origens_conclusao == inversa.origens_conclusao
    assert s.origens_conclusao['D'] == {'A', 'B'}
    assert _livres_potenciais(s, {'D': disc('D')}) == 0
    assert consolidar_historico([record('A')], simples, [({'A', 'B'}, 'C')]).concluidas == {'A'}
    assert consolidar_historico([record('D')], simples, [({'A', 'B'}, 'C')]).concluidas == {'C', 'D'}


@pytest.mark.parametrize('leitor', ['regular', 'matricula', 'ajuste'])
def test_trecho_adicional_nao_lido_bloqueia_turma_em_todos_os_leitores(tmp_path, monkeypatch, leitor):
    row = {name: '' for name in COLUNAS_DOCENTES}
    row.update({'CÓDIGO DE TURMA':'NA1BIS0001-15SA', 'TURMA':'A', 'turma':'BIS0001-15',
                'TEORIA':'segunda das 19:00 as 21:00, semanal; quarta 19h-21h',
                'PRÁTICA':'', 'CAMPUS':'SA', 'TURNO':'NOTURNO', 'TPEI':'4-0-0-4'})
    path = tmp_path/'oferta.xlsx'
    pd.DataFrame([row]).to_excel(path,index=False)
    if leitor == 'regular':
        result = _ler_ofertas_excel(path, {'BIS0001-15'}, {}, {}, 'SA', 'NOTURNO', set())
    elif leitor == 'matricula':
        result = ler_ofertas_matricula_inicial_completa(path, {}, 'SA', 'NOTURNO')
    else:
        pdfrow = dict(row, **{'CODIGO DE TURMA':row['CÓDIGO DE TURMA'], 'PRATICA':'', 'VAGAS REMANESCENTES':'1'})
        monkeypatch.setattr('planejador.ofertas._linhas_tabelas_pdf', lambda p: iter([(1, 1, pdfrow)]))
        result = ler_ofertas_ajuste_pdf(path, {'BIS0001-15'}, {}, {}, 'SA', 'NOTURNO', set())
    assert not result.ofertas
    assert result.avisos


def test_sessoes_isolam_upload_config_e_saida():
    a, b = ArquivosSessao(), ArquivosSessao()
    try:
        for directory in ('entradas', 'saidas', 'dados'):
            (getattr(a,directory)/'igual.txt').write_text('A')
            (getattr(b,directory)/'igual.txt').write_text('B')
            assert (getattr(a,directory)/'igual.txt').read_text() == 'A'
        a.configuracao.write_text('A');b.configuracao.write_text('B')
        a.limpar()
        assert not a.raiz.exists()
        assert b.configuracao.read_text() == 'B'
    finally:
        a.limpar();b.limpar()


def test_projecao_indeterminada_chega_ao_relatorio(tmp_path):
    curr, eq = _salvar_curriculo(tmp_path, 'Curso', [_disc('A','A','obrigatoria')])
    reg = {'c': RegistroCurriculo('c','Curso',curr,eq,'Teste')}
    analysis = _analise('c','Curso')
    analysis['cumpridas_apos_grade'] = ['A']
    analysis['estimativa_formatura'].update(opcao_limitada_pendente=0, creditos_regulares_pendentes=0, extensao_pendente_maxima_horas=240)
    plan = construir_plano_trajetoria(tmp_path,[analysis],reg,['c'],'2026.3',16,1)
    assert plan['periodo_conclusao_todos_minimo'] == 'Indeterminada'
    assert plan['quadrimestres_para_todos_minimo'] is None
    assert not plan['cursos'][0]['conclusao_modelada']
    output = tmp_path/'relatorio.html'
    gerar_relatorio_trajetoria_html(output,plan)
    assert 'Indeterminada' in output.read_text()
    assert 'None' not in output.read_text()


def test_perfis_conferem_com_enumeracao_independente_de_turmas():
    rng = random.Random(20260914)
    profiles = tuple(p for p in PerfilPlanejamento if p != PerfilPlanejamento.PADRAO)
    for _ in range(12):
        curriculum = {c:disc(c,q=rng.randint(1,4)) for c in ('A','B','C')}
        groups = [[offer(c,c+str(i),day=rng.randrange(3),start=rng.choice([17,19,21])) for i in range(2)] for c in curriculum]
        cfg = ConfiguracaoBusca(4,8,8,quadrimestre_planejado=4,perfis_gerados=profiles)
        candidates = []
        for selection in product(*[[None,*g] for g in groups]):
            selected = tuple(o for o in selection if o is not None)
            if not 4 <= sum(o.creditos for o in selected) <= 8: continue
            try: candidates.append(montar_grade_personalizada(selected,curriculum,set(),set(),cfg))
            except ValueError: pass
        result = gerar_planejamento(tuple(o for g in groups for o in g),curriculum,set(),set(),cfg,{})
        for profile in profiles:
            key = lambda g: chave_ordenacao(g,8,profile,cfg.preferencias)
            assert key(result.grades_por_perfil[profile]) == min(map(key,candidates))
        assert result.validacao_busca['grades_concretas_validas'] == len(candidates)


def test_orquestracao_usa_dados_publicos_e_saida_privada(tmp_path, monkeypatch):
    import main
    # Integra o motor e os exportadores; somente a extração do PDF é simulada.
    raw = json.loads((BASE/'dados/curriculos/bct_2015.json').read_text(encoding='utf-8'))
    d = next(d for d in raw['disciplinas'] if d['categoria']=='obrigatoria' and d['creditos']==4 and d.get('p',0)==0)
    row = {name:'' for name in COLUNAS_DOCENTES}
    row.update({'CÓDIGO DE TURMA':'NA1'+d['codigo']+'SA','TURMA':d['nome'],'turma':d['codigo'],
                'TEORIA':'segunda das 19:00 as 21:00, semanal','PRÁTICA':'','CAMPUS':'SA','TURNO':'NOTURNO','TPEI':'4-0-0-4'})
    excel=tmp_path/'ofertas.xlsx'
    invalid = dict(row, **{'CÓDIGO DE TURMA':'NB1'+d['codigo']+'SA', 'PRÁTICA':'quarta 19h-21h'})
    pd.DataFrame([row,invalid]).to_excel(excel,index=False)
    pdf=tmp_path/'historico.pdf';pdf.write_bytes(b'%PDF-test')
    monkeypatch.setattr(main,'ler_historico_sigaa',lambda p: ([],{},ResumoHistorico()))
    config=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    config.update(arquivo_historico=str(pdf),arquivo_ofertas=str(excel),arquivo_ofertas_inicial=str(excel),
                  min_creditos=4,max_creditos=4,creditos_alvo=4,min_creditos_flexivel=4,
                  gerar_cenarios_comparativos=False,gerar_planejamento_multiquadrimestral=False)
    config['trajetoria']['gerar_relatorio']=False
    cfg=tmp_path/'config_interface.json';cfg.write_text(json.dumps(config))
    output=tmp_path/'privado'
    paths=main.executar(cfg,base_dados=BASE,diretorio_saidas=output)
    assert len(paths)==3
    assert all(p.parent==output and p.is_file() for p in paths)
    assert json.loads(paths[2].read_text(encoding='utf-8'))['avisos']
