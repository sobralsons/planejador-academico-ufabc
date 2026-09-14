from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Camada visual opcional. O planejador continua funcional com componentes
# nativos caso alguma dependência de UI não esteja instalada.
try:
    import streamlit_shadcn_ui as ui
    SHADCN_AVAILABLE = True
except Exception:
    ui = None
    SHADCN_AVAILABLE = False

try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    AGGRID_AVAILABLE = True
except Exception:
    AgGrid = None
    GridOptionsBuilder = None
    AGGRID_AVAILABLE = False

try:
    from streamlit_sortables import sort_items
    SORTABLES_AVAILABLE = True
except Exception:
    sort_items = None
    SORTABLES_AVAILABLE = False

from main import executar
from planejador.sessao import ArquivosSessao
from planejador.avaliacoes_docentes import (
    carregar_avaliacoes_docentes,
    gerar_consultas_csv,
    resumo_avaliacoes,
)
from planejador.curriculo import carregar_aliases_oferta, carregar_curriculo, carregar_equivalencias
from planejador.academico import estimar_quadrimestre_planejado
from planejador.historico import STATUS_EM_ANDAMENTO, consolidar_historico, ler_historico_sigaa
from planejador.ofertas import extrair_docentes_arquivo, ler_ofertas
from planejador.modelos import Grade, Oferta
from planejador.multicurso import (
    carregar_registro_curriculos, comparar_curriculos, resolver_curriculo,
)
from planejador.planejador import (
    curriculo_com_componentes_matricula_atual,
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
if "arquivos_sessao" not in st.session_state:
    st.session_state["arquivos_sessao"] = ArquivosSessao()
ARQUIVOS_SESSAO = st.session_state["arquivos_sessao"]
CONFIG_INTERFACE = ARQUIVOS_SESSAO.configuracao
ENTRADAS = ARQUIVOS_SESSAO.entradas
SAIDAS = ARQUIVOS_SESSAO.saidas
DADOS_SESSAO = ARQUIVOS_SESSAO.dados

st.set_page_config(
    page_title="Planejador de Matrícula — UFABC",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
:root {
  --ufabc-green-950:#05584f;
  --ufabc-green-900:#076b60;
  --ufabc-green-800:#087f72;
  --ufabc-green-700:#15998a;
  --ufabc-green-600:#4fb1a4;
  --ufabc-green-100:#e5f5f2;
  --ufabc-green-050:#f6faf9;
  --ufabc-text:#17211c;
  --ufabc-muted:#66756e;
  --ufabc-border:#d9e4de;
  --ufabc-white:#ffffff;
}
[data-testid="stAppViewContainer"] { background:linear-gradient(180deg,#f7faf8 0,#f2f6f4 45%,#f7faf8 100%); }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,var(--ufabc-green-950),#123f31); border-right:1px solid #ffffff14; }
[data-testid="stSidebar"] * { color:#f7fbf8; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea { color:var(--ufabc-text) !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background:#ffffff10; border:1px dashed #ffffff45; border-radius:14px; }
.main .block-container { max-width:1380px; padding-top:1.35rem; padding-bottom:3rem; }
html, body, [class*="css"] { font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
h1,h2,h3 { letter-spacing:-.03em; color:var(--ufabc-text); }
h2 { margin-top:.35rem; }
p { line-height:1.55; }
.hero { position:relative; overflow:hidden; background:linear-gradient(135deg,#05766b 0%,#078579 58%,#14998a 100%); color:white; padding:30px 34px; border-radius:22px; margin-bottom:18px; box-shadow:0 14px 38px #05766b24; }
.hero:after { content:""; position:absolute; width:260px; height:260px; border-radius:50%; right:-85px; top:-120px; background:#ffffff0c; border:1px solid #ffffff17; }
.hero h1 { color:white; margin:0 0 8px; font-size:2.2rem; letter-spacing:-.035em; }
.hero p { margin:0; max-width:980px; color:#e8f3ee; font-size:1.02rem; }
.product-kicker { display:inline-flex; align-items:center; gap:7px; padding:5px 10px; border-radius:999px; background:#ffffff14; border:1px solid #ffffff20; font-size:.73rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px; }
.info-box { background:#fff; border:1px solid var(--ufabc-border); border-radius:16px; padding:17px 19px; margin:10px 0; box-shadow:0 5px 20px #173b2e09; }
[data-testid="stMetric"] { background:#fff; border:1px solid var(--ufabc-border); padding:15px 16px; border-radius:15px; box-shadow:0 6px 22px #173b2e09; }
[data-testid="stMetricLabel"] { color:var(--ufabc-muted); font-weight:700; }
[data-testid="stMetricValue"] { color:var(--ufabc-text); letter-spacing:-.035em; }
.stButton>button { background:var(--ufabc-green-800); color:white; border:1px solid var(--ufabc-green-800); border-radius:11px; font-weight:750; padding:.62rem 1.15rem; transition:all .16s ease; box-shadow:0 4px 12px #18513e18; }
.stButton>button:hover { background:var(--ufabc-green-700); color:white; border-color:var(--ufabc-green-700); transform:translateY(-1px); }
.stButton>button:focus { box-shadow:0 0 0 3px #287a5b28; }
.stDownloadButton>button { border-radius:11px; }
.small-note { color:var(--ufabc-muted); font-size:.91rem; }
.trajectory-builder { background:linear-gradient(135deg,#fff,#edf6f2); border:1px solid #cfe0d7; border-radius:20px; padding:21px 23px; margin:0 0 18px; box-shadow:0 10px 30px #153f3110; }
.trajectory-builder h2 { margin:2px 0 6px; }
.step-label { color:var(--ufabc-green-700); font-weight:850; font-size:.72rem; text-transform:uppercase; letter-spacing:.095em; margin-top:5px; }
.trajectory-summary { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:14px 0 20px; }
.trajectory-summary>div { background:white; border:1px solid var(--ufabc-border); border-radius:15px; padding:16px; box-shadow:0 5px 18px #173b2e08; }
.trajectory-summary span { display:block; color:var(--ufabc-muted); font-size:.76rem; text-transform:uppercase; font-weight:750; letter-spacing:.03em; }
.trajectory-summary strong { display:block; margin-top:5px; font-size:1.18rem; }
.path-card { background:#fff; border:1px solid var(--ufabc-border); border-radius:17px; padding:18px; height:100%; box-shadow:0 7px 20px #153f310d; }
.path-card .path-priority { color:var(--ufabc-green-700); font-size:.72rem; font-weight:850; text-transform:uppercase; letter-spacing:.05em; }
.path-card .path-date { font-size:1.4rem; font-weight:820; margin:8px 0 3px; }
.path-card .path-meta { color:#63746c; font-size:.88rem; margin-top:2px; }
.confidence-badge { display:inline-block; border-radius:999px; padding:5px 10px; background:#e8f3ed; color:#1f5b45; font-weight:800; font-size:.8rem; }
.ui-capabilities { display:flex; flex-wrap:wrap; gap:7px; margin:-7px 0 18px 2px; }
.ui-capability { display:inline-flex; align-items:center; gap:6px; padding:5px 9px; border-radius:999px; background:#fff; border:1px solid var(--ufabc-border); color:#496158; font-size:.75rem; font-weight:700; }
/* Tabs mais próximas de um wizard de produto */
.stTabs [data-baseweb="tab-list"] { gap:5px; background:#fff; border:1px solid var(--ufabc-border); border-radius:15px; padding:5px; box-shadow:0 5px 20px #173b2e08; overflow-x:auto; }
.stTabs [data-baseweb="tab"] { height:43px; border-radius:10px; padding:0 13px; white-space:nowrap; color:#52665d; font-weight:650; }
.stTabs [aria-selected="true"] { background:var(--ufabc-green-100) !important; color:var(--ufabc-green-900) !important; font-weight:800 !important; }
.stTabs [data-baseweb="tab-highlight"] { display:none; }
/* Inputs */
[data-baseweb="select"] > div, [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input, [data-testid="stTimeInput"] input, textarea { border-radius:11px !important; }
[data-testid="stExpander"] { border:1px solid var(--ufabc-border); border-radius:14px; background:#ffffffb8; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius:14px; overflow:hidden; }
.section-eyebrow { font-size:.72rem; text-transform:uppercase; letter-spacing:.09em; color:var(--ufabc-green-700); font-weight:850; margin-bottom:-5px; }

.app-summary-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:4px 0 18px; }
.app-summary-card { background:#fff; border:1px solid var(--ufabc-border); border-radius:20px; padding:17px 18px; box-shadow:0 7px 22px rgba(5,118,107,.08); }
.app-summary-card .icon { font-size:1.35rem; margin-bottom:8px; }
.app-summary-card span { display:block; color:#7a8984; font-size:.74rem; font-weight:750; text-transform:uppercase; letter-spacing:.045em; }
.app-summary-card strong { display:block; color:var(--ufabc-text); margin-top:4px; font-size:1rem; line-height:1.25; }
.app-summary-card small { display:block; color:#7b8b85; margin-top:5px; }
[data-testid="stExpander"] details summary { padding:.75rem .95rem; font-weight:750; }
[data-testid="stExpander"] details[open] { box-shadow:0 6px 24px rgba(5,118,107,.06); }
/* navegação curta: quatro áreas, não oito formulários */
.stTabs [data-baseweb="tab-list"] { position:sticky; top:.35rem; z-index:30; }
.stTabs [data-baseweb="tab"] { min-width:150px; justify-content:center; }
/* aparência mais próxima de app em telas pequenas */
@media(max-width:900px){
  .main .block-container { padding-left:.8rem; padding-right:.8rem; padding-top:.7rem; }
  .hero { border-radius:0 0 28px 28px; margin-left:-.8rem; margin-right:-.8rem; padding:24px 20px 28px; }
  .hero h1 { font-size:1.75rem; }
  .hero p { font-size:.92rem; }
  .ui-capabilities { display:none; }
  .app-summary-grid { grid-template-columns:repeat(2,1fr); gap:9px; }
  .app-summary-card { border-radius:17px; padding:14px; }
  .stTabs [data-baseweb="tab-list"] { gap:3px; border-radius:16px; padding:4px; }
  .stTabs [data-baseweb="tab"] { min-width:122px; padding:0 9px; font-size:.84rem; }
}
@media(max-width:900px){ .trajectory-summary { grid-template-columns:repeat(2,1fr); } .hero { padding:24px; } }
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
    return extrair_docentes_arquivo(caminho)


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




SORTABLE_STYLE = """
.sortable-component { background: transparent; padding: 2px 0; }
.sortable-container { background: transparent; }
.sortable-container-body { display:flex; gap:8px; flex-wrap:wrap; }
.sortable-item, .sortable-item:hover {
    background:#ffffff; color:#173f31; border:1px solid #d9e4de;
    border-radius:10px; padding:9px 12px; font-weight:700;
    box-shadow:0 3px 10px rgba(21,63,49,.07); cursor:grab;
}
"""


def metric_card(label: str, value, description: str | None = None, *, key: str | None = None) -> None:
    """Card de métrica moderno com fallback nativo."""
    if SHADCN_AVAILABLE:
        try:
            ui.metric_card(
                str(label),
                str(value),
                description=description or None,
                variant="dashboard",
                key=key,
            )
            return
        except Exception:
            pass
    st.metric(label, value, help=description)


def tabela_interativa(
    dados: pd.DataFrame,
    *,
    key: str,
    height: int = 330,
    filtros: bool = True,
) -> None:
    """Tabela de exploração com filtros/ordenação; usa st.dataframe como fallback."""
    if dados is None or dados.empty:
        st.caption("Nenhum registro para exibir.")
        return
    if AGGRID_AVAILABLE:
        try:
            builder = GridOptionsBuilder.from_dataframe(dados)
            builder.configure_default_column(
                sortable=True,
                filter=filtros,
                resizable=True,
                wrapText=True,
                autoHeight=True,
                minWidth=90,
            )
            builder.configure_grid_options(
                rowHeight=42,
                headerHeight=40,
                suppressRowHoverHighlight=False,
                animateRows=True,
            )
            AgGrid(
                dados,
                gridOptions=builder.build(),
                height=height,
                theme="streamlit",
                enable_enterprise_modules=False,
                allow_unsafe_jscode=False,
                key=key,
            )
            return
        except Exception:
            pass
    st.dataframe(dados, use_container_width=True, hide_index=True, height=height)


def ordenar_formacoes_adicionais(ids: list[str], rotulos: dict[str, str]) -> list[str]:
    """Permite reordenar apenas as prioridades 2 e 3, sem alterar a formação principal."""
    if len(ids) < 2 or not SORTABLES_AVAILABLE:
        return ids
    label_para_id = {rotulos[id_]: id_ for id_ in ids}
    try:
        ordenados = sort_items(
            list(label_para_id),
            header="Arraste para ordenar as formações adicionais",
            direction="horizontal",
            custom_style=SORTABLE_STYLE,
            key="traj_ordem_adicionais_sortable",
        )
        return [label_para_id[x] for x in ordenados if x in label_para_id]
    except Exception:
        return ids


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
            "Vagas remanescentes": oferta.vagas_remanescentes if oferta.vagas_remanescentes is not None else "—",
            "Alta demanda": "Sim" if oferta.alta_demanda else "Não" if oferta.origem_oferta == "ajuste" else "—",
            "Oferta vinculada a": oferta.curso_oferta or "—",
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
                "vagas_remanescentes": oferta.vagas_remanescentes,
                "alta_demanda": oferta.alta_demanda,
                "origem_oferta": oferta.origem_oferta,
                "curso_oferta": oferta.curso_oferta,
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
    if any(not c.get("conclusao_modelada", True) for c in plano.get("cursos", [])):
        st.warning("Há exigências sem prazo calculado ou tarefas fora do horizonte. A conclusão permanece indeterminada; confira as pendências de cada formação.")
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
        tabela_interativa(df_cenarios, key="grid_cenarios_trajetoria", height=290)

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
        b2.info("O relatório detalhado fica disponível para download. Os resultados principais são mostrados diretamente nesta tela, sem abrir outra página dentro do aplicativo.")


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
  <div class="product-kicker">Planejamento acadêmico inteligente</div>
  <h1>Planejador Acadêmico — UFABC</h1>
  <p>Veja sua trajetória, monte a próxima grade e faça ajustes sem precisar navegar por uma sequência de formulários.</p>
</div>
<div class="ui-capabilities">
  <span class="ui-capability">✓ histórico + PPC</span>
  <span class="ui-capability">✓ grades sem conflito</span>
  <span class="ui-capability">✓ cenários de trajetória</span>
  <span class="ui-capability">✓ ajuste de matrícula</span>
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

with st.expander("🎓 Formação e trajetória", expanded=False):
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

    # Na formação tripla, a ordem das formações adicionais é relevante para a trajetória.
    # O drag-and-drop atua somente nas prioridades 2 e 3 e nunca troca o curso principal sem intenção.
    adicionais_selecionados = ordenar_formacoes_adicionais(adicionais_selecionados, rotulos_curriculos)

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

with st.expander("📂 Dados e arquivos", expanded=False):
    st.markdown("#### Dados usados pelo planejador")
    st.caption("Carregue ou atualize os arquivos somente quando necessário. Eles são processados localmente no seu computador.")
    upload_historico = st.file_uploader("Histórico do SIGAA (PDF)", type=["pdf"])
    upload_ofertas = st.file_uploader("Turmas ofertadas — matrícula inicial (Excel)", type=["xlsx", "xls"])
    upload_ajuste = st.file_uploader(
        "Turmas para ajuste de matrícula (PDF, opcional)",
        type=["pdf"],
        help="Quando enviado, o PDF oficial é usado para novas inclusões no ajuste. O Excel inicial continua sendo usado para reconstruir as turmas em que você já está matriculado.",
    )
    uploads_historicos = st.file_uploader(
        "Ofertas de quadrimestres anteriores (opcional)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
    )

    if upload_historico:
        caminho_historico = salvar_upload(upload_historico, ENTRADAS / "historico_interface.pdf")
    else:
        caminho_historico = localizar_padrao("historico_sigaa.pdf")

    # Mantém as duas fontes separadas. No ajuste, o Excel da matrícula inicial
    # continua sendo necessário para reconstruir as turmas já matriculadas,
    # enquanto o PDF oficial informa as vagas remanescentes para novas inclusões.
    caminho_oferta_padrao = localizar_padrao("matriculas_2026_3_turmas_ofertadas.xlsx")
    caminho_ajuste_padrao = localizar_padrao("ajuste_matriculas_2026_3_turmas.pdf")

    if upload_ofertas:
        caminho_oferta_inicial = salvar_upload(upload_ofertas, ENTRADAS / "ofertas_interface.xlsx")
    else:
        caminho_oferta_inicial = caminho_oferta_padrao

    if upload_ajuste:
        caminho_ajuste = salvar_upload(upload_ajuste, ENTRADAS / "ajuste_matriculas_interface.pdf")
    else:
        caminho_ajuste = caminho_ajuste_padrao

    if caminho_ajuste.exists():
        caminho_ofertas = caminho_ajuste
        modo_ajuste_interface = True
    else:
        caminho_ofertas = caminho_oferta_inicial
        modo_ajuste_interface = False

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
    st.write("✅ Oferta inicial encontrada" if caminho_oferta_inicial.exists() else "⚠️ Envie a oferta inicial (Excel)")
    st.write("✅ PDF de ajuste encontrado" if caminho_ajuste.exists() else "➖ PDF de ajuste não enviado (opcional)")
    if modo_ajuste_interface:
        if caminho_oferta_inicial.exists():
            st.caption("Modo ajuste: sua matrícula atual vem do Excel inicial; novas sugestões vêm do PDF e exigem vagas remanescentes > 0.")
        else:
            st.caption("Modo ajuste: novas sugestões usam vagas remanescentes > 0. Para selecionar todas as turmas já matriculadas, envie também o Excel da matrícula inicial.")

st.markdown(
    f"""
    <div class="app-summary-grid">
      <div class="app-summary-card"><div class="icon">🎓</div><span>Formação principal</span><strong>{rotulos_curriculos[curriculo_principal_id]}</strong><small>{len(ordem_trajetoria)} formação(ões) no plano</small></div>
      <div class="app-summary-card"><div class="icon">📅</div><span>Quadrimestre</span><strong>{periodo_trajetoria}</strong><small>{int(ritmo_formatura)} créditos por quad.</small></div>
      <div class="app-summary-card"><div class="icon">📚</div><span>Dados acadêmicos</span><strong>{'Prontos' if caminho_historico.exists() and caminho_oferta_inicial.exists() else 'Atenção'}</strong><small>{'Histórico e oferta encontrados' if caminho_historico.exists() and caminho_oferta_inicial.exists() else 'Abra Dados e arquivos'}</small></div>
      <div class="app-summary-card"><div class="icon">🔄</div><span>Ajuste de matrícula</span><strong>{'Disponível' if caminho_ajuste.exists() else 'Opcional'}</strong><small>{'PDF de ajuste carregado' if caminho_ajuste.exists() else 'Adicione o PDF quando sair'}</small></div>
    </div>
    """,
    unsafe_allow_html=True,
)

abas = st.tabs([
    "🏠 Visão geral",
    "🧭 Planejar matrícula",
    "✨ Resultado",
    "🔄 Ajustar matrícula",
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
    with a1:
        metric_card("Curso atual", rotulos_curriculos[curso_atual_id], "Vínculo usado como referência", key="metric_curso_atual")
    with a2:
        metric_card("Primeira prioridade", rotulos_curriculos[curriculo_principal_id], "Primeiro diploma do plano", key="metric_primeira_prioridade")
    with a3:
        metric_card("Formações no plano", len(ordem_trajetoria), "Quantidade de matrizes comparadas", key="metric_formacoes")
    with a4:
        metric_card("Estratégia", estrategia_trajetoria.title(), "Como a trajetória será conciliada", key="metric_estrategia")

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
            rel_traj = SAIDAS / "relatorio_trajetoria_preliminar.html"
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
    with st.expander("1 · Período e carga", expanded=True):
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

with abas[1]:
    with st.expander("2 · Rotina e horários", expanded=False):
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

with abas[1]:
    with st.expander("3 · Disciplinas e docentes", expanded=False):
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

with abas[1]:
    with st.expander("4 · Avaliações UFABC Next", expanded=False):
        st.subheader("Avaliações docentes — UFABC Next")
        st.markdown(
            "<div class='info-box'><strong>Como funciona:</strong> a avaliação geral do docente é sempre a base. "
            "Quando existe avaliação da disciplina específica, o sistema combina as duas fontes (60% geral + 40% disciplina), "
            "mantendo qualidade pedagógica e risco acadêmico separados. O efeito continua sendo apenas uma preferência flexível no ranking.</div>",
            unsafe_allow_html=True,
        )

        avaliacoes_cfg_base = config_base.get("avaliacoes_docentes", {})
        caminho_avaliacoes = DADOS_SESSAO / "avaliacoes_docentes.json"
        if not caminho_avaliacoes.exists():
            caminho_avaliacoes = BASE / str(avaliacoes_cfg_base.get("arquivo", "dados/avaliacoes_docentes.json"))
        upload_avaliacoes = st.file_uploader(
            "Importar avaliações já coletadas (JSON)",
            type=["json"],
            help="Use o arquivo avaliacoes_docentes_compartilhavel.json gerado pelo coletor.",
        )
        if upload_avaliacoes:
            caminho_avaliacoes = salvar_upload(upload_avaliacoes, DADOS_SESSAO / "avaliacoes_docentes.json")
            st.success("Arquivo de avaliações importado.")

        c1, c2, c3 = st.columns(3)
        considerar_avaliacoes_docentes = c1.toggle(
            "Considerar avaliações no ranking",
            value=bool(avaliacoes_cfg_base.get("habilitado", False)),
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
            "Combinar avaliação geral + disciplina",
            value=bool(avaliacoes_cfg_base.get("usar_avaliacao_especifica", True)),
            help="Ligado: 60% da avaliação geral do docente + 40% da disciplina específica. Desligado: usa somente a avaliação geral.",
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
        sessao_next = DADOS_SESSAO / "sessao_ufabc_next"
        b_atualizar, b_limpar = st.columns([3, 1])
        if b_limpar.button("Limpar sessão", use_container_width=True, help="Apaga apenas a sessão local autenticada do Edge."):
            if sessao_next.exists():
                shutil.rmtree(sessao_next, ignore_errors=True)
                st.success("Sessão local do UFABC Next apagada.")
            else:
                st.info("Nenhuma sessão local estava salva.")

        if b_atualizar.button("Atualizar avaliações dos docentes das ofertas", use_container_width=True, disabled=not config_base.get("coleta_autenticada_habilitada", False)):
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
                    consultas_csv = DADOS_SESSAO / "consultas_ufabc_next.csv"
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
                            "--saida-json", str(DADOS_SESSAO / "avaliacoes_docentes.json"),
                            "--saida-html", str(SAIDAS / "relatorio_avaliacoes_docentes.html"),
                            "--saida-local", str(SAIDAS / "avaliacoes_docentes_local_com_comentarios_NAO_COMPARTILHAR.json"),
                            "--sessao", str(DADOS_SESSAO / "sessao_ufabc_next"),
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
                            caminho_avaliacoes = DADOS_SESSAO / "avaliacoes_docentes.json"
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
                tabela_interativa(df_preview, key="grid_avaliacoes_docentes", height=390)
            if base_preview.avisos:
                with st.expander("Avisos da leitura"):
                    for aviso in base_preview.avisos:
                        st.write("- " + aviso)
            relatorio_docentes = SAIDAS / "relatorio_avaliacoes_docentes.html"
            if relatorio_docentes.exists():
                st.download_button(
                    "Baixar relatório das avaliações docentes",
                    relatorio_docentes.read_bytes(),
                    file_name="relatorio_avaliacoes_docentes.html",
                    mime="text/html",
                )
        else:
            st.warning("Ainda não há um arquivo de avaliações docentes. Importe um JSON ou execute a atualização automática.")


with abas[1]:
    with st.expander("5 · Preferências acadêmicas", expanded=False):
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

with abas[2]:
    st.markdown("<div class='section-eyebrow'>Seu próximo quadrimestre</div>", unsafe_allow_html=True)
    st.subheader("Gerar e comparar grades")
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
            "arquivo_ofertas_inicial": path_relativo(caminho_oferta_inicial) if caminho_oferta_inicial.exists() else "",
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
                txt_path, html_path, json_path, contexto_editor = executar(CONFIG_INTERFACE, retornar_contexto=True, base_dados=BASE, diretorio_saidas=SAIDAS)
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
            for aviso in resumo.get("avisos", []):
                st.warning(aviso)
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
                    f"{validacao.get('pareto_quantidade_exibida', 0)} exibidas / {validacao.get('pareto_quantidade_retida', 0)} retidas",
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
                        "O limite do pool padrão foi atingido. Os rankings continuam exatos; a cobertura de Pareto é informada separadamente."
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
            st.caption("O relatório HTML detalhado está disponível no botão de download acima. A visualização no aplicativo permanece integrada a esta tela.")

with abas[3]:
    st.markdown("<div class='section-eyebrow'>Simulação interativa</div>", unsafe_allow_html=True)
    st.subheader("Ajustar matrícula")
    st.markdown(
        "<div class='info-box'><strong>Editor interativo:</strong> use uma grade gerada como base ou, no modo de ajuste, "
        "informe exatamente as turmas em que você já está matriculado. Você pode soltar disciplinas e testar novas turmas "
        "sem conflito. No PDF oficial de ajuste, novas adições só são sugeridas quando há vagas remanescentes.</div>",
        unsafe_allow_html=True,
    )

    contexto = st.session_state.get("contexto_editor")
    if not contexto:
        st.info("Gere o planejamento na aba 7 antes de abrir o ajuste de matrícula.")
    else:
        resultado_editor = contexto["resultado"]
        grades_base = list(resultado_editor.grades_padrao)
        curriculo_editor = contexto["curriculo"]
        ofertas_disponiveis = tuple(contexto["ofertas_disponiveis"])
        ofertas_todas = tuple(contexto.get("ofertas_todas", ofertas_disponiveis))
        ofertas_matricula_inicial = tuple(contexto.get("ofertas_matricula_inicial", ()))
        concluidas_editor = set(contexto["concluidas_reais"])
        busca_editor = contexto["configuracao_busca"]
        modo_ajuste_contexto = bool(contexto.get("modo_ajuste", False))
        curriculo_grade = curriculo_com_componentes_matricula_atual(
            curriculo_editor, ofertas_matricula_inicial if modo_ajuste_contexto else ()
        )

        # No ajuste, as matérias em que o aluno já está matriculado precisam ser
        # tratadas como parte da grade atual, e não como componentes já cumpridos.
        codigos_matricula_atual = set(st.session_state.get("ajuste_matricula_codigos", []))
        cumpridas_editor = set(contexto["cumpridas_projetadas"]) - codigos_matricula_atual
        grade_ajuste_base = None

        if modo_ajuste_contexto:
            st.success(
                "Modo de ajuste ativo. O PDF oficial foi reconhecido e o ranking usa as vagas remanescentes. "
                "Turmas com 0 vagas podem permanecer na sua matrícula atual, mas não aparecem como novas adições."
            )
            st.caption(
                "As vagas do PDF são uma fotografia do momento e aparecem vinculadas à linha/curso de oferta oficial. "
                "O planejador mostra essa origem para você conferir no SIGAA; a inclusão efetiva continua sujeita às regras e ao deferimento da UFABC."
            )
            st.markdown("### Minha matrícula atual")
            if ofertas_matricula_inicial:
                st.caption(
                    "Selecione as turmas em que você ficou matriculado após a matrícula comum. "
                    "A lista abaixo vem da planilha Excel da oferta inicial, mesmo quando essas turmas não aparecem no PDF de ajuste."
                )
                fonte_matricula = ofertas_matricula_inicial
            else:
                st.warning(
                    "O PDF de ajuste está ativo, mas a planilha Excel da matrícula inicial não foi encontrada. "
                    "A lista abaixo usa o PDF apenas como alternativa e pode não conter todas as turmas em que você já está matriculado."
                )
                fonte_matricula = ofertas_todas

            ofertas_ordenadas = sorted(
                fonte_matricula,
                key=lambda o: (
                    (curriculo_grade.get(o.codigo_curriculo).quadrimestre_recomendado if curriculo_grade.get(o.codigo_curriculo) else None) or 99,
                    o.codigo_curriculo,
                    o.nome_turma,
                ),
            )
            mapa_matricula = {}
            for oferta in ofertas_ordenadas:
                disciplina = curriculo_grade.get(oferta.codigo_curriculo)
                if disciplina is None:
                    continue
                if oferta.origem_oferta == "ajuste":
                    vagas_txt = "?" if oferta.vagas_remanescentes is None else str(oferta.vagas_remanescentes)
                    disponibilidade_txt = f" · remanescentes {vagas_txt}"
                    demanda_txt = " · alta demanda" if oferta.alta_demanda else ""
                else:
                    disponibilidade_txt = " · matrícula inicial"
                    demanda_txt = ""
                origem_txt = f" · oferta: {oferta.curso_oferta}" if oferta.curso_oferta else ""
                externa_txt = " · fora da matriz principal" if oferta.codigo_curriculo not in curriculo_editor else ""
                label = (
                    f"{oferta.codigo_turma} · {oferta.codigo_curriculo} — {disciplina.nome} · "
                    f"{oferta.nome_turma}{disponibilidade_txt}{demanda_txt}{externa_txt}{origem_txt}"
                )
                mapa_matricula[label] = oferta

            st.caption(
                f"{len(mapa_matricula)} turma(s) da oferta inicial disponíveis para seleção em {campus}/{turno}. "
                "Você pode pesquisar digitando o código exato da turma, por exemplo NA1ESTM004-17SA."
            )

            selecionadas_anteriores = set(st.session_state.get("ajuste_matricula_turmas", []))
            defaults_matricula = [
                label for label, oferta in mapa_matricula.items()
                if oferta.codigo_turma in selecionadas_anteriores
            ]
            # Se o usuário troca os arquivos de oferta durante a mesma sessão,
            # o Streamlit pode manter labels antigos do multiselect. Reiniciamos
            # somente o widget, preservando as turmas salvas pelo código.
            token_fonte_matricula = tuple(sorted(o.codigo_turma for o in fonte_matricula))
            if st.session_state.get("ajuste_fonte_matricula_token") != token_fonte_matricula:
                st.session_state.pop("ajuste_matricula_multiselect", None)
                st.session_state["ajuste_fonte_matricula_token"] = token_fonte_matricula
            selecao_matricula = st.multiselect(
                "Turmas em que estou matriculado",
                options=list(mapa_matricula),
                default=defaults_matricula,
                key="ajuste_matricula_multiselect",
            )
            if st.button(
                "Usar esta matrícula como base do ajuste",
                disabled=not selecao_matricula,
                use_container_width=True,
                key="ajuste_definir_base",
            ):
                ofertas_matriculadas = tuple(mapa_matricula[x] for x in selecao_matricula)
                codigos = [o.codigo_curriculo for o in ofertas_matriculadas]
                if len(codigos) != len(set(codigos)):
                    st.error("Selecione somente uma turma por disciplina na matrícula atual.")
                else:
                    cumpridas_base = set(contexto["cumpridas_projetadas"]) - set(codigos)
                    try:
                        montar_grade_personalizada(
                            ofertas_matriculadas,
                            curriculo_grade,
                            cumpridas_base,
                            concluidas_editor,
                            busca_editor,
                            rotulo="Matrícula atual",
                        )
                    except Exception as erro_base:
                        st.error(f"A matrícula selecionada não pôde ser usada como base: {erro_base}")
                    else:
                        st.session_state["ajuste_matricula_turmas"] = [o.codigo_turma for o in ofertas_matriculadas]
                        st.session_state["ajuste_matricula_codigos"] = codigos
                        st.session_state["grade_editada_ofertas"] = ofertas_matriculadas
                        st.session_state["grade_editor_historico"] = []
                        st.session_state["grade_editor_base"] = None
                        st.rerun()

            codigos_matricula_atual = set(st.session_state.get("ajuste_matricula_codigos", []))
            cumpridas_editor = set(contexto["cumpridas_projetadas"]) - codigos_matricula_atual
            turmas_matricula_salvas = set(st.session_state.get("ajuste_matricula_turmas", []))
            # Reconstrói a base prioritariamente com a planilha da matrícula inicial.
            # Faz fallback para o PDF de ajuste apenas para manter compatibilidade
            # com sessões antigas ou quando o Excel não foi fornecido.
            ofertas_por_turma = {o.codigo_turma: o for o in ofertas_todas}
            for oferta in ofertas_matricula_inicial:
                ofertas_por_turma[oferta.codigo_turma] = oferta
            ofertas_matricula_salvas = tuple(
                ofertas_por_turma[codigo]
                for codigo in turmas_matricula_salvas
                if codigo in ofertas_por_turma
            )
            if ofertas_matricula_salvas:
                try:
                    grade_ajuste_base = montar_grade_personalizada(
                        ofertas_matricula_salvas,
                        curriculo_grade,
                        cumpridas_editor,
                        concluidas_editor,
                        busca_editor,
                        rotulo="Matrícula atual",
                    )
                    grades_base = [grade_ajuste_base]
                    st.caption(
                        "Base ativa: sua matrícula atual. Remova uma ou mais disciplinas abaixo e o sistema mostrará "
                        "as melhores inclusões com vaga remanescente."
                    )
                except Exception as erro_base_salva:
                    st.warning(f"Não foi possível reconstruir a matrícula atual salva: {erro_base_salva}")

        if not grades_base:
            st.warning(
                "Nenhuma grade automática foi gerada. No modo de ajuste, selecione sua matrícula atual acima para continuar."
            )
        else:
            if grade_ajuste_base is not None:
                base_selecionada = 0
                base_token = (
                    "ajuste",
                    tuple(sorted(o.codigo_turma for o in grade_ajuste_base.ofertas)),
                )
                st.markdown("**Grade inicial:** Matrícula atual informada por você")
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
                base_token = ("planejamento", base_selecionada)

            if st.session_state.get("grade_editor_base") != base_token:
                st.session_state["grade_editor_base"] = base_token
                st.session_state["grade_editada_ofertas"] = tuple(grades_base[base_selecionada].ofertas)
                st.session_state["grade_editor_historico"] = []

            base_grade = grades_base[base_selecionada]
            ofertas_atuais = tuple(st.session_state.get("grade_editada_ofertas", base_grade.ofertas))

            controles1, controles2, controles3 = st.columns([1, 1, 3])
            texto_restaurar = "Restaurar matrícula atual" if grade_ajuste_base is not None else "Restaurar grade-base"
            if controles1.button(texto_restaurar, use_container_width=True):
                st.session_state["grade_editada_ofertas"] = tuple(base_grade.ofertas)
                st.session_state["grade_editor_historico"] = []
                st.rerun()
            historico_editor = st.session_state.get("grade_editor_historico", [])
            if controles2.button("Desfazer", disabled=not historico_editor, use_container_width=True):
                st.session_state["grade_editada_ofertas"] = historico_editor[-1]
                st.session_state["grade_editor_historico"] = historico_editor[:-1]
                st.rerun()
            controles3.caption(
                "Você pode ficar temporariamente abaixo dos créditos mínimos enquanto remove uma matéria e escolhe outra no lugar."
            )

            try:
                grade_atual = montar_grade_personalizada(
                    ofertas_atuais,
                    curriculo_grade,
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
                mensagem_exigidas = (
                    "A grade personalizada não contém disciplina(s) marcada(s) como obrigatória(s) na configuração: "
                    + ", ".join(sorted(exigidas_faltantes))
                )
                if modo_ajuste_contexto:
                    st.warning(mensagem_exigidas + ". No ajuste isso é permitido para você simular uma troca, mas confira antes de finalizar.")
                else:
                    st.error(mensagem_exigidas)

            dataframe_grade = tabela_grade(grade_atual, curriculo_grade)
            if dataframe_grade.empty:
                st.info("A grade está vazia. Escolha uma disciplina compatível abaixo.")
            else:
                tabela_interativa(dataframe_grade, key="grid_grade_atual_editor", height=390)

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
                    curriculo_origem=curriculo_grade,
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
                f"{o.codigo_curriculo} — {curriculo_grade[o.codigo_curriculo].nome} · {o.creditos} cr": o.codigo_curriculo
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
                curriculo_grade,
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
                    categoria = curriculo_grade[sugestao.oferta.codigo_curriculo].categoria.value
                    if filtro_tipo == "Somente obrigatórias" and categoria != "obrigatoria":
                        continue
                    if filtro_tipo == "Somente opção limitada" and categoria != "opcao_limitada":
                        continue
                    sugestoes_filtradas.append(sugestao)

                linhas_sugestoes = []
                labels_sugestoes = []
                for indice, sugestao in enumerate(sugestoes_filtradas):
                    oferta = sugestao.oferta
                    disciplina = curriculo_grade[oferta.codigo_curriculo]
                    gm = sugestao.grade_resultante.metricas
                    avaliacoes = sugestao.grade_resultante.avaliacoes_docentes_por_disciplina.get(oferta.codigo_curriculo, ())
                    avaliacao = ", ".join(a.get("classificacao", "") for a in avaliacoes if a.get("classificacao")) or "Sem dados"
                    vagas_label = (
                        f" · {oferta.vagas_remanescentes} vaga(s)"
                        if oferta.vagas_remanescentes is not None else ""
                    )
                    demanda_label = " · alta demanda" if oferta.alta_demanda else ""
                    origem_label = f" · oferta: {oferta.curso_oferta}" if oferta.curso_oferta else ""
                    label = (
                        f"{oferta.codigo_curriculo} — {disciplina.nome} · {oferta.nome_turma} · "
                        f"{oferta.creditos} cr · total {gm.creditos_totais} cr{vagas_label}{demanda_label}{origem_label}"
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
                        "Vagas remanescentes": oferta.vagas_remanescentes if oferta.vagas_remanescentes is not None else "—",
                        "Alta demanda": "Sim" if oferta.alta_demanda else "Não" if oferta.origem_oferta == "ajuste" else "—",
                        "Oferta vinculada a": oferta.curso_oferta or "—",
                        "Horários": formatar_horarios_oferta(oferta),
                    })

                if linhas_sugestoes:
                    tabela_interativa(pd.DataFrame(linhas_sugestoes), key="grid_sugestoes_editor", height=430)
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
                    ofertas_todas if modo_ajuste_contexto else ofertas_disponiveis,
                    curriculo_grade,
                    cumpridas_editor,
                    busca_editor,
                )
                linhas_diag = []
                for codigo, motivos in diagnosticos_editor.items():
                    disciplina = curriculo_grade.get(codigo)
                    if disciplina is None:
                        continue
                    linhas_diag.append({
                        "Código": codigo,
                        "Disciplina": disciplina.nome,
                        "Motivo": "; ".join(motivos),
                    })
                if linhas_diag:
                    tabela_interativa(pd.DataFrame(linhas_diag), key="grid_diagnosticos_editor", height=360)
                else:
                    st.write("Todas as disciplinas pendentes ofertadas possuem ao menos uma turma compatível.")

            st.markdown("### 3. Salvar grade personalizada")
            exportar1, exportar2 = st.columns(2)
            json_personalizado = grade_personalizada_json(grade_atual, curriculo_grade)
            html_personalizado = grade_personalizada_html(grade_atual, curriculo_grade)
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
