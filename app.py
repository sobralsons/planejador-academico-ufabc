from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import time
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from main import executar
from planejador.avaliacoes_docentes import (
    carregar_avaliacoes_docentes,
    gerar_consultas_csv,
    resumo_avaliacoes,
)
from planejador.curriculo import carregar_aliases_oferta, carregar_curriculo, carregar_equivalencias
from planejador.academico import estimar_quadrimestre_planejado
from planejador.historico import STATUS_EM_ANDAMENTO, consolidar_historico, ler_historico_sigaa
from planejador.ofertas import ler_ofertas
from planejador.modelos import Grade, Oferta
from planejador.multicurso import (
    carregar_registro_curriculos, comparar_curriculos, resolver_curriculo,
)
from planejador.planejador import (
    diagnosticar_adicoes_grade,
    montar_grade_personalizada,
    sugerir_adicoes_grade,
)
from planejador.utils import normalizar_texto
from planejador.trajetorias import (
    construir_plano_trajetoria, gerar_cenarios_trajetoria,
    gerar_relatorio_trajetoria_html,
)

BASE = Path(__file__).resolve().parent
CONFIG_PADRAO = BASE / "config" / "config.json"
CONFIG_INTERFACE = BASE / "config" / "config_interface.json"
ENTRADAS = BASE / "entradas"
ENTRADAS.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Planejador de Matrícula — UFABC",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
[data-testid="stAppViewContainer"] { background: #f4f7f5; }
[data-testid="stSidebar"] { background: #153f31; }
[data-testid="stSidebar"] * { color: #f7fbf8; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea { color: #17211c !important; }
.main .block-container { max-width: 1320px; padding-top: 1.8rem; }
h1, h2, h3 { letter-spacing: -0.025em; }
.hero { background: linear-gradient(135deg,#153f31,#287358); color:white; padding:28px 32px; border-radius:18px; margin-bottom:22px; box-shadow:0 12px 35px #153f3120; }
.hero h1 { margin:0 0 8px; font-size:2.25rem; }
.hero p { margin:0; color:#e5f0ea; }
.info-box { background:white; border:1px solid #dce5df; border-radius:14px; padding:16px 18px; margin:8px 0; }
[data-testid="stMetric"] { background:white; border:1px solid #dce5df; padding:14px; border-radius:12px; }
.stButton>button { background:#1f5b45; color:white; border:none; border-radius:10px; font-weight:700; padding:.65rem 1.2rem; }
.stButton>button:hover { background:#287358; color:white; border:none; }
.stDownloadButton>button { border-radius:10px; }
.small-note { color:#607068; font-size:.9rem; }
.trajectory-builder { background:linear-gradient(135deg,#ffffff,#edf6f2); border:1px solid #cfe0d7; border-radius:20px; padding:22px 24px; margin:0 0 22px; box-shadow:0 10px 30px #153f3112; }
.trajectory-builder h2 { margin:0 0 6px; }
.step-label { color:#1f6a50; font-weight:800; font-size:.76rem; text-transform:uppercase; letter-spacing:.08em; margin-top:8px; }
.trajectory-summary { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:14px 0 20px; }
.trajectory-summary>div { background:white; border:1px solid #dce5df; border-radius:14px; padding:15px; }
.trajectory-summary span { display:block; color:#667970; font-size:.78rem; text-transform:uppercase; font-weight:700; }
.trajectory-summary strong { display:block; margin-top:5px; font-size:1.15rem; }
.path-card { background:white; border:1px solid #dce5df; border-radius:16px; padding:17px; height:100%; box-shadow:0 7px 20px #153f310d; }
.path-card .path-priority { color:#287358; font-size:.74rem; font-weight:800; text-transform:uppercase; }
.path-card .path-date { font-size:1.4rem; font-weight:800; margin:8px 0 3px; }
.path-card .path-meta { color:#63746c; font-size:.88rem; }
.confidence-badge { display:inline-block; border-radius:999px; padding:5px 10px; background:#e8f3ed; color:#1f5b45; font-weight:800; font-size:.8rem; }
@media(max-width:900px){ .trajectory-summary { grid-template-columns:repeat(2,1fr); } }
</style>
""",
    unsafe_allow_html=True,
)


def ler_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def salvar_upload(upload, destino: Path) -> Path:
    destino.write_bytes(upload.getvalue())
    return destino


def localizar_padrao(nome: str) -> Path:
    return ENTRADAS / nome


def extrair_docentes(caminho: Path) -> list[str]:
    if not caminho.exists():
        return []
    try:
        df = pd.read_excel(caminho)
    except Exception:
        return []
    colunas = [c for c in df.columns if "DOCENTE" in normalizar_texto(c)]
    nomes: set[str] = set()
    for coluna in colunas:
        for valor in df[coluna].dropna():
            texto = str(valor).strip()
            if texto and texto not in {"0", "0.0"} and "DEFINIR DOCENTE" not in normalizar_texto(texto):
                nomes.add(normalizar_texto(texto))
    return sorted(nomes)


def em_andamento_historico(caminho: Path) -> list[tuple[str, str]]:
    if not caminho.exists():
        return []
    try:
        registros, _, _ = ler_historico_sigaa(caminho)
    except Exception:
        return []
    por_codigo: dict[str, str] = {}
    for registro in registros:
        if registro.situacao in STATUS_EM_ANDAMENTO:
            por_codigo[registro.codigo] = registro.nome
    return sorted(por_codigo.items())


def path_relativo(path: Path) -> str:
    try:
        return str(path.relative_to(BASE)).replace("\\", "/")
    except ValueError:
        return str(path)




def formatar_minutos(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def formatar_horarios_oferta(oferta: Oferta) -> str:
    nomes_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    partes = []
    for h in sorted(oferta.horarios, key=lambda x: (x.dia, x.inicio, x.fim, x.recorrencia.value)):
        recorrencia = {
            "semanal": "semanal",
            "quinzenal_i": "quinz. I",
            "quinzenal_ii": "quinz. II",
            "desconhecida": "recorrência não identificada",
        }.get(h.recorrencia.value, h.recorrencia.value)
        partes.append(
            f"{nomes_dias[h.dia]} {formatar_minutos(h.inicio)}–{formatar_minutos(h.fim)} ({recorrencia})"
        )
    return "; ".join(partes) or "Horário não informado"


def tabela_grade(grade: Grade, curriculo_local: dict) -> pd.DataFrame:
    linhas = []
    for oferta in sorted(grade.ofertas, key=lambda x: (curriculo_local[x.codigo_curriculo].quadrimestre_recomendado or 99, x.codigo_curriculo)):
        disciplina = curriculo_local[oferta.codigo_curriculo]
        avaliacoes = grade.avaliacoes_docentes_por_disciplina.get(oferta.codigo_curriculo, ())
        docente_texto = ", ".join(oferta.docentes) or "A definir"
        classificacoes = [a.get("classificacao", "") for a in avaliacoes if a.get("classificacao")]
        linhas.append({
            "Código": oferta.codigo_curriculo,
            "Disciplina": disciplina.nome,
            "PPC": f"Q{disciplina.quadrimestre_recomendado}" if disciplina.quadrimestre_recomendado else "—",
            "Turma": oferta.nome_turma,
            "Créditos": oferta.creditos,
            "Docente(s)": docente_texto,
            "Avaliação docente": " · ".join(classificacoes) if classificacoes else "Sem dados",
            "Horários": formatar_horarios_oferta(oferta),
        })
    return pd.DataFrame(linhas)


def grade_personalizada_json(grade: Grade, curriculo_local: dict) -> str:
    dados = {
        "tipo": "grade_personalizada",
        "disciplinas": [
            {
                "codigo": oferta.codigo_curriculo,
                "nome": curriculo_local[oferta.codigo_curriculo].nome,
                "turma": oferta.nome_turma,
                "codigo_turma": oferta.codigo_turma,
                "creditos": oferta.creditos,
                "docentes": list(oferta.docentes),
                "horarios": [
                    {
                        "dia": h.dia,
                        "inicio": h.inicio,
                        "fim": h.fim,
                        "recorrencia": h.recorrencia.value,
                        "tipo": h.tipo,
                    }
                    for h in oferta.horarios
                ],
            }
            for oferta in grade.ofertas
        ],
        "metricas": grade.metricas.__dict__,
        "recomendacoes_faltantes": grade.recomendacoes_faltantes_por_disciplina,
        "dependencias_em_andamento": grade.dependencias_em_andamento_por_disciplina,
        "avaliacoes_docentes": grade.avaliacoes_docentes_por_disciplina,
    }
    return json.dumps(dados, ensure_ascii=False, indent=2)


def grade_personalizada_html(grade: Grade, curriculo_local: dict) -> str:
    linhas = []
    for oferta in grade.ofertas:
        disciplina = curriculo_local[oferta.codigo_curriculo]
        linhas.append(
            "<tr>"
            f"<td><strong>{oferta.codigo_curriculo}</strong></td>"
            f"<td>{disciplina.nome}</td>"
            f"<td>{oferta.nome_turma}</td>"
            f"<td>{oferta.creditos}</td>"
            f"<td>{', '.join(oferta.docentes) or 'A definir'}</td>"
            f"<td>{formatar_horarios_oferta(oferta)}</td>"
            "</tr>"
        )
    m = grade.metricas
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Grade personalizada</title>
<style>body{{font-family:Arial,sans-serif;background:#f4f7f5;color:#17211c;margin:0}}header{{background:#174936;color:white;padding:28px}}main{{max-width:1150px;margin:24px auto;background:white;padding:26px;border-radius:16px}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0}}.metric{{background:#eef4f0;padding:14px;border-radius:10px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #dde6e0;text-align:left}}th{{background:#e5efe9}}</style></head>
<body><header><h1>Grade personalizada — UFABC</h1></header><main>
<div class='metrics'><div class='metric'><b>Créditos</b><br>{m.creditos_totais}</div><div class='metric'><b>Dias</b><br>{m.dias_com_aula}</div><div class='metric'><b>Janelas</b><br>{m.buracos_minutos} min</div><div class='metric'><b>Carga total</b><br>{m.carga_total_referencia}</div><div class='metric'><b>Ajuste docente</b><br>{m.ajuste_avaliacao_docente:+.1f}</div></div>
<table><thead><tr><th>Código</th><th>Disciplina</th><th>Turma</th><th>Cr.</th><th>Docente(s)</th><th>Horários</th></tr></thead><tbody>{''.join(linhas)}</tbody></table>
<p><small>Grade montada manualmente. A disponibilidade de vagas e a matrícula não são garantidas.</small></p></main></body></html>"""



def renderizar_plano_trajetoria(plano: dict, cenarios: list[dict] | None = None, relatorio: Path | None = None) -> None:
    if not plano:
        st.info("Configure os cursos e clique em **Analisar minha trajetória** para visualizar as estimativas.")
        return

    st.markdown(
        f"""
        <div class='trajectory-summary'>
          <div><span>Conclusão de todas</span><strong>{plano.get('periodo_conclusao_todos_minimo','—')}–{plano.get('periodo_conclusao_todos_prudente','—')}</strong></div>
          <div><span>Créditos únicos estimados</span><strong>{plano.get('creditos_regulares_unicos_estimados',0)} cr</strong></div>
          <div><span>Economia por sobreposição</span><strong>{plano.get('creditos_economizados_por_sobreposicao',0)} cr</strong></div>
          <div><span>Confiança</span><strong>{plano.get('confianca',{}).get('classificacao','—').title()} · {plano.get('confianca',{}).get('score_0_100','—')}/100</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Em quanto tempo posso me formar?")
    cursos = plano.get("cursos", [])
    cols = st.columns(min(3, max(1, len(cursos))))
    for i, curso in enumerate(cursos):
        with cols[i % len(cols)]:
            st.markdown(
                f"""
                <div class='path-card'>
                  <div class='path-priority'>Prioridade {curso.get('prioridade','—')}</div>
                  <strong>{curso.get('rotulo','')}</strong>
                  <div class='path-date'>{curso.get('periodo_no_plano_conjunto','—')}</div>
                  <div class='path-meta'>Faixa prudente até {curso.get('periodo_prudente_no_plano','—')}</div>
                  <div class='path-meta'>{curso.get('percentual_conclusao',0)}% estimado · {curso.get('creditos_regulares_pendentes',0)} cr pendentes</div>
                  <div class='path-meta'>Se cursado isoladamente: {curso.get('periodo_se_cursado_isoladamente','—')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if cenarios:
        st.markdown("### E se eu mudar de plano?")
        df_cenarios = pd.DataFrame([
            {
                "Cenário": c.get("nome"),
                "Formações": " + ".join(c.get("cursos", [])),
                "Conclusão mínima": c.get("periodo_minimo"),
                "Faixa prudente": c.get("periodo_prudente"),
                "Quadrimestres": c.get("quadrimestres_minimos"),
                "Créditos únicos": c.get("creditos_unicos"),
                "Economia por sobreposição": c.get("economia_sobreposicao"),
                "Confiança": str(c.get("confianca", "")).title(),
            }
            for c in cenarios
        ])
        st.dataframe(df_cenarios, use_container_width=True, hide_index=True)

    compartilhadas = plano.get("disciplinas_compartilhadas", [])
    if compartilhadas:
        st.markdown("### Onde os cursos se sobrepõem")
        st.caption("Estas disciplinas são estratégicas porque atendem mais de uma formação ou preenchem categorias diferentes simultaneamente.")
        st.dataframe(
            pd.DataFrame([
                {
                    "Disciplina": x.get("disciplina"),
                    "Créditos únicos": x.get("creditos_unicos"),
                    "Cursos atendidos": x.get("quantidade_cursos"),
                    "Formações": " · ".join(x.get("cursos", [])),
                    "Tipo de aproveitamento": x.get("tipo"),
                }
                for x in compartilhadas[:20]
            ]),
            use_container_width=True, hide_index=True,
        )

    roadmap = plano.get("roadmap", [])
    if roadmap:
        st.markdown("### Roteiro acadêmico aproximado")
        st.caption("O roteiro prioriza ordem curricular e sobreposição. A oferta e os horários devem ser recalculados em cada matrícula.")
        st.dataframe(
            pd.DataFrame([
                {
                    "Quadrimestre": x.get("periodo"),
                    "Carga estimada": x.get("creditos_estimados"),
                    "Focos sugeridos": " · ".join(x.get("focos", [])),
                    "Formações impactadas": " · ".join(x.get("cursos_impactados", [])),
                    "Marco de conclusão": " · ".join(x.get("diplomas_estimados", [])) or "—",
                }
                for x in roadmap
            ]),
            use_container_width=True, hide_index=True,
        )

    confianca = plano.get("confianca", {})
    with st.expander("Entender a confiança e as premissas do cálculo"):
        st.markdown(f"**Confiança {str(confianca.get('classificacao','—')).title()} — {confianca.get('score_0_100','—')}/100**")
        for fator in confianca.get("fatores", []):
            st.write("- " + str(fator))
        st.markdown("**Premissas**")
        for item in plano.get("premissas", []):
            st.write("- " + str(item))

    if relatorio and relatorio.exists():
        b1, b2 = st.columns([1, 1])
        b1.download_button(
            "Baixar relatório completo da trajetória",
            relatorio.read_bytes(),
            file_name="relatorio_trajetoria_academica.html",
            mime="text/html",
            use_container_width=True,
        )
        if b2.button("Visualizar relatório completo nesta página", use_container_width=True, key=f"preview_traj_{relatorio.stat().st_mtime_ns}"):
            st.session_state["mostrar_preview_trajetoria"] = not st.session_state.get("mostrar_preview_trajetoria", False)
        if st.session_state.get("mostrar_preview_trajetoria", False):
            components.html(relatorio.read_text(encoding="utf-8"), height=1100, scrolling=True)


config_base = ler_json(CONFIG_PADRAO)
registro_curriculos = carregar_registro_curriculos(
    BASE, config_base.get("arquivo_registro_curriculos", "dados/registro_curriculos.json")
)
ids_registro = list(registro_curriculos)
id_padrao = config_base.get("curriculo_principal_id", "materiais_2017")
if id_padrao not in registro_curriculos:
    id_padrao = ids_registro[0]
rotulos_curriculos = {id_: registro_curriculos[id_].rotulo for id_ in ids_registro}

st.markdown(
    """
<div class="hero">
  <h1>Planejador Acadêmico — UFABC</h1>
  <p>Planeje a próxima matrícula e simule sua trajetória completa: mudança de curso, dupla ou tríplice formação, datas de conclusão e aproveitamento entre matrizes.</p>
</div>
""",
    unsafe_allow_html=True,
)

traj_padrao = config_base.get("trajetoria", {}) or {}
curso_atual_padrao = traj_padrao.get("curso_atual_id", id_padrao)
if curso_atual_padrao not in registro_curriculos:
    curso_atual_padrao = id_padrao
ordem_padrao = [x for x in traj_padrao.get("ordem_ids", [id_padrao]) if x in registro_curriculos][:3]
if not ordem_padrao:
    ordem_padrao = [id_padrao]

st.markdown(
    """<div class='trajectory-builder'><div class='step-label'>Comece por aqui</div>
    <h2>Qual trajetória você quer planejar?</h2>
    <p class='small-note'>Escolha seu curso atual, a ordem dos diplomas desejados e como pretende conciliá-los. Você poderá alterar tudo e comparar cenários.</p></div>""",
    unsafe_allow_html=True,
)

objetivos_rotulos = {
    "Continuar e concluir meu curso principal": "continuar",
    "Avaliar uma mudança de curso": "mudar",
    "Fazer duas formações": "dupla",
    "Fazer três formações": "tripla",
    "Explorar possibilidades sem decidir agora": "explorar",
}
obj_default = traj_padrao.get("objetivo", "dupla" if len(ordem_padrao) == 2 else "tripla" if len(ordem_padrao) >= 3 else "continuar")
objetivo_label = st.radio(
    "Seu objetivo",
    list(objetivos_rotulos),
    index=next((i for i, v in enumerate(objetivos_rotulos.values()) if v == obj_default), 0),
    horizontal=True,
    key="traj_objetivo",
)
objetivo_trajetoria = objetivos_rotulos[objetivo_label]

p1, p2, p3 = st.columns([1, 1, 1.35])
curso_atual_id = p1.selectbox(
    "Curso atual ou vínculo que deseja usar como referência",
    ids_registro,
    index=ids_registro.index(curso_atual_padrao),
    format_func=lambda x: rotulos_curriculos[x],
    key="traj_curso_atual",
)
primeiro_padrao = ordem_padrao[0] if ordem_padrao[0] in ids_registro else id_padrao
curriculo_principal_id = p2.selectbox(
    "Primeira formação prioritária",
    ids_registro,
    index=ids_registro.index(primeiro_padrao),
    format_func=lambda x: rotulos_curriculos[x],
    key="traj_primeiro_diploma",
)
opcoes_adicionais = [x for x in ids_registro if x != curriculo_principal_id]
default_adicionais = [x for x in ordem_padrao[1:] if x in opcoes_adicionais]
adicionais_selecionados = p3.multiselect(
    "Outras formações desejadas — até duas",
    opcoes_adicionais,
    default=default_adicionais,
    max_selections=2,
    format_func=lambda x: rotulos_curriculos[x],
    key="traj_cursos_adicionais",
)

if objetivo_trajetoria == "continuar" and curriculo_principal_id != curso_atual_id:
    st.info("No modo continuar, a primeira formação foi ajustada automaticamente para o curso atual.")
    curriculo_principal_id = curso_atual_id
if objetivo_trajetoria == "mudar" and curriculo_principal_id == curso_atual_id:
    st.warning("Para comparar uma mudança, escolha uma primeira formação diferente do curso atual.")

if objetivo_trajetoria in {"continuar", "mudar"}:
    ordem_trajetoria = [curriculo_principal_id]
elif objetivo_trajetoria == "dupla":
    ordem_trajetoria = [curriculo_principal_id, *adicionais_selecionados[:1]]
elif objetivo_trajetoria == "tripla":
    ordem_trajetoria = [curriculo_principal_id, *adicionais_selecionados[:2]]
else:
    ordem_trajetoria = [curriculo_principal_id, *adicionais_selecionados[:2]]
ordem_trajetoria = list(dict.fromkeys(ordem_trajetoria))

if objetivo_trajetoria == "dupla" and len(ordem_trajetoria) < 2:
    st.info("Selecione uma segunda formação para comparar uma dupla formação.")
if objetivo_trajetoria == "tripla" and len(ordem_trajetoria) < 3:
    st.info("Selecione duas formações adicionais para simular três diplomas.")

estrategias_rotulos = {
    "Simultânea — avançar em todos desde o início": "simultanea",
    "Híbrida — priorizar disciplinas compartilhadas e depois o curso principal": "hibrida",
    "Sequencial — concluir um curso antes de concentrar no seguinte": "sequencial",
}
estrategia_padrao = traj_padrao.get("estrategia", "hibrida")
e1, e2, e3, e4 = st.columns([1.5, .8, .8, .8])
estrategia_label = e1.selectbox(
    "Estratégia da trajetória",
    list(estrategias_rotulos),
    index=next((i for i, v in enumerate(estrategias_rotulos.values()) if v == estrategia_padrao), 1),
    key="traj_estrategia",
)
estrategia_trajetoria = estrategias_rotulos[estrategia_label]
periodo_trajetoria = e2.text_input(
    "Início", value=str(config_base.get("periodo_planejamento", "2026.3")), key="traj_periodo"
).strip()
ritmo_formatura = e3.number_input(
    "Créditos/quad", min_value=4, max_value=28,
    value=int(config_base.get("creditos_futuros_por_quadrimestre", 16)), key="traj_ritmo",
)
margem_formatura = e4.number_input(
    "Margem prudente", min_value=0, max_value=5,
    value=int(config_base.get("margem_formatura_quadrimestres", 1)), key="traj_margem",
)

projecao_traj_label = st.radio(
    "Para esta simulação, como tratar as matérias que você está cursando agora?",
    ["Otimista — considerar aprovação", "Conservador — considerar somente o que já foi aprovado"],
    horizontal=True,
    key="traj_projecao",
)
modo_projecao_trajetoria = "todas" if projecao_traj_label.startswith("Otimista") else "nenhuma"

# A formação prioritária define a busca de horários; os demais cursos entram na análise paralela.
curriculos_comparacao = []
for id_ in [*ordem_trajetoria, curso_atual_id]:
    if id_ in registro_curriculos and id_ not in curriculos_comparacao:
        curriculos_comparacao.append(id_)
modo_multicurso = "principal" if len(curriculos_comparacao) == 1 else (
    "maximizar_sobreposicao" if objetivo_trajetoria in {"dupla", "tripla"} else "comparar"
)
modo_multicurso_label = {
    "principal": "Curso único",
    "comparar": "Comparação de trajetórias",
    "maximizar_sobreposicao": "Maximizar aproveitamento conjunto",
}[modo_multicurso]

_, curriculo, _, _ = resolver_curriculo(BASE, registro_curriculos[curriculo_principal_id])
rotulos_disciplinas = {
    f"Q{d.quadrimestre_recomendado or '?'} · {d.codigo} — {d.nome}": d.codigo
    for d in sorted(curriculo.values(), key=lambda x: (x.quadrimestre_recomendado or 99, x.nome))
}
rotulo_por_codigo = {codigo: rotulo for rotulo, codigo in rotulos_disciplinas.items()}

with st.sidebar:
    st.header("Arquivos")
    st.caption("Os arquivos são processados localmente no seu computador.")
    upload_historico = st.file_uploader("Histórico do SIGAA (PDF)", type=["pdf"])
    upload_ofertas = st.file_uploader("Turmas ofertadas (Excel)", type=["xlsx", "xls"])
    uploads_historicos = st.file_uploader(
        "Ofertas de quadrimestres anteriores (opcional)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
    )

    if upload_historico:
        caminho_historico = salvar_upload(upload_historico, ENTRADAS / "historico_interface.pdf")
    else:
        caminho_historico = localizar_padrao("historico_sigaa.pdf")

    if upload_ofertas:
        caminho_ofertas = salvar_upload(upload_ofertas, ENTRADAS / "ofertas_interface.xlsx")
    else:
        caminho_ofertas = localizar_padrao("matriculas_2026_3_turmas_ofertadas.xlsx")

    caminhos_historicos: list[Path] = []
    for indice, arquivo in enumerate(uploads_historicos or []):
        destino = ENTRADAS / f"oferta_historica_{indice + 1}_{arquivo.name}"
        caminhos_historicos.append(salvar_upload(arquivo, destino))

    st.divider()
    st.write("**Plano ativo**")
    st.write(f"🎯 {rotulos_curriculos[curriculo_principal_id]}")
    if len(ordem_trajetoria) > 1:
        for id_ in ordem_trajetoria[1:]:
            st.write(f"＋ {rotulos_curriculos[id_]}")
    st.caption(f"Estratégia: {estrategia_trajetoria} · ritmo: {int(ritmo_formatura)} cr/quad")
    st.divider()
    st.write("**Status dos arquivos**")
    st.write("✅ Histórico encontrado" if caminho_historico.exists() else "⚠️ Envie o histórico")
    st.write("✅ Oferta encontrada" if caminho_ofertas.exists() else "⚠️ Envie a oferta")

abas = st.tabs([
    "1. Minha trajetória",
    "2. Período e carga",
    "3. Rotina e horários",
    "4. Disciplinas e docentes",
    "5. Avaliações UFABC Next",
    "6. Preferências acadêmicas",
    "7. Gerar planejamento",
    "8. Ajustar grade",
])

with abas[0]:
    st.subheader("Minha trajetória acadêmica")
    st.markdown(
        "<div class='info-box'><strong>Esta análise é diferente da montagem da grade.</strong> "
        "Ela usa seu histórico e os PPCs para comparar mudança de curso, dupla ou tríplice formação, "
        "descontando disciplinas compartilhadas e respeitando trabalho final, estágio e curso-base. "
        "Depois da matrícula, o sistema também destaca a <strong>Grade com maior aproveitamento conjunto</strong> e separa os créditos usados na projeção do <strong>Total oficial informado no PPC</strong>.</div>",
        unsafe_allow_html=True,
    )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Curso atual", rotulos_curriculos[curso_atual_id])
    a2.metric("Primeira prioridade", rotulos_curriculos[curriculo_principal_id])
    a3.metric("Formações no plano", len(ordem_trajetoria))
    a4.metric("Estratégia", estrategia_trajetoria.title())

    st.markdown("### Situação dos estágios obrigatórios")
    status_estagio_rotulos_multi = {
        "Não iniciado / não contabilizar": "nao_iniciado",
        "Em andamento — considerar cumprido na projeção": "em_andamento",
        "Concluído ou já validado": "concluido",
    }
    estagios_status_ui = {}
    cursos_status = list(dict.fromkeys([*curriculos_comparacao, *ordem_trajetoria]))
    cursos_com_estagio = [id_ for id_ in cursos_status if registro_curriculos[id_].estagio_codigo]
    if not cursos_com_estagio:
        st.caption("Nenhuma das formações deste cenário possui estágio obrigatório cadastrado.")
    else:
        colunas = st.columns(min(3, len(cursos_com_estagio)))
        base_status = config_base.get("estagios_status", {})
        for indice, id_ in enumerate(cursos_com_estagio):
            atual = base_status.get(id_, config_base.get("estagio_status", "nao_iniciado") if id_ == curriculo_principal_id else "nao_iniciado")
            opcoes = list(status_estagio_rotulos_multi)
            idx = next((i for i, r in enumerate(opcoes) if status_estagio_rotulos_multi[r] == atual), 0)
            label = colunas[indice % len(colunas)].selectbox(
                rotulos_curriculos[id_], opcoes, index=idx, key=f"estagio_multi_{id_}"
            )
            estagios_status_ui[id_] = status_estagio_rotulos_multi[label]
    for id_ in curriculos_comparacao:
        estagios_status_ui.setdefault(id_, "nao_iniciado")

    assinatura_trajetoria = json.dumps({
        "curso_atual": curso_atual_id,
        "ordem": ordem_trajetoria,
        "estrategia": estrategia_trajetoria,
        "periodo": periodo_trajetoria,
        "ritmo": int(ritmo_formatura),
        "margem": int(margem_formatura),
        "projecao": modo_projecao_trajetoria,
        "estagios": estagios_status_ui,
    }, sort_keys=True, ensure_ascii=False)

    pode_analisar_traj = caminho_historico.exists() and bool(ordem_trajetoria)
    if not caminho_historico.exists():
        st.warning("Envie o histórico na barra lateral para calcular a trajetória.")
    if st.button(
        "Analisar minha trajetória agora",
        type="primary",
        use_container_width=True,
        disabled=not pode_analisar_traj,
        key="analisar_trajetoria_preliminar",
    ):
        try:
            registros_traj, convalidacoes_traj, resumo_hist_traj = ler_historico_sigaa(caminho_historico)
            q_traj = estimar_quadrimestre_planejado(
                resumo_hist_traj.periodo_inicial, periodo_trajetoria, None
            )
            ids_analise = []
            for id_ in [curso_atual_id, *ordem_trajetoria]:
                if id_ not in ids_analise:
                    ids_analise.append(id_)
            comparacoes_traj = comparar_curriculos(
                base=BASE, ids=ids_analise, registro_curriculos=registro_curriculos,
                registros_historico=registros_traj, convalidacoes_historico=convalidacoes_traj,
                resumo_historico=resumo_hist_traj, modo_projecao=modo_projecao_trajetoria,
                codigos_personalizados=[], estagios_status=estagios_status_ui, grade=None,
                curriculo_origem=None, periodo_planejamento=periodo_trajetoria,
                ritmo=int(ritmo_formatura), margem=int(margem_formatura),
                quadrimestre_planejado=q_traj,
            )
            por_id_traj = {x["id"]: x for x in comparacoes_traj}
            plano_traj = construir_plano_trajetoria(
                base=BASE,
                comparacoes=[por_id_traj[x] for x in ordem_trajetoria if x in por_id_traj],
                registro_curriculos=registro_curriculos, ordem_ids=ordem_trajetoria,
                periodo_planejamento=periodo_trajetoria, ritmo=int(ritmo_formatura),
                margem=int(margem_formatura), estrategia=estrategia_trajetoria,
                curso_atual_id=curso_atual_id, ofertas_historicas=len(caminhos_historicos),
            )
            cenarios_traj = gerar_cenarios_trajetoria(
                base=BASE, comparacoes=comparacoes_traj, registro_curriculos=registro_curriculos,
                curso_atual_id=curso_atual_id, alvo_ids=ordem_trajetoria,
                periodo_planejamento=periodo_trajetoria, ritmo=int(ritmo_formatura),
                margem=int(margem_formatura), estrategia=estrategia_trajetoria,
                ofertas_historicas=len(caminhos_historicos),
            )
            rel_traj = BASE / "saidas" / "relatorio_trajetoria_preliminar.html"
            rel_traj.parent.mkdir(exist_ok=True)
            gerar_relatorio_trajetoria_html(rel_traj, plano_traj, cenarios_traj)
            st.session_state["analise_trajetoria_preliminar"] = {
                "assinatura": assinatura_trajetoria,
                "plano": plano_traj,
                "cenarios": cenarios_traj,
                "relatorio": str(rel_traj),
            }
            st.success("Trajetória calculada. A análise será refinada depois que você escolher uma grade para o próximo quadrimestre.")
        except Exception as erro:
            st.exception(erro)

    plano_exibir = None
    cenarios_exibir = None
    relatorio_exibir = None

    # O resultado completo, após gerar a matrícula, incorpora a grade escolhida.
    if "resultado_paths" in st.session_state:
        resumo_path = Path(st.session_state["resultado_paths"][2])
        if resumo_path.exists():
            resumo_full = json.loads(resumo_path.read_text(encoding="utf-8"))
            config_full = resumo_full.get("configuracao_efetiva", {}).get("trajetoria", {})
            config_efetiva_full = resumo_full.get("configuracao_efetiva", {})
            if (
                config_full.get("ordem_ids") == ordem_trajetoria
                and config_full.get("estrategia") == estrategia_trajetoria
                and config_full.get("curso_atual_id") == curso_atual_id
                and resumo_full.get("periodo_planejamento") == periodo_trajetoria
                and int(config_efetiva_full.get("creditos_futuros_por_quadrimestre", -1)) == int(ritmo_formatura)
                and int(config_efetiva_full.get("margem_formatura_quadrimestres", -1)) == int(margem_formatura)
            ):
                plano_exibir = resumo_full.get("plano_trajetoria") or None
                cenarios_exibir = resumo_full.get("cenarios_trajetoria") or []
                contexto_full = st.session_state.get("contexto_editor", {})
                caminho_rel_full = contexto_full.get("relatorio_trajetoria")
                if caminho_rel_full:
                    relatorio_exibir = Path(caminho_rel_full)

    preliminar = st.session_state.get("analise_trajetoria_preliminar")
    if plano_exibir is None and preliminar and preliminar.get("assinatura") == assinatura_trajetoria:
        plano_exibir = preliminar.get("plano")
        cenarios_exibir = preliminar.get("cenarios", [])
        relatorio_exibir = Path(preliminar["relatorio"]) if preliminar.get("relatorio") else None

    if plano_exibir:
        st.divider()
        renderizar_plano_trajetoria(plano_exibir, cenarios_exibir, relatorio_exibir)
    else:
        st.markdown(
            "<div class='info-box'><strong>O que você verá:</strong> data estimada de cada diploma, "
            "prazo para concluir todas as formações, créditos únicos restantes, economia por sobreposição, "
            "disciplinas estratégicas compartilhadas e um roteiro aproximado por quadrimestre.</div>",
            unsafe_allow_html=True,
        )

with abas[1]:
    st.subheader("Período e carga acadêmica")
    col1, col2, col3 = st.columns(3)
    with col1:
        periodo = periodo_trajetoria
        st.metric("Quadrimestre de planejamento", periodo)
        st.caption("Altere o período no painel de trajetória no início da página.")
        campus = st.selectbox("Campus", options=["SA", "SBC"], index=0 if config_base.get("campus", "SA") == "SA" else 1)
    with col2:
        turno = st.selectbox("Turno", options=["Noturno", "Matutino", "Vespertino", "Integral"], index=0)
        quadrimestre_manual = st.number_input("Quadrimestre aproximado no PPC (opcional)", min_value=1, max_value=30, value=None, placeholder="Automático")
    with col3:
        top_n = st.number_input("Quantidade de grades padrão", min_value=3, max_value=10, value=int(config_base.get("top_n", 5)))
        incluir_ol = st.toggle("Incluir opções limitadas na busca", value=bool(config_base.get("incluir_opcao_limitada", True)))

    c1, c2, c3, c4 = st.columns(4)
    min_creditos = c1.number_input("Créditos mínimos", min_value=4, max_value=30, value=int(config_base.get("min_creditos", 14)))
    alvo_creditos = c2.number_input("Carga-alvo", min_value=4, max_value=30, value=int(config_base.get("creditos_alvo", 16)))
    max_creditos = c3.number_input("Créditos máximos", min_value=4, max_value=32, value=int(config_base.get("max_creditos", 20)))
    min_flex = c4.number_input("Mínimo flexível", min_value=4, max_value=30, value=int(config_base.get("min_creditos_flexivel", 12)))

    st.subheader("Projeção das disciplinas em andamento")
    modo_projecao_label = st.radio(
        "Como tratar as disciplinas do quadrimestre atual na montagem da grade?",
        ["Otimista — assumir aprovação em todas", "Conservador — não assumir aprovação", "Personalizado"],
        index=0 if modo_projecao_trajetoria == "todas" else 1,
        horizontal=True,
    )
    modo_map = {
        "Otimista — assumir aprovação em todas": "todas",
        "Conservador — não assumir aprovação": "nenhuma",
        "Personalizado": "personalizada",
    }
    modo_projecao = modo_map[modo_projecao_label]
    andamento = em_andamento_historico(caminho_historico)
    andamento_map = {f"{codigo} — {nome}": codigo for codigo, nome in andamento}
    selecionadas_andamento: list[str] = []
    if modo_projecao == "personalizada":
        escolhidas = st.multiselect(
            "Quais disciplinas em andamento devem ser presumidas como aprovadas?",
            options=list(andamento_map),
        )
        selecionadas_andamento = [andamento_map[x] for x in escolhidas]
    elif andamento:
        with st.expander("Disciplinas em andamento identificadas"):
            for codigo, nome in andamento:
                st.write(f"- **{codigo}** — {nome}")

    projecoes_cumpridas = st.toggle(
        "No cenário otimista/personalizado, tratar as aprovações presumidas como recomendações cumpridas",
        value=True,
        help=(
            "Quando ativado, uma disciplina em andamento que foi presumida aprovada não recebe penalidade no ranking. "
            "Ela continua identificada no relatório como dependência baseada em projeção."
        ),
    )


    with st.expander("Configurações avançadas da busca"):
        st.caption(
            "O limite de candidatas controla quantas disciplinas ofertadas entram na enumeração. "
            "Quanto maior, mais abrangente e potencialmente mais lenta será a busca. O limite de retenção "
            "não interrompe o Top 5: ele limita apenas quantas grades ficam guardadas para a fronteira de Pareto e apresentação."
        )
        busca1, busca2 = st.columns(2)
        max_disciplinas_candidatas_ui = busca1.number_input(
            "Máximo de disciplinas candidatas",
            min_value=8,
            max_value=50,
            value=int(config_base.get("max_disciplinas_candidatas", 24)),
            step=1,
            help=(
                "Se a oferta tiver mais candidatas do que este valor, o relatório avisará que a garantia global ficou limitada. "
                "Para comparar currículos muito flexíveis, como o BC&T, pode ser útil aumentar este número."
            ),
        )
        max_solucoes_pool_ui = busca2.number_input(
            "Grades retidas para Pareto e exploração visual",
            min_value=100,
            max_value=50000,
            value=int(config_base.get("max_solucoes_pool", 5000)),
            step=100,
            help=(
                "As grades padrão e os perfis são ordenados usando todas as combinações analisadas. "
                "Este limite afeta somente a retenção do conjunto usado na fronteira de Pareto."
            ),
        )

with abas[2]:
    st.subheader("Restrições de rotina")
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado"]
    c1, c2 = st.columns(2)
    dias_indisponiveis = c1.multiselect("Dias em que você não pode ter aula", dias)
    dias_preferidos_livres = c2.multiselect("Dias que você prefere deixar livres", dias)

    c3, c4 = st.columns(2)
    horario_mais_cedo = c3.time_input("Horário mais cedo permitido", value=time(19, 0), step=1800)
    horario_mais_tarde = c4.time_input("Horário mais tarde permitido", value=time(23, 0), step=1800)

    c5, c6, c7 = st.columns(3)
    max_dias_preferido = c5.selectbox("Máximo de dias preferido", ["Sem preferência", 3, 4, 5, 6], index=0)
    max_praticas_rigido = c6.selectbox("Máximo rígido de disciplinas práticas", ["Sem limite", 1, 2, 3, 4], index=0)
    max_praticas_preferido = c7.selectbox("Máximo preferido de práticas", ["Sem preferência", 1, 2, 3, 4], index=0)

    c8, c9 = st.columns(2)
    max_carga_individual = c8.selectbox("Carga individual máxima preferida", ["Sem preferência", 12, 16, 18, 20, 24, 28], index=0)
    incluir_especiais = c9.toggle("Permitir Engenharia Unificada/TG/Estágio na grade regular", value=False)

with abas[3]:
    st.subheader("Disciplinas obrigatórias e proibidas")
    c1, c2 = st.columns(2)
    obrigatorias_rotulos = c1.multiselect("Disciplinas que precisam aparecer na grade", options=list(rotulos_disciplinas))
    proibidas_rotulos = c2.multiselect("Disciplinas que não devem aparecer", options=list(rotulos_disciplinas))

    docentes_oferta = extrair_docentes(caminho_ofertas)
    defaults_bloqueados = [normalizar_texto(x) for x in config_base.get("professores_bloqueados", [])]
    opcoes_docentes = sorted(set(docentes_oferta) | set(defaults_bloqueados))
    st.subheader("Docentes")
    c3, c4, c5 = st.columns(3)
    bloqueados = c3.multiselect("Bloquear completamente", opcoes_docentes, default=[x for x in defaults_bloqueados if x in opcoes_docentes])
    preferidos = c4.multiselect("Docentes preferidos", opcoes_docentes)
    evitar = c5.multiselect("Preferir evitar, sem bloquear", opcoes_docentes)

    st.caption("Nomes que não aparecem na planilha podem ser incluídos manualmente, um por linha.")
    manual_bloqueados = st.text_area("Docentes bloqueados adicionais", height=90)

with abas[4]:
    st.subheader("Avaliações docentes — UFABC Next")
    st.markdown(
        "<div class='info-box'><strong>Como funciona:</strong> o sistema usa a avaliação da disciplina específica quando disponível, "
        "separa qualidade pedagógica de risco acadêmico e aplica apenas uma preferência flexível no ranking. "
        "Uma turma importante nunca é bloqueada automaticamente.</div>",
        unsafe_allow_html=True,
    )

    avaliacoes_cfg_base = config_base.get("avaliacoes_docentes", {})
    caminho_avaliacoes = BASE / str(avaliacoes_cfg_base.get("arquivo", "dados/avaliacoes_docentes.json"))
    upload_avaliacoes = st.file_uploader(
        "Importar avaliações já coletadas (JSON)",
        type=["json"],
        help="Use o arquivo avaliacoes_docentes_compartilhavel.json gerado pelo coletor.",
    )
    if upload_avaliacoes:
        caminho_avaliacoes = salvar_upload(upload_avaliacoes, BASE / "dados" / "avaliacoes_docentes.json")
        st.success("Arquivo de avaliações importado.")

    c1, c2, c3 = st.columns(3)
    considerar_avaliacoes_docentes = c1.toggle(
        "Considerar avaliações no ranking",
        value=bool(avaliacoes_cfg_base.get("habilitado", True)),
    )
    importancia_label = c2.selectbox(
        "Importância no ranking",
        ["Não considerar", "Baixa", "Média", "Alta"],
        index={"nao_considerar": 0, "baixa": 1, "media": 2, "alta": 3}.get(
            str(avaliacoes_cfg_base.get("importancia", "media")), 2
        ),
        help="A progressão curricular continua mais importante. Este controle ajusta apenas o peso relativo entre grades semelhantes.",
    )
    usar_especifica = c3.toggle(
        "Priorizar avaliação da disciplina específica",
        value=bool(avaliacoes_cfg_base.get("usar_avaliacao_especifica", True)),
    )
    importancia_map = {
        "Não considerar": "nao_considerar",
        "Baixa": "baixa",
        "Média": "media",
        "Alta": "alta",
    }
    importancia_avaliacoes = importancia_map[importancia_label]

    a1, a2 = st.columns(2)
    minimo_conceitos_docentes = a1.number_input(
        "Amostra mínima de conceitos",
        min_value=0,
        max_value=500,
        value=int(avaliacoes_cfg_base.get("minimo_conceitos", 10)),
        help="Abaixo deste valor, o efeito no ranking é reduzido automaticamente.",
    )
    minimo_comentarios_docentes = a2.number_input(
        "Amostra mínima de comentários",
        min_value=0,
        max_value=100,
        value=int(avaliacoes_cfg_base.get("minimo_comentarios", 3)),
        help="Abaixo deste valor, o efeito no ranking é reduzido automaticamente.",
    )

    st.markdown("#### Atualização automática")
    st.caption(
        "O Edge será aberto. Faça login institucional e deixe a página Reviews aberta; depois disso a coleta é automática. "
        "A senha e o token não são gravados nos relatórios."
    )
    sessao_next = BASE / "dados" / "sessao_ufabc_next"
    b_atualizar, b_limpar = st.columns([3, 1])
    if b_limpar.button("Limpar sessão", use_container_width=True, help="Apaga apenas a sessão local autenticada do Edge."):
        if sessao_next.exists():
            shutil.rmtree(sessao_next, ignore_errors=True)
            st.success("Sessão local do UFABC Next apagada.")
        else:
            st.info("Nenhuma sessão local estava salva.")

    if b_atualizar.button("Atualizar avaliações dos docentes das ofertas", use_container_width=True):
        if not caminho_ofertas.exists():
            st.error("Envie primeiro a planilha de ofertas.")
        else:
            try:
                aliases_atualizacao = carregar_aliases_oferta(BASE / config_base["arquivo_aliases_oferta"])
                ofertas_atualizacao = ler_ofertas(
                    caminho_ofertas,
                    codigos_curriculo=set(curriculo),
                    nomes_curriculo={c: d.nome for c, d in curriculo.items()},
                    aliases_oferta=aliases_atualizacao,
                    campus=campus,
                    turno=turno,
                    professores_bloqueados=set(),
                )
                consultas_csv = BASE / "dados" / "consultas_ufabc_next.csv"
                codigos_permitidos = None
                if caminho_historico.exists():
                    try:
                        equivalencias, equivalencias_compostas = carregar_equivalencias(
                            BASE / config_base["arquivo_equivalencias"]
                        )
                        registros_hist, convalidacoes_hist, resumo_hist = ler_historico_sigaa(caminho_historico)
                        situacao_coleta = consolidar_historico(
                            registros_hist, equivalencias, equivalencias_compostas,
                            convalidacoes_hist, resumo_hist,
                        )
                        cumpridas_coleta = situacao_coleta.codigos_projetados(
                            modo_projecao, selecionadas_andamento
                        )
                        codigos_permitidos = set(curriculo) - set(cumpridas_coleta)
                    except Exception:
                        codigos_permitidos = None
                quantidade_consultas = gerar_consultas_csv(
                    consultas_csv,
                    ofertas_atualizacao.ofertas,
                    curriculo,
                    codigos_permitidos=codigos_permitidos,
                )
                if quantidade_consultas == 0:
                    st.warning("Nenhum par professor–disciplina foi encontrado nas ofertas atuais.")
                else:
                    script = BASE / "ferramentas" / "coletar_avaliacoes_ufabc_next.py"
                    comando = [
                        sys.executable,
                        str(script),
                        "--config", str(BASE / "config" / "ufabc_next.json"),
                        "--consultas", str(consultas_csv),
                        "--saida-json", str(BASE / "dados" / "avaliacoes_docentes.json"),
                        "--saida-html", str(BASE / "saidas" / "relatorio_avaliacoes_docentes.html"),
                        "--saida-local", str(BASE / "saidas" / "avaliacoes_docentes_local_com_comentarios_NAO_COMPARTILHAR.json"),
                        "--sessao", str(BASE / "dados" / "sessao_ufabc_next"),
                    ]
                    with st.spinner(
                        f"Consultando {quantidade_consultas} combinações de docente e disciplina. Faça login na janela do Edge..."
                    ):
                        processo = subprocess.run(
                            comando,
                            cwd=BASE,
                            text=True,
                            capture_output=True,
                            timeout=1800,
                        )
                    if processo.returncode != 0:
                        st.error("A coleta não foi concluída.")
                        st.code((processo.stdout + "\n" + processo.stderr)[-5000:])
                    else:
                        caminho_avaliacoes = BASE / "dados" / "avaliacoes_docentes.json"
                        st.success(f"Avaliações atualizadas para {quantidade_consultas} combinações.")
                        st.session_state["avaliacoes_atualizadas"] = True
            except subprocess.TimeoutExpired:
                st.error("A coleta excedeu 30 minutos e foi interrompida.")
            except Exception as erro:
                st.exception(erro)

    if caminho_avaliacoes.exists():
        base_preview = carregar_avaliacoes_docentes(
            caminho_avaliacoes,
            habilitado=True,
            importancia=importancia_avaliacoes,
            minimo_conceitos=int(minimo_conceitos_docentes),
            minimo_comentarios=int(minimo_comentarios_docentes),
            usar_avaliacao_especifica=usar_especifica,
        )
        registros_preview = resumo_avaliacoes(base_preview)
        p1, p2, p3 = st.columns(3)
        p1.metric("Avaliações carregadas", len(registros_preview))
        p2.metric("Gerado em", base_preview.gerado_em_utc[:10] if base_preview.gerado_em_utc else "—")
        p3.metric("Avisos", len(base_preview.avisos))
        if registros_preview:
            df_preview = pd.DataFrame([
                {
                    "Professor": r["professor"],
                    "Fonte": "Disciplina" if r["fonte"] == "disciplina" else "Geral",
                    "Disciplina": r["codigo_disciplina"] or "Geral",
                    "Classificação": r["classificacao"],
                    "Qualidade": r["qualidade_pedagogica"],
                    "Risco": r["risco_academico"],
                    "Amostra": f"{r['conceitos']} conceitos / {r['comentarios']} comentários",
                    "Efeito": r["efeito_ranking_aplicado"],
                }
                for r in registros_preview
            ])
            st.dataframe(df_preview, use_container_width=True, hide_index=True)
        if base_preview.avisos:
            with st.expander("Avisos da leitura"):
                for aviso in base_preview.avisos:
                    st.write("- " + aviso)
        relatorio_docentes = BASE / "saidas" / "relatorio_avaliacoes_docentes.html"
        if relatorio_docentes.exists():
            st.download_button(
                "Baixar relatório das avaliações docentes",
                relatorio_docentes.read_bytes(),
                file_name="relatorio_avaliacoes_docentes.html",
                mime="text/html",
            )
    else:
        st.warning("Ainda não há um arquivo de avaliações docentes. Importe um JSON ou execute a atualização automática.")


with abas[5]:
    st.subheader("Perfil acadêmico")
    interesses = st.multiselect(
        "Áreas de interesse para opções limitadas",
        [
            "metais", "polimeros", "ceramicas", "nanomateriais", "energia_ambiente",
            "biomateriais", "computacional", "caracterizacao", "eletronicos", "software",
            "dados_ia", "redes_comunicacao", "sistemas_computacionais", "teoria_computacao",
            "seguranca", "multimidia", "generalista",
        ],
        help="Essas áreas só alteram a prioridade das opções limitadas; não eliminam disciplinas.",
    )
    c1, c2, c3 = st.columns(3)
    gerar_pareto = c1.toggle("Mostrar alternativas não dominadas", value=True)
    gerar_reservas = c2.toggle("Gerar grades de reserva", value=True)
    gerar_cenarios = c3.toggle("Comparar cenários de aprovação", value=True)
    c4, c5 = st.columns(2)
    gerar_multiquad = c4.toggle("Planejamento de próximos quadrimestres", value=True)
    horizonte = c5.slider("Horizonte de planejamento", min_value=1, max_value=6, value=3)

    st.subheader("Estimativa de formatura e desempenho")
    registro_principal_ui = registro_curriculos[curriculo_principal_id]
    estagio_status = estagios_status_ui.get(curriculo_principal_id, "nao_iniciado")
    if registro_principal_ui.estagio_codigo:
        st.caption(
            f"Estágio do curso principal: {dict((v, k) for k, v in status_estagio_rotulos_multi.items()).get(estagio_status, estagio_status)}. "
            "A situação de todos os cursos pode ser alterada na aba 1."
        )
    else:
        st.caption("O currículo principal selecionado não possui estágio obrigatório.")

    f1, f2, f3 = st.columns(3)
    f1.metric("Ritmo futuro da trajetória", f"{int(ritmo_formatura)} cr/quad")
    f2.metric("Margem prudente", f"{int(margem_formatura)} quad")
    gerar_desempenho = f3.toggle(
        "Gerar análise do histórico", value=bool(config_base.get("gerar_analise_desempenho", True)),
        help="Inclui aprovações, reprovações, conceitos, coeficientes e gráficos no relatório.",
    )
    st.caption("O ritmo e a margem podem ser alterados no painel de trajetória no início da página.")

with abas[6]:
    st.subheader("Gerar planejamento")
    st.markdown(
        "<div class='info-box'><strong>Antes de continuar:</strong> confira os arquivos na barra lateral. "
        f"O relatório separará os números oficiais do vínculo atual da estimativa para <strong>{rotulos_curriculos[curriculo_principal_id]}</strong>.</div>",
        unsafe_allow_html=True,
    )

    pode_gerar = caminho_historico.exists() and caminho_ofertas.exists()
    if not pode_gerar:
        st.warning("Envie o histórico e a planilha de ofertas para continuar.")

    if st.button("Gerar planejamento", type="primary", disabled=not pode_gerar, use_container_width=True):
        professores_extras = [normalizar_texto(x) for x in manual_bloqueados.splitlines() if x.strip()]
        config = dict(config_base)
        config.update({
            "arquivo_historico": path_relativo(caminho_historico),
            "arquivo_ofertas": path_relativo(caminho_ofertas),
            "arquivos_ofertas_historicas": [path_relativo(p) for p in caminhos_historicos],
            "arquivo_registro_curriculos": config_base.get("arquivo_registro_curriculos", "dados/registro_curriculos.json"),
            "curriculo_principal_id": curriculo_principal_id,
            "curriculos_comparacao": curriculos_comparacao if modo_multicurso != "principal" else [curriculo_principal_id],
            "modo_multicurso": modo_multicurso,
            "trajetoria": {
                "objetivo": objetivo_trajetoria,
                "curso_atual_id": curso_atual_id,
                "ordem_ids": ordem_trajetoria,
                "estrategia": estrategia_trajetoria,
                "gerar_relatorio": True,
            },
            "estagios_status": estagios_status_ui,
            "arquivo_curriculo": registro_curriculos[curriculo_principal_id].arquivo,
            "arquivo_equivalencias": registro_curriculos[curriculo_principal_id].equivalencias,
            "periodo_planejamento": periodo.strip(),
            "quadrimestre_planejado": int(quadrimestre_manual) if quadrimestre_manual is not None else None,
            "campus": campus,
            "turno": turno,
            "professores_bloqueados": sorted(set(bloqueados + professores_extras)),
            "min_creditos": int(min_creditos),
            "max_creditos": int(max_creditos),
            "creditos_alvo": int(alvo_creditos),
            "min_creditos_flexivel": int(min_flex),
            "top_n": int(top_n),
            "min_opcoes_padrao": 3,
            "max_disciplinas_candidatas": int(max_disciplinas_candidatas_ui),
            "max_solucoes_pool": int(max_solucoes_pool_ui),
            "projecao_em_andamento": modo_projecao,
            "disciplinas_em_andamento_assumidas_aprovadas": selecionadas_andamento,
            "incluir_opcao_limitada": incluir_ol,
            "gerar_fronteira_pareto": gerar_pareto,
            "gerar_grades_reserva": gerar_reservas,
            "gerar_cenarios_comparativos": gerar_cenarios,
            "gerar_planejamento_multiquadrimestral": gerar_multiquad,
            "horizonte_quadrimestres": int(horizonte),
            "creditos_futuros_por_quadrimestre": int(ritmo_formatura),
            "margem_formatura_quadrimestres": int(margem_formatura),
            "estagio_status": estagio_status,
            "gerar_analise_desempenho": bool(gerar_desempenho),
            "avaliacoes_docentes": {
                "habilitado": bool(considerar_avaliacoes_docentes),
                "arquivo": path_relativo(caminho_avaliacoes),
                "importancia": importancia_avaliacoes,
                "usar_avaliacao_especifica": bool(usar_especifica),
                "minimo_conceitos": int(minimo_conceitos_docentes),
                "minimo_comentarios": int(minimo_comentarios_docentes),
                "mostrar_no_relatorio": True,
            },
            "restricoes": {
                "dias_indisponiveis": dias_indisponiveis,
                "horario_mais_cedo": horario_mais_cedo.strftime("%H:%M"),
                "horario_mais_tarde": horario_mais_tarde.strftime("%H:%M"),
                "disciplinas_obrigatorias_na_grade": [rotulos_disciplinas[x] for x in obrigatorias_rotulos],
                "disciplinas_proibidas": [rotulos_disciplinas[x] for x in proibidas_rotulos],
                "max_disciplinas_praticas": None if max_praticas_rigido == "Sem limite" else int(max_praticas_rigido),
                "incluir_componentes_especiais_na_grade": incluir_especiais,
            },
            "preferencias": {
                "dias_preferidos_sem_aula": dias_preferidos_livres,
                "maximo_dias_preferido": None if max_dias_preferido == "Sem preferência" else int(max_dias_preferido),
                "max_carga_individual_preferida": None if max_carga_individual == "Sem preferência" else int(max_carga_individual),
                "max_disciplinas_praticas_preferida": None if max_praticas_preferido == "Sem preferência" else int(max_praticas_preferido),
                "professores_preferidos": preferidos,
                "professores_a_evitar": evitar,
                "interesses_formacao": interesses,
                "considerar_aprovacoes_projetadas_como_cumpridas": bool(projecoes_cumpridas),
            },
        })
        CONFIG_INTERFACE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            with st.spinner("Analisando histórico, matriz, turmas e combinações..."):
                txt_path, html_path, json_path, contexto_editor = executar(CONFIG_INTERFACE, retornar_contexto=True)
            st.session_state["resultado_paths"] = (str(txt_path), str(html_path), str(json_path))
            st.session_state["contexto_editor"] = contexto_editor
            st.session_state.pop("grade_editada_ofertas", None)
            st.session_state.pop("grade_editor_base", None)
            st.session_state["config_gerada"] = json.dumps(config, ensure_ascii=False, indent=2)
            st.success("Planejamento gerado com sucesso.")
        except Exception as erro:
            st.exception(erro)

    if "resultado_paths" in st.session_state:
        txt_path, html_path, json_path = map(Path, st.session_state["resultado_paths"])
        st.divider()
        st.subheader("Resultado")
        if json_path.exists():
            resumo = json.loads(json_path.read_text(encoding="utf-8"))
            auditoria = resumo.get("auditoria", {})
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Grades padrão", len(resumo.get("grades_padrao", [])))
            col2.metric("Obrigatórios reconhecidos", f"{auditoria.get('por_categoria', {}).get('obrigatoria', {}).get('integralizado_confirmado', 0)} cr")
            col3.metric("Livres estimados", f"{auditoria.get('por_categoria', {}).get('livre', {}).get('integralizado_estimado', 0)} cr")
            col4.metric("Quadrimestre aproximado", f"Q{resumo.get('quadrimestre_planejado', '?')}")
            validacao = resumo.get("validacao_busca", {})
            if validacao.get("busca_completa"):
                status_busca = "Completa"
                detalhe_busca = "todas as candidatas"
            else:
                status_busca = "Limitada"
                detalhe_busca = (
                    f"{validacao.get('disciplinas_analisadas', 0)}/"
                    f"{validacao.get('disciplinas_candidatas_encontradas', 0)} candidatas"
                )
            col5.metric("Cobertura da busca", status_busca, detalhe_busca)

            with st.expander("Certificado da busca e exatidão do ranking"):
                v1, v2, v3, v4 = st.columns(4)
                v1.metric(
                    "Ranking padrão",
                    "Exato" if validacao.get("ranking_padrao_exato") else "Parcial",
                    "entre as candidatas analisadas",
                )
                v2.metric(
                    "Pareto",
                    "Completo" if validacao.get("fronteira_pareto_completa") else "Parcial",
                    f"{validacao.get('conjuntos_retidos_no_pool', 0)} retidas",
                )
                v3.metric("Grades únicas", validacao.get("conjuntos_unicos_validos", 0))
                v4.metric("Nós visitados", validacao.get("nos_visitados", 0))
                if validacao.get("busca_completa"):
                    st.success("Todas as disciplinas candidatas foram incluídas. A garantia global do ranking está ativa.")
                else:
                    st.warning(
                        "O Top 5 é exato para o conjunto analisado, mas algumas disciplinas ofertadas ficaram fora. "
                        "Aumente o limite de candidatas em ‘Período e carga’ para ampliar a cobertura."
                    )
                if validacao.get("limite_pool_atingido"):
                    st.info(
                        "O limite de retenção foi atingido. Isso não altera as grades padrão; apenas torna a fronteira de Pareto parcial."
                    )
            comparacoes = resumo.get("comparacao_curriculos", [])
            if comparacoes:
                st.markdown("### Comparação de formação")
                linhas_multi = []
                for item in comparacoes:
                    est = item.get("estimativa_formatura", {})
                    linhas_multi.append({
                        "Curso": item.get("rotulo"),
                        "Conclusão estimada mínima": est.get("periodo_estimado_minimo"),
                        "Faixa prudente": est.get("periodo_estimado_prudente"),
                        "Quadrimestres": f"{est.get('quadrimestres_estimados_incluindo_atual','—')}–{est.get('quadrimestres_estimados_prudente','—')}",
                        "% estimado": est.get("percentual_conclusao", 0),
                        "Créditos da grade aproveitados": item.get("creditos_grade_aproveitados", 0),
                        "Créditos regulares pendentes": est.get("creditos_regulares_pendentes", 0),
                        "Curso-base considerado": est.get("curso_base_rotulo", "—"),
                    })
                st.dataframe(pd.DataFrame(linhas_multi), hide_index=True, use_container_width=True)
                melhor_multi = resumo.get("melhor_sobreposicao_multicurso")
                if melhor_multi and melhor_multi.get("assinatura"):
                    nomes_grade_multi = [curriculo[c].nome if c in curriculo else c for c in melhor_multi.get("assinatura", [])]
                    st.success(
                        "Maior sobreposição multicurso entre as grades padrão: "
                        + " + ".join(nomes_grade_multi)
                        + f". Aproveitamento somado: {melhor_multi.get('creditos_aproveitados_somados', 0)} cr "
                        + f"em {melhor_multi.get('cursos_impactados', 0)} trajetória(s)."
                    )

        d1, d2, d3, d4 = st.columns(4)
        if html_path.exists():
            d1.download_button("Baixar relatório HTML", html_path.read_bytes(), file_name="relatorio_planejamento.html", mime="text/html", use_container_width=True)
        if txt_path.exists():
            d2.download_button("Baixar relatório TXT", txt_path.read_bytes(), file_name="relatorio_planejamento.txt", mime="text/plain", use_container_width=True)
        if json_path.exists():
            d3.download_button("Baixar resumo JSON", json_path.read_bytes(), file_name="resultado_resumo.json", mime="application/json", use_container_width=True)
        d4.download_button("Salvar preferências", st.session_state.get("config_gerada", "{}"), file_name="minhas_preferencias.json", mime="application/json", use_container_width=True)

        if html_path.exists():
            st.iframe(html_path, height="content")

with abas[7]:
    st.subheader("Ajustar uma grade")
    st.markdown(
        "<div class='info-box'><strong>Editor interativo:</strong> escolha uma das grades geradas, "
        "remova disciplinas e veja somente turmas que podem ser adicionadas sem conflito e sem ultrapassar "
        "as restrições atuais. As métricas são recalculadas a cada alteração.</div>",
        unsafe_allow_html=True,
    )

    contexto = st.session_state.get("contexto_editor")
    if not contexto:
        st.info("Gere o planejamento na aba 6 antes de abrir o editor de grade.")
    else:
        resultado_editor = contexto["resultado"]
        grades_base = resultado_editor.grades_padrao
        curriculo_editor = contexto["curriculo"]
        ofertas_disponiveis = contexto["ofertas_disponiveis"]
        cumpridas_editor = contexto["cumpridas_projetadas"]
        concluidas_editor = contexto["concluidas_reais"]
        busca_editor = contexto["configuracao_busca"]

        if not grades_base:
            st.warning("Nenhuma grade padrão foi gerada para servir como base.")
        else:
            labels_base = [
                f"Opção {i + 1} · {g.metricas.creditos_totais} cr · "
                + " + ".join(o.codigo_curriculo for o in g.ofertas)
                for i, g in enumerate(grades_base)
            ]
            base_selecionada = st.selectbox(
                "Grade inicial",
                options=list(range(len(grades_base))),
                format_func=lambda i: labels_base[i],
                key="editor_grade_base_select",
            )

            if st.session_state.get("grade_editor_base") != base_selecionada:
                st.session_state["grade_editor_base"] = base_selecionada
                st.session_state["grade_editada_ofertas"] = tuple(grades_base[base_selecionada].ofertas)
                st.session_state["grade_editor_historico"] = []

            base_grade = grades_base[base_selecionada]
            ofertas_atuais = tuple(st.session_state.get("grade_editada_ofertas", base_grade.ofertas))

            controles1, controles2, controles3 = st.columns([1, 1, 3])
            if controles1.button("Restaurar grade-base", use_container_width=True):
                st.session_state["grade_editada_ofertas"] = tuple(base_grade.ofertas)
                st.session_state["grade_editor_historico"] = []
                st.rerun()
            historico_editor = st.session_state.get("grade_editor_historico", [])
            if controles2.button("Desfazer", disabled=not historico_editor, use_container_width=True):
                st.session_state["grade_editada_ofertas"] = historico_editor[-1]
                st.session_state["grade_editor_historico"] = historico_editor[:-1]
                st.rerun()
            controles3.caption(
                "O editor permite ficar temporariamente abaixo dos créditos mínimos para que você remova uma matéria e escolha outra no lugar."
            )

            try:
                grade_atual = montar_grade_personalizada(
                    ofertas_atuais,
                    curriculo_editor,
                    cumpridas_editor,
                    concluidas_editor,
                    busca_editor,
                )
            except Exception as erro:
                st.error(f"A grade personalizada ficou inválida: {erro}")
                grade_atual = base_grade
                ofertas_atuais = tuple(base_grade.ofertas)
                st.session_state["grade_editada_ofertas"] = ofertas_atuais

            m = grade_atual.metricas
            mb = base_grade.metricas
            st.markdown("### Grade atual")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Créditos", m.creditos_totais, delta=m.creditos_totais - mb.creditos_totais)
            c2.metric("Dias", m.dias_com_aula, delta=m.dias_com_aula - mb.dias_com_aula, delta_color="inverse")
            c3.metric("Janelas", f"{m.buracos_minutos} min", delta=f"{m.buracos_minutos - mb.buracos_minutos} min", delta_color="inverse")
            c4.metric("Carga total", m.carga_total_referencia, delta=m.carga_total_referencia - mb.carga_total_referencia, delta_color="inverse")
            c5.metric("Atraso recuperado", m.atraso_curricular_total, delta=m.atraso_curricular_total - mb.atraso_curricular_total)
            c6.metric("Ajuste docente", f"{m.ajuste_avaliacao_docente:+.1f}", delta=f"{m.ajuste_avaliacao_docente - mb.ajuste_avaliacao_docente:+.1f}")

            if m.creditos_totais < busca_editor.min_creditos:
                st.warning(
                    f"A grade está com {m.creditos_totais} créditos, abaixo do mínimo configurado de "
                    f"{busca_editor.min_creditos}. Adicione uma disciplina para completar a substituição."
                )
            if m.creditos_totais > busca_editor.creditos_alvo:
                st.caption(f"A grade está {m.creditos_totais - busca_editor.creditos_alvo} crédito(s) acima da carga-alvo.")
            elif m.creditos_totais < busca_editor.creditos_alvo:
                st.caption(f"Faltam {busca_editor.creditos_alvo - m.creditos_totais} crédito(s) para a carga-alvo.")
            else:
                st.success("A grade atinge exatamente a carga-alvo configurada.")

            exigidas_editor = set(busca_editor.restricoes.disciplinas_obrigatorias_na_grade)
            codigos_grade_atual = {o.codigo_curriculo for o in grade_atual.ofertas}
            exigidas_faltantes = exigidas_editor - codigos_grade_atual
            if exigidas_faltantes:
                st.error(
                    "A grade personalizada não contém disciplina(s) marcada(s) como obrigatória(s) na configuração: "
                    + ", ".join(sorted(exigidas_faltantes))
                )

            dataframe_grade = tabela_grade(grade_atual, curriculo_editor)
            if dataframe_grade.empty:
                st.info("A grade está vazia. Escolha uma disciplina compatível abaixo.")
            else:
                st.dataframe(dataframe_grade, hide_index=True, use_container_width=True)

            try:
                comparacao_editada = comparar_curriculos(
                    base=BASE,
                    ids=contexto.get("ids_comparacao", []),
                    registro_curriculos=contexto.get("registro_curriculos", {}),
                    registros_historico=contexto.get("registros_historico", []),
                    convalidacoes_historico=contexto.get("convalidacoes_historico", {}),
                    resumo_historico=contexto.get("resumo_historico"),
                    modo_projecao=modo_projecao,
                    codigos_personalizados=selecionadas_andamento,
                    estagios_status=contexto.get("estagios_status", {}),
                    grade=grade_atual,
                    curriculo_origem=curriculo_editor,
                    periodo_planejamento=contexto.get("periodo_planejamento", periodo),
                    ritmo=int(ritmo_formatura), margem=int(margem_formatura),
                    quadrimestre_planejado=contexto.get("quadrimestre_planejado"),
                )
                if comparacao_editada:
                    st.markdown("#### Impacto desta grade em cada curso")
                    st.dataframe(pd.DataFrame([{
                        "Curso": x["rotulo"],
                        "Créditos aproveitados nesta grade": x["creditos_grade_aproveitados"],
                        "% após a grade": x["estimativa_formatura"]["percentual_conclusao"],
                        "Conclusão mínima": x["estimativa_formatura"]["periodo_estimado_minimo"],
                        "Conclusão prudente": x["estimativa_formatura"]["periodo_estimado_prudente"],
                    } for x in comparacao_editada]), hide_index=True, use_container_width=True)
            except Exception as erro_multi:
                st.caption(f"Não foi possível recalcular o impacto multicurso desta edição: {erro_multi}")

            st.markdown("### 1. Remover disciplinas")
            opcoes_remocao = {
                f"{o.codigo_curriculo} — {curriculo_editor[o.codigo_curriculo].nome} · {o.creditos} cr": o.codigo_curriculo
                for o in grade_atual.ofertas
            }
            remover_rotulos = st.multiselect(
                "Selecione uma ou mais disciplinas para retirar",
                options=list(opcoes_remocao),
                key="editor_remover_multiselect",
            )
            if st.button(
                "Remover selecionadas",
                disabled=not remover_rotulos,
                key="editor_remover_botao",
                use_container_width=True,
            ):
                remover_codigos = {opcoes_remocao[x] for x in remover_rotulos}
                historico = list(st.session_state.get("grade_editor_historico", []))
                historico.append(tuple(grade_atual.ofertas))
                st.session_state["grade_editor_historico"] = historico
                st.session_state["grade_editada_ofertas"] = tuple(
                    o for o in grade_atual.ofertas if o.codigo_curriculo not in remover_codigos
                )
                st.rerun()

            st.markdown("### 2. Adicionar uma disciplina compatível")
            sugestoes = sugerir_adicoes_grade(
                grade_atual,
                ofertas_disponiveis,
                curriculo_editor,
                cumpridas_editor,
                concluidas_editor,
                busca_editor,
                limite=100,
            )

            if not sugestoes:
                st.warning(
                    "Nenhuma turma adicional cabe na grade atual. Remova uma disciplina, aumente o limite de créditos "
                    "ou altere as restrições de dias/horários."
                )
            else:
                filtro_tipo = st.radio(
                    "Mostrar sugestões",
                    ["Todas", "Somente obrigatórias", "Somente opção limitada"],
                    horizontal=True,
                    key="editor_filtro_tipo",
                )
                sugestoes_filtradas = []
                for sugestao in sugestoes:
                    categoria = curriculo_editor[sugestao.oferta.codigo_curriculo].categoria.value
                    if filtro_tipo == "Somente obrigatórias" and categoria != "obrigatoria":
                        continue
                    if filtro_tipo == "Somente opção limitada" and categoria != "opcao_limitada":
                        continue
                    sugestoes_filtradas.append(sugestao)

                linhas_sugestoes = []
                labels_sugestoes = []
                for indice, sugestao in enumerate(sugestoes_filtradas):
                    oferta = sugestao.oferta
                    disciplina = curriculo_editor[oferta.codigo_curriculo]
                    gm = sugestao.grade_resultante.metricas
                    avaliacoes = sugestao.grade_resultante.avaliacoes_docentes_por_disciplina.get(oferta.codigo_curriculo, ())
                    avaliacao = ", ".join(a.get("classificacao", "") for a in avaliacoes if a.get("classificacao")) or "Sem dados"
                    label = (
                        f"{oferta.codigo_curriculo} — {disciplina.nome} · {oferta.nome_turma} · "
                        f"{oferta.creditos} cr · total {gm.creditos_totais} cr"
                    )
                    labels_sugestoes.append(label)
                    linhas_sugestoes.append({
                        "Prioridade": indice + 1,
                        "Código": oferta.codigo_curriculo,
                        "Disciplina": disciplina.nome,
                        "PPC": f"Q{disciplina.quadrimestre_recomendado}" if disciplina.quadrimestre_recomendado else "—",
                        "Turma": oferta.nome_turma,
                        "Cr.": oferta.creditos,
                        "Total após adicionar": gm.creditos_totais,
                        "Dias": gm.dias_com_aula,
                        "Janelas": gm.buracos_minutos,
                        "Docente(s)": ", ".join(oferta.docentes) or "A definir",
                        "Avaliação": avaliacao,
                        "Horários": formatar_horarios_oferta(oferta),
                    })

                if linhas_sugestoes:
                    st.dataframe(pd.DataFrame(linhas_sugestoes), hide_index=True, use_container_width=True)
                    escolha_indice = st.selectbox(
                        "Turma a adicionar",
                        options=list(range(len(labels_sugestoes))),
                        format_func=lambda i: labels_sugestoes[i],
                        key="editor_adicao_select",
                    )
                    escolha = sugestoes_filtradas[escolha_indice]
                    if st.button("Adicionar turma selecionada", key="editor_adicionar_botao", use_container_width=True):
                        historico = list(st.session_state.get("grade_editor_historico", []))
                        historico.append(tuple(grade_atual.ofertas))
                        st.session_state["grade_editor_historico"] = historico
                        st.session_state["grade_editada_ofertas"] = tuple(escolha.grade_resultante.ofertas)
                        st.rerun()
                else:
                    st.info("Nenhuma sugestão corresponde ao filtro selecionado.")

            with st.expander("Por que outras disciplinas não podem ser adicionadas agora?"):
                diagnosticos_editor = diagnosticar_adicoes_grade(
                    grade_atual,
                    ofertas_disponiveis,
                    curriculo_editor,
                    cumpridas_editor,
                    busca_editor,
                )
                linhas_diag = []
                for codigo, motivos in diagnosticos_editor.items():
                    disciplina = curriculo_editor.get(codigo)
                    if disciplina is None:
                        continue
                    linhas_diag.append({
                        "Código": codigo,
                        "Disciplina": disciplina.nome,
                        "Motivo": "; ".join(motivos),
                    })
                if linhas_diag:
                    st.dataframe(pd.DataFrame(linhas_diag), hide_index=True, use_container_width=True, height=360)
                else:
                    st.write("Todas as disciplinas pendentes ofertadas possuem ao menos uma turma compatível.")

            st.markdown("### 3. Salvar grade personalizada")
            exportar1, exportar2 = st.columns(2)
            json_personalizado = grade_personalizada_json(grade_atual, curriculo_editor)
            html_personalizado = grade_personalizada_html(grade_atual, curriculo_editor)
            exportar1.download_button(
                "Baixar grade personalizada (JSON)",
                json_personalizado,
                file_name="grade_personalizada.json",
                mime="application/json",
                use_container_width=True,
            )
            exportar2.download_button(
                "Baixar grade personalizada (HTML)",
                html_personalizado,
                file_name="grade_personalizada.html",
                mime="text/html",
                use_container_width=True,
            )
