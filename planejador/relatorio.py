from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Iterable

from .academico import classificar_area_formacao, rotulo_custo_adiamento
from .modelos import (
    Categoria,
    DisciplinaCurricular,
    Grade,
    PerfilPlanejamento,
    ResultadoPlanejamento,
    SituacaoAcademica,
    TipoComponente,
)
from .utils import minutos_para_hora

DIAS_NOMES = {
    0: "segunda",
    1: "terça",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sábado",
    6: "domingo",
}

PERFIS_ROTULOS = {
    PerfilPlanejamento.PADRAO: "Modelo padrão",
    PerfilPlanejamento.PROGRESSAO: "Melhor progressão curricular",
    PerfilPlanejamento.COMPACTA: "Grade mais compacta",
    PerfilPlanejamento.EQUILIBRADA: "Carga mais equilibrada",
    PerfilPlanejamento.MENOR_CARGA: "Menor carga acadêmica estimada",
    PerfilPlanejamento.MAIOR_AVANCO: "Maior avanço em créditos",
    PerfilPlanejamento.MENOR_RISCO: "Menor risco pedagógico",
}

CORES_DISCIPLINAS = (
    "#dbeafe", "#dcfce7", "#fef3c7", "#fce7f3", "#ede9fe",
    "#cffafe", "#ffedd5", "#e0e7ff", "#ecfccb", "#fee2e2",
)

ESTAGIO_STATUS_ROTULOS = {
    "nao_iniciado": "não iniciado / não contabilizado",
    "em_andamento": "em andamento — considerado cumprido na projeção",
    "concluido": "concluído/validado — informado manualmente",
}


def _esc(valor: object) -> str:
    return html.escape(str(valor if valor is not None else ""))


def _fmt_numero(valor: float | int) -> str:
    numero = float(valor)
    if numero.is_integer():
        return str(int(numero))
    return f"{numero:.1f}".replace(".", ",")


def _fmt_duracao(minutos: int) -> str:
    if minutos <= 0:
        return "0 min"
    horas, resto = divmod(minutos, 60)
    if horas and resto:
        return f"{horas}h {resto}min"
    if horas:
        return f"{horas}h"
    return f"{resto} min"


def _nomes_codigos(
    codigos: Iterable[str],
    curriculo: dict[str, DisciplinaCurricular],
) -> str:
    return "; ".join(
        f"{curriculo[c].nome} [{c}]" if c in curriculo else c
        for c in codigos
    )


def _pontos_grade(
    grade: Grade,
    creditos_alvo: int,
    projecoes_valem_como_cumpridas: bool = True,
) -> tuple[list[str], list[str]]:
    m = grade.metricas
    positivos: list[str] = []
    negativos: list[str] = []
    if m.recomendacoes_faltantes == 0:
        positivos.append("todas as recomendações pedagógicas estão atendidas no cenário selecionado")
    else:
        negativos.append(f"há {m.recomendacoes_faltantes} recomendação(ões) ainda não atendida(s)")
    if m.dependencias_em_andamento:
        texto = (
            f"{m.dependencias_em_andamento} recomendação(ões) são atendidas por disciplinas "
            "em andamento presumidas aprovadas"
        )
        if projecoes_valem_como_cumpridas:
            positivos.append(texto)
        else:
            negativos.append("depende da aprovação projetada em " + str(m.dependencias_em_andamento) + " recomendação(ões)")
    if m.atraso_curricular_total:
        positivos.append(
            f"recupera {m.atraso_curricular_total} ponto(s) de atraso acumulado em relação ao PPC"
        )
    if m.disciplinas_totalmente_destravadas:
        positivos.append(
            f"deixa {m.disciplinas_totalmente_destravadas} disciplina(s) futura(s) com todas as recomendações atendidas"
        )
    if m.pendencias_futuras_impactadas:
        positivos.append(
            f"impacta diretamente {m.pendencias_futuras_impactadas} pendência(s) curricular(es) futura(s)"
        )
    if m.creditos_totais == creditos_alvo:
        positivos.append("atinge exatamente a carga-alvo configurada")
    elif abs(m.creditos_totais - creditos_alvo) <= 2:
        positivos.append("fica próxima da carga-alvo configurada")
    if m.buracos_minutos == 0:
        positivos.append("não possui janelas internas entre duas aulas do mesmo dia")
    else:
        negativos.append(f"possui {_fmt_duracao(m.buracos_minutos)} de janelas internas")
    if m.tempo_livre_extremidades_minutos:
        negativos.append(
            f"há {_fmt_duracao(m.tempo_livre_extremidades_minutos)} de blocos livres no início ou fim das noites"
        )
    if m.dias_com_aula >= 5:
        negativos.append("exige presença em cinco ou mais dias da semana")
    elif m.dias_com_aula <= 4:
        positivos.append(f"concentra as aulas em {m.dias_com_aula} dia(s)")
    if m.disciplinas_praticas >= 3:
        negativos.append("concentra três ou mais disciplinas com componente prático")
    if m.carga_individual >= 20:
        negativos.append(f"possui carga individual de referência elevada ({m.carga_individual})")
    if m.docentes_a_evitar:
        negativos.append("contém docente marcado como preferência negativa")
    if m.docentes_preferidos:
        positivos.append("contém docente indicado como preferido")
    if m.docentes_favoraveis:
        positivos.append(f"inclui {m.docentes_favoraveis} avaliação(ões) docente(s) favorável(is) do UFABC Next")
    if m.docentes_alerta:
        negativos.append(f"inclui {m.docentes_alerta} avaliação(ões) docente(s) com alerta no UFABC Next")
    return positivos, negativos


def _recomendacoes_status(
    disciplina: DisciplinaCurricular,
    curriculo: dict[str, DisciplinaCurricular],
    concluidas_reais: set[str],
    cumpridas_projetadas: set[str],
) -> list[tuple[str, str, str]]:
    resultado: list[tuple[str, str, str]] = []
    for codigo in disciplina.recomendacoes:
        nome = curriculo[codigo].nome if codigo in curriculo else codigo
        if codigo in concluidas_reais:
            resultado.append((codigo, nome, "concluída"))
        elif codigo in cumpridas_projetadas:
            resultado.append((codigo, nome, "em andamento — aprovada na projeção"))
        else:
            resultado.append((codigo, nome, "ainda não cumprida"))
    return resultado


def _texto_grade(
    grade: Grade,
    curriculo: dict[str, DisciplinaCurricular],
    titulo: str,
    creditos_alvo: int,
    concluidas_reais: set[str],
    cumpridas_projetadas: set[str],
    estimativa_formatura: dict | None = None,
    projecoes_valem_como_cumpridas: bool = True,
    detalhar_motivos: bool = True,
) -> list[str]:
    linhas = [titulo, "=" * 78]
    for oferta in sorted(
        grade.ofertas,
        key=lambda o: (
            curriculo[o.codigo_curriculo].quadrimestre_recomendado or 99,
            o.codigo_curriculo,
        ),
    ):
        disciplina = curriculo[oferta.codigo_curriculo]
        linhas.append(
            f"{disciplina.nome} [{disciplina.codigo}] — {oferta.creditos} créditos "
            f"(PPC Q{disciplina.quadrimestre_recomendado or '?'})"
        )
        linhas.append(f"  Turma: {oferta.nome_turma}")
        if oferta.docentes:
            linhas.append(f"  Docente(s): {', '.join(oferta.docentes)}")
        for avaliacao in grade.avaliacoes_docentes_por_disciplina.get(disciplina.codigo, ()):
            fonte = "na disciplina" if avaliacao.get("fonte") == "disciplina" else "geral"
            linhas.append(
                f"  UFABC Next ({fonte}): {avaliacao.get('classificacao', 'sem classificação')} | "
                f"qualidade {avaliacao.get('qualidade_pedagogica', 'sem dados')} | "
                f"risco {avaliacao.get('risco_academico', 'sem dados')} | "
                f"confiança {avaliacao.get('confianca', 'sem dados')}"
            )
            linhas.append(
                f"    Amostra: {avaliacao.get('conceitos', 0)} conceitos e "
                f"{avaliacao.get('comentarios', 0)} comentários | "
                f"efeito flexível no ranking: {avaliacao.get('efeito_ranking_aplicado', 0):+g}"
            )
        linhas.append(
            f"  T-P-E-I: {oferta.t}-{oferta.p}-{oferta.e}-{oferta.i} | "
            f"carga total de referência: {oferta.carga_total_referencia}"
        )
        if oferta.vagas_veteranos is not None:
            linhas.append(
                f"  Vagas previstas: total {oferta.vagas_totais if oferta.vagas_totais is not None else '?'}; "
                f"veteranos {oferta.vagas_veteranos}"
            )
        for horario in sorted(oferta.horarios, key=lambda h: (h.dia, h.inicio)):
            linhas.append(
                f"  {DIAS_NOMES[horario.dia]} "
                f"{minutos_para_hora(horario.inicio)}–{minutos_para_hora(horario.fim)} "
                f"({horario.recorrencia.value}, {horario.tipo})"
            )
        recomendacoes_status = _recomendacoes_status(
            disciplina, curriculo, concluidas_reais, cumpridas_projetadas
        )
        if recomendacoes_status:
            linhas.append("  Recomendações anteriores:")
            for codigo_rec, nome_rec, status_rec in recomendacoes_status:
                simbolo = "✓" if status_rec == "concluída" else ("◐" if "projeção" in status_rec else "⚠")
                linhas.append(f"    {simbolo} {nome_rec} [{codigo_rec}] — {status_rec}")
        if disciplina.requisito_manual:
            linhas.append("  ⚠ Verificação manual: " + disciplina.requisito_manual)
        linhas.append("")

    m = grade.metricas
    linhas.extend(
        [
            f"TOTAL: {m.creditos_totais} créditos",
            f"Obrigatórios: {m.creditos_obrigatorios} | Opção limitada: {m.creditos_opcao_limitada}",
            f"T-P-E-I acumulado: {m.carga_teorica}-{m.carga_pratica}-{m.carga_extensao}-{m.carga_individual}",
            f"Carga acadêmica total de referência: {m.carga_total_referencia}",
            f"Disciplinas com prática: {m.disciplinas_praticas}",
            f"Dias com aula: {m.dias_com_aula}",
            f"Tempo em aula: {_fmt_duracao(m.tempo_em_aula_minutos)}",
            f"Permanência semanal estimada no campus: {_fmt_duracao(m.permanencia_total_minutos)}",
            f"Janelas internas entre aulas: {_fmt_duracao(m.buracos_minutos)}",
            f"Blocos livres no início/fim das noites: {_fmt_duracao(m.tempo_livre_extremidades_minutos)}",
            f"Dias com jornada parcial: {m.dias_com_jornada_parcial}",
            f"Recomendações faltantes: {m.recomendacoes_faltantes}",
            f"Dependências baseadas em aprovação projetada: {m.dependencias_em_andamento}",
            f"Atraso curricular recuperado: {m.atraso_curricular_total}",
            f"Vínculos de recomendação atendidos: {m.desbloqueios_diretos}",
            f"Pendências futuras impactadas: {m.pendencias_futuras_impactadas}",
            f"Disciplinas totalmente destravadas: {m.disciplinas_totalmente_destravadas}",
            f"Avaliações docentes utilizadas: {m.docentes_avaliados} | favoráveis: {m.docentes_favoraveis} | alertas: {m.docentes_alerta}",
            f"Ajuste docente flexível no ranking: {m.ajuste_avaliacao_docente:+g}",
        ]
    )
    if estimativa_formatura:
        linhas.extend([
            f"Previsão de conclusão: entre {estimativa_formatura.get('periodo_estimado_minimo', '?')} "
            f"e {estimativa_formatura.get('periodo_estimado_prudente', '?')}",
            f"Quadrimestres estimados incluindo o atual: "
            f"{estimativa_formatura.get('quadrimestres_estimados_incluindo_atual', '?')} "
            f"(prudente: {estimativa_formatura.get('quadrimestres_estimados_prudente', '?')})",
            f"Créditos totais pendentes após esta grade: "
            f"{estimativa_formatura.get('creditos_totais_pendentes_apos_grade', estimativa_formatura.get('creditos_pendentes_apos_grade', '?'))}",
            f"Carga regular usada no cálculo de ritmo: "
            f"{estimativa_formatura.get('creditos_regulares_pendentes_apos_grade', '?')} cr",
            f"TG pendente: {estimativa_formatura.get('creditos_tg_pendentes_apos_grade', '?')} cr "
            f"({estimativa_formatura.get('tg_etapas_pendentes', '?')} etapa(s)); "
            f"estágio pendente: {estimativa_formatura.get('creditos_estagio_pendentes_apos_grade', '?')} cr",
        ])
    if m.vagas_veteranos_minimas is not None:
        linhas.append(
            f"Menor número de vagas de veteranos entre as turmas: {m.vagas_veteranos_minimas} "
            "(capacidade prevista, não garantia de matrícula)"
        )
    if detalhar_motivos:
        positivos, negativos = _pontos_grade(
            grade, creditos_alvo, projecoes_valem_como_cumpridas
        )
        linhas.append("Por que esta opção aparece:")
        for item in positivos:
            linhas.append(f"  + {item}")
        for item in negativos:
            linhas.append(f"  - {item}")
    linhas.append("")
    return linhas


def _secao_auditoria(auditoria: dict, situacao: SituacaoAcademica) -> list[str]:
    linhas = ["AUDITORIA CURRICULAR", "-" * 78]
    linhas.append(
        f"Componentes concluídos no histórico: {auditoria['componentes_historico_concluidos']}"
    )
    linhas.append(
        f"Componentes da matriz confirmados no histórico: "
        f"{auditoria.get('componentes_curriculo_concluidos_confirmados', auditoria['componentes_curriculo_concluidos'])}"
    )
    linhas.append(
        f"Componentes da matriz reconhecidos no cenário projetado: "
        f"{auditoria.get('componentes_curriculo_concluidos_projetados', auditoria['componentes_curriculo_concluidos'])}"
    )
    linhas.append("")
    linhas.append("VÍNCULO ATUAL — QUADRO OFICIAL DO SIGAA")
    sigaa = auditoria.get("sigaa_vinculo_atual", {})
    for categoria, rotulo in (
        ("obrigatorias", "Obrigatórias"),
        ("optativos", "Optativos"),
        ("livres", "Livres"),
        ("complementares", "Complementares"),
        ("total", "Total"),
    ):
        dados = sigaa.get(categoria, {})
        if dados:
            linhas.append(
                f"{rotulo}: {dados['integralizado_horas']} / {dados['exigido_horas']} h "
                f"(pendentes: {dados['pendente_horas']} h)"
            )
    linhas.append("")
    linhas.append("ENGENHARIA DE MATERIAIS 2017 — ESTIMATIVA RECLASSIFICADA")
    for categoria, rotulo in (
        ("obrigatoria", "Obrigatórios"),
        ("opcao_limitada", "Opção limitada"),
        ("livre", "Livres"),
    ):
        dados = auditoria["por_categoria"][categoria]
        if categoria == "livre":
            linhas.append(
                f"{rotulo}: {dados['integralizado_estimado']} / {dados['exigido']} cr estimados "
                f"({dados['integralizado_confirmado']} diretamente classificados + "
                f"{auditoria['livres_estimados_adicionais']} potenciais; "
                f"pendentes estimados: {dados['pendente_estimado']})"
            )
        else:
            if dados.get("integralizado_estimado") != dados.get("integralizado_confirmado"):
                linhas.append(
                    f"{rotulo}: {dados['integralizado_confirmado']} cr confirmados no histórico; "
                    f"{dados['integralizado_estimado']} / {dados['exigido']} cr no cenário projetado "
                    f"(pendentes projetados: {dados['pendente_estimado']})"
                )
            else:
                linhas.append(
                    f"{rotulo}: {dados['integralizado_confirmado']} / {dados['exigido']} cr confirmados "
                    f"(pendentes: {dados['pendente_confirmado']})"
                )
    linhas.append(auditoria.get("observacao_categorias", ""))
    if situacao.resumo.atividades_complementares_horas is not None:
        linhas.append(
            f"Atividades complementares registradas: "
            f"{situacao.resumo.atividades_complementares_horas:g} h"
        )
    for tipo, rotulo in (
        ("engenharia_unificada", "Engenharia Unificada"),
        ("trabalho_graduacao", "Trabalho de Graduação"),
        ("estagio", "Estágio curricular"),
    ):
        dados = auditoria["especiais"][tipo]
        status_extra = ""
        if tipo == "estagio":
            status = dados.get("status_informado", "nao_iniciado")
            status_extra = f"; situação informada: {ESTAGIO_STATUS_ROTULOS.get(status, status)}"
        linhas.append(
            f"{rotulo}: {dados.get('integralizado_confirmado', dados['integralizado'])} cr confirmados; "
            f"{dados.get('integralizado_projetado', dados['integralizado'])} / {dados['exigido']} cr projetados; "
            f"pendentes na projeção: {', '.join(dados.get('pendentes_projetados', dados['pendentes'])) or 'nenhum'}"
            f"{status_extra}"
        )
    linhas.append("")
    return linhas


def _grade_chave(grade: Grade) -> str:
    return "|".join(grade.assinatura_disciplinas)


def _secao_validacao_texto(validacao: dict) -> list[str]:
    if not validacao:
        return []

    global_completa = bool(validacao.get("busca_completa"))
    ranking_exato = bool(validacao.get("ranking_padrao_exato", False))
    pareto_completa = bool(validacao.get("fronteira_pareto_completa", False))

    linhas = ["CERTIFICADO DE VALIDAÇÃO DA BUSCA", "-" * 78]
    if global_completa:
        linhas.append("Status global: todas as disciplinas candidatas foram incluídas na enumeração.")
    else:
        linhas.append(
            "Status global: limitado — parte das disciplinas candidatas foi excluída pelo limite configurado."
        )

    linhas.append(
        f"Disciplinas candidatas: {validacao.get('disciplinas_candidatas_encontradas', 0)}; "
        f"analisadas: {validacao.get('disciplinas_analisadas', 0)}; "
        f"limite: {validacao.get('limite_disciplinas_candidatas', 0)}"
    )
    linhas.append(
        f"Combinações teóricas de escolha/turma: {validacao.get('combinacoes_teoricas', 0):,}".replace(",", ".")
    )
    linhas.append(f"Nós visitados: {validacao.get('nos_visitados', 0):,}".replace(",", "."))
    linhas.append(
        f"Grades concretas válidas: {validacao.get('grades_concretas_validas', 0)}; "
        f"conjuntos únicos: {validacao.get('conjuntos_unicos_validos', 0)}; "
        f"retidos para apresentação/Pareto: {validacao.get('conjuntos_retidos_no_pool', validacao.get('conjuntos_unicos_validos', 0))}"
    )
    linhas.append(
        f"Podas por conflito: {validacao.get('podas_por_conflito', 0)}; "
        f"podas por créditos: {validacao.get('podas_por_creditos', 0)}"
    )
    linhas.append(
        "✓ Ranking das grades padrão e dos perfis: exato para todas as candidatas analisadas."
        if ranking_exato
        else "⚠ O ranking padrão pode ter sido interrompido antes do fim."
    )
    if pareto_completa:
        linhas.append("✓ Fronteira de Pareto: completa para todas as grades válidas analisadas.")
    else:
        linhas.append(
            "⚠ Fronteira de Pareto: parcial, calculada sobre o conjunto retido; isso não altera as grades padrão."
        )
    if not global_completa:
        linhas.append(
            "⚠ A optimalidade global entre todas as disciplinas ofertadas não é garantida. "
            "Aumente o limite de candidatas para ampliar a cobertura."
        )
    linhas.append("")
    return linhas


def _secao_desempenho_texto(analise: dict) -> list[str]:
    if not analise:
        return []
    linhas = ["ANÁLISE DO HISTÓRICO ACADÊMICO", "-" * 78]
    linhas.append(
        f"Aprovações em turmas: {analise.get('aprovacoes', 0)} | "
        f"Reprovações: {analise.get('reprovacoes', 0)} | "
        f"Taxa de aprovação: {_fmt_numero(analise.get('taxa_aprovacao_percentual', 0))}%"
    )
    linhas.append(
        f"Dispensas/transferências/aproveitamentos: {analise.get('aproveitamentos_dispensas', 0)} | "
        f"Créditos aprovados em turmas: {analise.get('creditos_aprovados_em_turmas', 0)}"
    )
    coef = analise.get("coeficientes_oficiais", {})
    if coef:
        linhas.append("Coeficientes oficiais: " + " | ".join(f"{k}={_fmt_numero(v)}" for k, v in coef.items()))
    dist = analise.get("distribuicao_conceitos", {})
    linhas.append("Distribuição de conceitos: " + " | ".join(f"{c}: {dist.get(c, 0)}" for c in ("A", "B", "C", "D", "F", "O")))
    recuperadas = analise.get("disciplinas_recuperadas_apos_reprovacao", [])
    if recuperadas:
        linhas.append(f"Disciplinas aprovadas após reprovação anterior: {len(recuperadas)}")
    linhas.append("")
    return linhas


def _validacao_html(validacao: dict) -> str:
    if not validacao:
        return ""

    global_completa = bool(validacao.get("busca_completa"))
    ranking_exato = bool(validacao.get("ranking_padrao_exato", False))
    pareto_completa = bool(validacao.get("fronteira_pareto_completa", False))

    if global_completa and pareto_completa:
        classe = "certificate-ok"
        status = "Busca global completa"
        descricao = "Todas as candidatas e combinações viáveis foram percorridas; rankings e Pareto são completos."
        selo = "✓"
    elif global_completa:
        classe = "certificate-ok"
        status = "Rankings exatos · Pareto parcial"
        descricao = (
            "Todas as candidatas foram enumeradas e as grades padrão são exatas. "
            "Somente a fronteira de Pareto foi limitada ao conjunto retido."
        )
        selo = "✓"
    else:
        classe = "certificate-warning"
        status = "Busca global limitada"
        descricao = (
            "O ranking é exato para as candidatas analisadas, mas algumas disciplinas ofertadas ficaram fora "
            "pelo limite configurado."
        )
        selo = "!"

    total_unicos = int(validacao.get("conjuntos_unicos_validos", 0))
    retidos = int(validacao.get("conjuntos_retidos_no_pool", total_unicos))
    cards = "".join([
        _metric_card(
            "Candidatas analisadas",
            str(validacao.get("disciplinas_analisadas", 0)),
            f"de {validacao.get('disciplinas_candidatas_encontradas', 0)} encontradas",
        ),
        _metric_card(
            "Combinações teóricas",
            f"{validacao.get('combinacoes_teoricas', 0):,}".replace(",", "."),
            "escolha de disciplina/turma",
        ),
        _metric_card(
            "Grades únicas",
            str(total_unicos),
            f"{retidos} retidas para Pareto/apresentação",
        ),
        _metric_card(
            "Ranking padrão",
            "Exato" if ranking_exato else "Parcial",
            "no conjunto analisado",
        ),
        _metric_card(
            "Fronteira de Pareto",
            "Completa" if pareto_completa else "Parcial",
            "não altera o Top 5",
        ),
        _metric_card(
            "Avaliações docentes",
            str(validacao.get("avaliacoes_docentes_carregadas", 0)),
            "registros usados no ranking",
        ),
    ])
    return (
        f"<div class='search-certificate {classe}'><div class='certificate-head'>"
        f"<div><span class='eyebrow'>Certificado de busca</span><h3>{_esc(status)}</h3><p>{_esc(descricao)}</p></div>"
        f"<span class='certificate-seal'>{selo}</span></div>"
        f"<div class='metrics-grid'>{cards}</div></div>"
    )


def _desempenho_html(analise: dict) -> str:
    if not analise:
        return "<p class='muted'>Análise de desempenho desativada.</p>"
    taxa = float(analise.get("taxa_aprovacao_percentual", 0))
    dist = analise.get("distribuicao_conceitos", {})
    max_conceito = max([int(v) for v in dist.values()] + [1])
    conceito_barras = "".join(
        f"<div class='concept-row'><strong>{c}</strong><div class='concept-track'><span style='width:{int(dist.get(c,0))/max_conceito*100:.1f}%'></span></div><em>{dist.get(c,0)}</em></div>"
        for c in ("A", "B", "C", "D", "F", "O")
    )
    evolucao = analise.get("evolucao_por_periodo", [])
    max_eventos = max([p.get("aprovacoes",0)+p.get("reprovacoes",0) for p in evolucao] + [1])
    evolucao_barras = "".join(
        f"<div class='period-row'><span>{_esc(p.get('periodo',''))}</span>"
        f"<div class='period-track'><i class='approved' style='width:{p.get('aprovacoes',0)/max_eventos*100:.1f}%'></i>"
        f"<i class='failed' style='width:{p.get('reprovacoes',0)/max_eventos*100:.1f}%'></i></div>"
        f"<small>{p.get('aprovacoes',0)} apr. · {p.get('reprovacoes',0)} rep.</small></div>"
        for p in evolucao
    )
    coef = analise.get("coeficientes_oficiais", {})
    coef_cards = "".join(
        _metric_card(k, _fmt_numero(v), "coeficiente oficial do histórico")
        for k, v in coef.items()
    )
    cards = "".join([
        _metric_card("Aprovações", str(analise.get("aprovacoes",0)), "resultados APR/APRN"),
        _metric_card("Reprovações", str(analise.get("reprovacoes",0)), "tentativas não concluídas"),
        _metric_card("Taxa de aprovação", f"{_fmt_numero(taxa)}%", "entre tentativas avaliadas", taxa),
        _metric_card("Aproveitamentos", str(analise.get("aproveitamentos_dispensas",0)), "dispensas, transferências e convalidações"),
    ])
    recuperadas = analise.get("disciplinas_recuperadas_apos_reprovacao", [])
    rec_html = "".join(
        f"<li><strong>{_esc(x['codigo'])}</strong> — {_esc(x['nome'])} <span>{x['tentativas']} registros</span></li>"
        for x in recuperadas
    ) or "<li>Nenhuma disciplina recuperada após reprovação foi identificada.</li>"
    return (
        f"<div class='metrics-grid'>{cards}{coef_cards}</div>"
        f"<div class='analytics-grid'><article class='chart-card'><h3>Taxa de aprovação</h3>"
        f"<div class='donut' style='--pct:{taxa:.1f}'><span>{_fmt_numero(taxa)}%</span></div>"
        f"<p>Considera somente tentativas com aprovação ou reprovação.</p></article>"
        f"<article class='chart-card'><h3>Distribuição de conceitos</h3>{conceito_barras}</article></div>"
        f"<article class='chart-card wide'><h3>Evolução por quadrimestre</h3>"
        f"<div class='legend'><span class='leg-approved'>Aprovações</span><span class='leg-failed'>Reprovações</span></div>"
        f"<div class='period-chart'>{evolucao_barras}</div></article>"
        f"<details class='simple'><summary>Disciplinas aprovadas após reprovação anterior</summary><ul class='recovery-list'>{rec_html}</ul></details>"
    )


def gerar_relatorio_texto(
    caminho: str | Path,
    metadados: dict,
    curriculo: dict[str, DisciplinaCurricular],
    situacao: SituacaoAcademica,
    cumpridas_projetadas: set[str],
    resultado: ResultadoPlanejamento,
    auditoria: dict,
    avisos_ofertas: list[str],
    modo_projecao: str,
    quadrimestre_planejado: int | None,
    periodo_planejamento: str,
    creditos_alvo: int,
    frequencias: dict[str, dict[str, float | int]],
    analise_desempenho: dict,
    estimativas_formatura: dict[str, dict],
    validacao_busca: dict,
    projecoes_valem_como_cumpridas: bool,
) -> None:
    linhas = [
        "PLANEJADOR DE MATRÍCULA — UFABC",
        "=" * 78,
        f"Curso: {metadados.get('curso', '')}",
        f"Matriz: {metadados.get('versao', '')}",
        f"Período planejado: {periodo_planejamento or 'não informado'}",
        f"Quadrimestre aproximado do aluno: Q{quadrimestre_planejado or '?'}",
        f"Modo de projeção das disciplinas em andamento: {modo_projecao}",
        "",
        "IMPORTANTE",
        "-" * 78,
        "As grades são alternativas de apoio à decisão. Recomendações do PPC não são "
        "tratadas como bloqueios gerais de matrícula. Vagas e planejamento futuro não "
        "constituem garantia de alocação ou de oferta.",
        "",
    ]
    linhas.extend(_secao_auditoria(auditoria, situacao))
    linhas.extend(_secao_validacao_texto(validacao_busca))
    linhas.extend(_secao_desempenho_texto(analise_desempenho))

    pendentes_obrigatorias = [
        d for d in curriculo.values()
        if d.categoria == Categoria.OBRIGATORIA and d.codigo not in cumpridas_projetadas
    ]
    linhas.extend(["SITUAÇÃO ACADÊMICA", "-" * 78])
    linhas.append(f"Disciplinas em andamento: {len(situacao.em_andamento)}")
    if situacao.em_andamento:
        linhas.append("Em andamento: " + _nomes_codigos(sorted(situacao.em_andamento), curriculo))
    linhas.append(f"Obrigatórias pendentes projetadas: {len(pendentes_obrigatorias)}")
    linhas.append("")

    linhas.extend(["ORDEM CURRICULAR E PENDÊNCIAS", "-" * 78])
    for d in sorted(pendentes_obrigatorias, key=lambda x: (x.quadrimestre_recomendado or 99, x.codigo)):
        atraso = max(0, (quadrimestre_planejado or 0) - (d.quadrimestre_recomendado or (quadrimestre_planejado or 0)))
        tipo = "" if d.tipo_componente == TipoComponente.DISCIPLINA_REGULAR else f" [{d.tipo_componente.value}]"
        linhas.append(
            f"Q{d.quadrimestre_recomendado or '?'} — {d.codigo} — {d.nome} "
            f"({d.creditos} cr){tipo} | atraso aproximado: {atraso}Q"
        )
    linhas.append("")

    linhas.extend([
        f"GRADES PADRÃO — {len(resultado.grades_padrao)} OPÇÕES",
        "#" * 78,
        "Esta seção preserva o modelo original. O projeto sempre tenta apresentar "
        "pelo menos 3 opções e, por padrão, apresenta 5.",
        "",
    ])
    if resultado.grades_padrao:
        for indice, grade in enumerate(resultado.grades_padrao, start=1):
            linhas.extend(_texto_grade(
                grade, curriculo, f"OPÇÃO PADRÃO {indice}", creditos_alvo,
                situacao.concluidas, cumpridas_projetadas,
                estimativas_formatura.get(_grade_chave(grade), {}),
                projecoes_valem_como_cumpridas,
                detalhar_motivos=(indice == 1),
            ))
    else:
        linhas.append("Nenhuma grade viável foi encontrada com os limites configurados.\n")

    if resultado.grades_por_perfil:
        linhas.extend(["ALTERNATIVAS POR OBJETIVO", "#" * 78, ""])
        for perfil, grade in resultado.grades_por_perfil.items():
            linhas.extend(_texto_grade(
                grade, curriculo, PERFIS_ROTULOS[perfil], creditos_alvo,
                situacao.concluidas, cumpridas_projetadas,
                estimativas_formatura.get(_grade_chave(grade), {}),
                projecoes_valem_como_cumpridas, detalhar_motivos=True
            ))

    if resultado.fronteira_pareto:
        linhas.extend([
            "ALTERNATIVAS NÃO DOMINADAS", "#" * 78,
            "Cada opção oferece uma troca diferente entre progressão, logística e carga.", "",
        ])
        for indice, grade in enumerate(resultado.fronteira_pareto, start=1):
            m = grade.metricas
            linhas.append(
                f"PARETO {indice}: {', '.join(grade.assinatura_disciplinas)} | "
                f"{m.creditos_totais} cr | {m.dias_com_aula} dias | "
                f"janelas {_fmt_duracao(m.buracos_minutos)} | "
                f"bordas livres {_fmt_duracao(m.tempo_livre_extremidades_minutos)} | "
                f"carga {m.carga_total_referencia} | atraso recuperado {m.atraso_curricular_total}"
            )
        linhas.append("")

    if resultado.grades_reserva and resultado.grade_principal:
        linhas.extend([
            "PLANO PRINCIPAL E GRADES DE RESERVA", "#" * 78,
            "As reservas ajudam caso uma disciplina ou turma do plano principal não seja obtida.", "",
            "Plano principal: " + ", ".join(resultado.grade_principal.assinatura_disciplinas),
        ])
        for codigo_removido, grade in resultado.grades_reserva:
            linhas.append(f"Sem {codigo_removido}: usar {', '.join(grade.assinatura_disciplinas)}")
        linhas.append("")

    if resultado.cenarios:
        linhas.extend(["COMPARAÇÃO DE CENÁRIOS", "#" * 78, ""])
        for cenario in resultado.cenarios:
            if cenario.melhor_grade:
                linhas.append(
                    f"{cenario.nome}: {cenario.pendentes_obrigatorias} obrigatórias pendentes; "
                    f"melhor grade = {', '.join(cenario.melhor_grade.assinatura_disciplinas)} "
                    f"({cenario.melhor_grade.metricas.creditos_totais} cr)"
                )
            else:
                linhas.append(
                    f"{cenario.nome}: {cenario.pendentes_obrigatorias} obrigatórias pendentes; nenhuma grade encontrada"
                )
        linhas.append("")

    if resultado.planos_futuros:
        linhas.extend([
            "PLANEJAMENTO MULTIQUADRIMESTRAL", "#" * 78,
            "Somente o primeiro período usa ofertas e horários reais. Os seguintes são uma projeção.", "",
        ])
        for plano in resultado.planos_futuros:
            linhas.append(
                f"{plano.rotulo} (Q{plano.indice or '?'}): {plano.creditos} cr — "
                + _nomes_codigos(plano.codigos, curriculo)
            )
            linhas.append(f"  {plano.observacao}")
        linhas.append("")

    pendentes_ol = [
        d for d in curriculo.values()
        if d.categoria == Categoria.OPCAO_LIMITADA and d.codigo not in cumpridas_projetadas
    ]
    if pendentes_ol:
        linhas.extend(["OPÇÃO LIMITADA E PERFIL DE FORMAÇÃO", "#" * 78])
        for d in sorted(pendentes_ol, key=lambda x: (x.quadrimestre_recomendado or 99, x.nome))[:20]:
            linhas.append(
                f"{d.codigo} — {d.nome} ({d.creditos} cr) | áreas: "
                + ", ".join(classificar_area_formacao(d))
            )
        linhas.append("")

    linhas.extend(["CUSTO DE ADIAMENTO", "#" * 78])
    if not frequencias:
        linhas.append(
            "Nenhuma planilha histórica adicional foi configurada. O custo usa atraso e desbloqueio."
        )
    desbloqueios: dict[str, int] = {}
    for d in curriculo.values():
        for recomendacao in d.recomendacoes:
            desbloqueios[recomendacao] = desbloqueios.get(recomendacao, 0) + 1
    for d in sorted(pendentes_obrigatorias, key=lambda x: (x.quadrimestre_recomendado or 99, x.codigo)):
        if d.tipo_componente != TipoComponente.DISCIPLINA_REGULAR:
            continue
        atraso = max(0, (quadrimestre_planejado or 0) - (d.quadrimestre_recomendado or (quadrimestre_planejado or 0)))
        linhas.append(
            f"{d.codigo} — {rotulo_custo_adiamento(d.codigo, frequencias, atraso, desbloqueios.get(d.codigo, 0))}"
        )
    linhas.append("")

    linhas.extend(["DISCIPLINAS PENDENTES FORA DAS OPÇÕES PADRÃO", "#" * 78])
    presentes = {codigo for grade in resultado.grades_padrao for codigo in grade.assinatura_disciplinas}
    houve = False
    for d in sorted(pendentes_obrigatorias, key=lambda x: (x.quadrimestre_recomendado or 99, x.codigo)):
        if d.codigo in presentes:
            continue
        houve = True
        diag = resultado.diagnosticos.get(d.codigo)
        motivos = "; ".join(diag.motivos) if diag and diag.motivos else "não entrou entre as melhores combinações"
        linhas.append(f"{d.codigo} — {d.nome}: {motivos}")
    if not houve:
        linhas.append("Todas as pendências ofertadas aparecem em pelo menos uma opção padrão.")
    linhas.append("")

    todos_avisos = list(avisos_ofertas) + list(resultado.avisos)
    if todos_avisos:
        linhas.extend(["AVISOS E VALIDAÇÕES", "#" * 78])
        linhas.extend(f"- {aviso}" for aviso in dict.fromkeys(todos_avisos))
        linhas.append("")

    linhas.extend([
        "PRIVACIDADE E CONFERÊNCIA", "#" * 78,
        "O processamento é local. Confirme no SIGAA as regras de matrícula, vagas, "
        "equivalências, estágio e TG antes da decisão final.",
    ])
    Path(caminho).write_text("\n".join(linhas), encoding="utf-8")


def _cor_disciplina(codigo: str) -> str:
    indice = int(hashlib.sha1(codigo.encode("utf-8")).hexdigest()[:4], 16) % len(CORES_DISCIPLINAS)
    return CORES_DISCIPLINAS[indice]


def _grade_schedule_html(grade: Grade, curriculo: dict[str, DisciplinaCurricular]) -> str:
    dias_presentes = {h.dia for o in grade.ofertas for h in o.horarios}
    dias = range(0, max(4, max(dias_presentes, default=4)) + 1)
    blocos = sorted({(h.inicio, h.fim) for o in grade.ofertas for h in o.horarios})
    if not blocos:
        return "<p class='muted'>Sem horários regulares.</p>"
    cabecalho = "".join(f"<th>{_esc(DIAS_NOMES[d].title())}</th>" for d in dias)
    linhas: list[str] = []
    for inicio, fim in blocos:
        celulas: list[str] = []
        for dia in dias:
            itens: list[str] = []
            for oferta in grade.ofertas:
                for horario in oferta.horarios:
                    if horario.dia == dia and horario.inicio == inicio and horario.fim == fim:
                        disciplina = curriculo[oferta.codigo_curriculo]
                        itens.append(
                            f"<div class='schedule-course' style='background:{_cor_disciplina(oferta.codigo_curriculo)}'>"
                            f"<strong>{_esc(oferta.codigo_curriculo)}</strong>"
                            f"<span>{_esc(disciplina.nome)}</span>"
                            f"<small>{_esc(horario.recorrencia.value.replace('_', ' '))} · {_esc(horario.tipo)}</small>"
                            "</div>"
                        )
            if itens:
                celulas.append("<td>" + "".join(itens) + "</td>")
            else:
                celulas.append("<td class='free-cell'><span>Livre</span></td>")
        linhas.append(
            f"<tr><th class='time'>{minutos_para_hora(inicio)}–{minutos_para_hora(fim)}</th>"
            + "".join(celulas) + "</tr>"
        )
    return (
        "<div class='schedule-wrap'><table class='schedule'><thead><tr><th>Horário</th>"
        + cabecalho + "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
        "<div class='schedule-note'><strong>Como ler:</strong> uma célula livre antes da primeira "
        "aula ou depois da última aula do dia não é uma janela interna, pois você pode chegar mais "
        "tarde ou sair mais cedo. O relatório mede separadamente as <em>janelas entre duas aulas</em> "
        "e os <em>blocos livres nas extremidades da noite</em>.</div>"
    )


def _pill(texto: str, classe: str = "") -> str:
    return f"<span class='pill {classe}'>{_esc(texto)}</span>"


def _metric_card(titulo: str, valor: str, detalhe: str = "", progresso: float | None = None, classe: str = "") -> str:
    barra = ""
    if progresso is not None:
        progresso = min(100, max(0, progresso))
        barra = f"<div class='progress'><span style='width:{progresso:.1f}%'></span></div>"
    return (
        f"<article class='metric-card {classe}'><span class='metric-label'>{_esc(titulo)}</span>"
        f"<strong class='metric-value'>{_esc(valor)}</strong>"
        f"{barra}<small>{_esc(detalhe)}</small></article>"
    )


def _avaliacoes_docentes_html(avaliacoes: tuple[dict, ...]) -> str:
    if not avaliacoes:
        return ""
    itens: list[str] = []
    for avaliacao in avaliacoes:
        efeito = float(avaliacao.get("efeito_ranking_aplicado") or 0)
        classe = "review-positive" if efeito > 0 else ("review-alert" if efeito < 0 else "review-neutral")
        fonte = "disciplina específica" if avaliacao.get("fonte") == "disciplina" else "avaliação geral"
        score = avaliacao.get("score_0_100")
        score_txt = f"{float(score):.1f}/100" if score is not None else "sem nota"
        itens.append(
            f"<article class='teacher-review-item {classe}'>"
            f"<div class='teacher-review-head'><strong>{_esc(avaliacao.get('professor', 'Docente'))}</strong>"
            f"<span>{efeito:+g}</span></div>"
            f"<div class='teacher-review-badges'>"
            f"{_pill(str(avaliacao.get('classificacao', 'sem classificação')))}"
            f"{_pill('qualidade: ' + str(avaliacao.get('qualidade_pedagogica', 'sem dados')), 'green' if efeito > 0 else '')}"
            f"{_pill('risco: ' + str(avaliacao.get('risco_academico', 'sem dados')), 'gold' if efeito < 0 else '')}"
            f"</div>"
            f"<small>{_esc(fonte)} · {score_txt} · confiança {_esc(avaliacao.get('confianca', 'sem dados'))} · "
            f"{int(avaliacao.get('conceitos') or 0)} conceitos · {int(avaliacao.get('comentarios') or 0)} comentários</small>"
            f"</article>"
        )
    return (
        "<div class='teacher-review'><div class='teacher-review-title'>"
        "<strong>Avaliação docente — UFABC Next</strong>"
        "<span>preferência flexível, não bloqueio</span></div>"
        + "".join(itens) + "</div>"
    )


def _disciplina_cards_html(
    grade: Grade,
    curriculo: dict[str, DisciplinaCurricular],
    concluidas_reais: set[str],
    cumpridas_projetadas: set[str],
) -> str:
    cards: list[str] = []
    for oferta in sorted(grade.ofertas, key=lambda o: (curriculo[o.codigo_curriculo].quadrimestre_recomendado or 99, o.codigo_curriculo)):
        d = curriculo[oferta.codigo_curriculo]
        horarios = "".join(
            f"<li>{_esc(DIAS_NOMES[h.dia].title())}, {minutos_para_hora(h.inicio)}–{minutos_para_hora(h.fim)} "
            f"<span class='muted'>({_esc(h.recorrencia.value.replace('_', ' '))}, {_esc(h.tipo)})</span></li>"
            for h in sorted(oferta.horarios, key=lambda x: (x.dia, x.inicio))
        )
        docentes = ", ".join(oferta.docentes) or "Não informado"
        vagas = "Não informadas"
        if oferta.vagas_totais is not None or oferta.vagas_veteranos is not None:
            vagas = f"total {oferta.vagas_totais if oferta.vagas_totais is not None else '?'} · veteranos {oferta.vagas_veteranos if oferta.vagas_veteranos is not None else '?'}"

        recomendacoes = _recomendacoes_status(d, curriculo, concluidas_reais, cumpridas_projetadas)
        if recomendacoes:
            itens_rec = []
            for codigo_rec, nome_rec, status_rec in recomendacoes:
                classe = "rec-ok" if status_rec == "concluída" else ("rec-projected" if "projeção" in status_rec else "rec-missing")
                simbolo = "✓" if classe == "rec-ok" else ("◐" if classe == "rec-projected" else "!")
                itens_rec.append(
                    f"<li class='{classe}'><strong>{simbolo} {_esc(codigo_rec)}</strong> — {_esc(nome_rec)}"
                    f"<small>{_esc(status_rec)}</small></li>"
                )
            recomendacoes_html = (
                "<div class='recommendations'><strong>Recomendações anteriores do PPC</strong>"
                "<ul>" + "".join(itens_rec) + "</ul></div>"
            )
        else:
            recomendacoes_html = "<div class='recommendations empty-rec'>Sem recomendações anteriores cadastradas.</div>"

        alertas: list[str] = []
        if d.requisito_manual:
            alertas.append("Conferência manual: " + d.requisito_manual)
        alertas_html = "".join(f"<div class='inline-alert'>{_esc(a)}</div>" for a in alertas)
        avaliacoes_html = _avaliacoes_docentes_html(
            grade.avaliacoes_docentes_por_disciplina.get(d.codigo, ())
        )
        cards.append(
            f"<article class='course-card' style='--course:{_cor_disciplina(d.codigo)}'>"
            f"<div class='course-head'><div><span class='course-code'>{_esc(d.codigo)}</span>"
            f"<h4>{_esc(d.nome)}</h4></div><div class='course-badges'>"
            f"{_pill(f'{oferta.creditos} cr', 'green')}{_pill(f'PPC Q{d.quadrimestre_recomendado or "?"}')}</div></div>"
            f"<dl><div><dt>Turma</dt><dd>{_esc(oferta.nome_turma)}</dd></div>"
            f"<div><dt>Docente(s)</dt><dd>{_esc(docentes)}</dd></div>"
            f"<div><dt>T-P-E-I</dt><dd>{oferta.t}-{oferta.p}-{oferta.e}-{oferta.i} · carga ref. {oferta.carga_total_referencia}</dd></div>"
            f"<div><dt>Vagas previstas</dt><dd>{_esc(vagas)}</dd></div></dl>"
            f"<ul class='schedule-list'>{horarios}</ul>{avaliacoes_html}{recomendacoes_html}{alertas_html}</article>"
        )
    return "<div class='course-grid'>" + "".join(cards) + "</div>"


def _grade_card_html(
    grade: Grade,
    curriculo: dict[str, DisciplinaCurricular],
    titulo: str,
    creditos_alvo: int,
    concluidas_reais: set[str],
    cumpridas_projetadas: set[str],
    estimativa_formatura: dict | None = None,
    projecoes_valem_como_cumpridas: bool = True,
    aberta: bool = False,
) -> str:
    m = grade.metricas
    positivos, negativos = _pontos_grade(grade, creditos_alvo, projecoes_valem_como_cumpridas)
    leitura = "".join(f"<li class='positive'>✓ {_esc(x)}</li>" for x in positivos) + "".join(
        f"<li class='negative'>• {_esc(x)}</li>" for x in negativos
    )
    formatura_cards = ""
    formatura_box = ""
    if estimativa_formatura:
        periodo_min = estimativa_formatura.get("periodo_estimado_minimo", "?")
        periodo_pru = estimativa_formatura.get("periodo_estimado_prudente", "?")
        formatura_cards = _metric_card(
            "Previsão de conclusão",
            f"{periodo_min}–{periodo_pru}",
            f"{estimativa_formatura.get('quadrimestres_estimados_incluindo_atual', '?')} a "
            f"{estimativa_formatura.get('quadrimestres_estimados_prudente', '?')} quads incluindo o atual",
            classe="estimated",
        )
        gargalos = "".join(f"<li>{_esc(x)}</li>" for x in estimativa_formatura.get("gargalos", []))
        total_pendente = estimativa_formatura.get(
            "creditos_totais_pendentes_apos_grade",
            estimativa_formatura.get("creditos_pendentes_apos_grade", "?"),
        )
        regular_pendente = estimativa_formatura.get("creditos_regulares_pendentes_apos_grade", "?")
        tg_pendente = estimativa_formatura.get("creditos_tg_pendentes_apos_grade", "?")
        estagio_pendente = estimativa_formatura.get("creditos_estagio_pendentes_apos_grade", "?")
        formatura_box = (
            "<div class='graduation-box'><div><span class='eyebrow'>Projeção de formatura</span>"
            f"<h4>Conclusão estimada entre { _esc(periodo_min) } e { _esc(periodo_pru) }</h4>"
            f"<p>Após esta grade, restariam <strong>{total_pendente} créditos totais</strong>. "
            f"Para o ritmo de {estimativa_formatura.get('ritmo_futuro_creditos_por_quadrimestre', '?')} cr/quadrimestre, "
            f"o cálculo usa <strong>{regular_pendente} créditos de carga regular</strong>; "
            f"TG ({tg_pendente} cr) e estágio ({estagio_pendente} cr) são tratados como atividades paralelas.</p></div>"
            f"<ul>{gargalos or '<li>Nenhum gargalo adicional estruturado.</li>'}</ul>"
            f"<small>{_esc(estimativa_formatura.get('observacao', ''))}</small></div>"
        )
    metricas = "".join([
        _metric_card("Créditos", str(m.creditos_totais), f"alvo: {creditos_alvo}", m.creditos_totais / max(1, creditos_alvo) * 100),
        _metric_card("Dias com aula", str(m.dias_com_aula), f"{m.dias_com_jornada_parcial} com jornada parcial"),
        _metric_card("Janelas internas", _fmt_duracao(m.buracos_minutos), "entre duas aulas do mesmo dia", classe="success" if m.buracos_minutos == 0 else "warning"),
        _metric_card("Blocos livres nas bordas", _fmt_duracao(m.tempo_livre_extremidades_minutos), "antes da primeira ou após a última aula"),
        _metric_card("Tempo em aula", _fmt_duracao(m.tempo_em_aula_minutos), f"permanência: {_fmt_duracao(m.permanencia_total_minutos)}"),
        _metric_card("Carga de referência", str(m.carga_total_referencia), f"T-P-E-I {m.carga_teorica}-{m.carga_pratica}-{m.carga_extensao}-{m.carga_individual}"),
        _metric_card("Progressão", str(m.atraso_curricular_total), f"{m.disciplinas_totalmente_destravadas} totalmente destravadas · {m.pendencias_futuras_impactadas} impactadas"),
        _metric_card("Recomendações", str(m.recomendacoes_faltantes), f"{m.dependencias_em_andamento} atendidas por projeção"),
        _metric_card(
            "Avaliação docente",
            f"{m.ajuste_avaliacao_docente:+g}",
            f"{m.docentes_avaliados} avaliados · {m.docentes_favoraveis} favoráveis · {m.docentes_alerta} alertas",
            classe="success" if m.ajuste_avaliacao_docente > 0 else ("warning" if m.ajuste_avaliacao_docente < 0 else ""),
        ),
        formatura_cards,
    ])
    chips = (
        _pill(f"{m.creditos_obrigatorios} cr obrigatórios", "green")
        + _pill(f"{m.creditos_opcao_limitada} cr opção limitada")
        + _pill(f"{m.disciplinas_praticas} prática(s)")
        + (_pill(f"mín. {m.vagas_veteranos_minimas} vagas veteranos", "gold") if m.vagas_veteranos_minimas is not None else "")
    )
    return (
        f"<details class='grade-card' {'open' if aberta else ''}><summary>"
        f"<div><span class='eyebrow'>Alternativa de matrícula</span><h3>{_esc(titulo)}</h3>"
        f"<div class='chips'>{chips}</div></div><span class='open-label'>Ver detalhes</span></summary>"
        f"<div class='grade-content'><div class='metrics-grid'>{metricas}</div>{formatura_box}"
        f"<h4 class='section-subtitle'>Disciplinas e turmas</h4>{_disciplina_cards_html(grade, curriculo, concluidas_reais, cumpridas_projetadas)}"
        f"<h4 class='section-subtitle'>Grade semanal</h4>{_grade_schedule_html(grade, curriculo)}"
        f"<div class='reading'><h4>Leitura da opção</h4><ul>{leitura}</ul></div></div></details>"
    )


def _progress_percent(integralizado: int | float, exigido: int | float) -> float:
    return (float(integralizado) / float(exigido) * 100) if exigido else 0


def gerar_relatorio_html(
    caminho: str | Path,
    metadados: dict,
    curriculo: dict[str, DisciplinaCurricular],
    situacao: SituacaoAcademica,
    cumpridas_projetadas: set[str],
    resultado: ResultadoPlanejamento,
    auditoria: dict,
    avisos_ofertas: list[str],
    modo_projecao: str,
    quadrimestre_planejado: int | None,
    periodo_planejamento: str,
    creditos_alvo: int,
    frequencias: dict[str, dict[str, float | int]],
    analise_desempenho: dict,
    estimativas_formatura: dict[str, dict],
    validacao_busca: dict,
    projecoes_valem_como_cumpridas: bool,
) -> None:
    cat = auditoria["por_categoria"]
    sigaa = auditoria.get("sigaa_vinculo_atual", {})

    sigaa_cards: list[str] = []
    for chave, rotulo in (
        ("obrigatorias", "Obrigatórias"),
        ("optativos", "Optativos"),
        ("livres", "Livres"),
        ("complementares", "Complementares"),
        ("total", "Carga total"),
    ):
        d = sigaa.get(chave, {})
        if not d:
            continue
        sigaa_cards.append(_metric_card(
            rotulo,
            f"{d['integralizado_horas']} / {d['exigido_horas']} h",
            f"faltam {d['pendente_horas']} h · quadro oficial do vínculo atual",
            _progress_percent(d["integralizado_horas"], d["exigido_horas"]),
        ))

    obrig = cat["obrigatoria"]
    ol = cat["opcao_limitada"]
    livre = cat["livre"]
    engenharia_cards = [
        _metric_card(
            "Obrigatórios — projeção",
            f"{obrig['integralizado_estimado']} / {obrig['exigido']} cr",
            f"{obrig['integralizado_confirmado']} cr confirmados no histórico · "
            f"{obrig['pendente_estimado']} cr pendentes na projeção",
            _progress_percent(obrig["integralizado_estimado"], obrig["exigido"]),
            "estimated" if obrig['integralizado_estimado'] != obrig['integralizado_confirmado'] else "",
        ),
        _metric_card(
            "Opção limitada — projeção",
            f"{ol['integralizado_estimado']} / {ol['exigido']} cr",
            f"{ol['integralizado_confirmado']} cr confirmados na lista da Engenharia 2017",
            _progress_percent(ol["integralizado_estimado"], ol["exigido"]),
            "estimated" if ol['integralizado_estimado'] != ol['integralizado_confirmado'] else "",
        ),
        _metric_card(
            "Livres — estimativa",
            f"{livre['integralizado_estimado']} / {livre['exigido']} cr",
            f"{livre['integralizado_confirmado']} direto(s) + {auditoria['livres_estimados_adicionais']} potencial(is)",
            _progress_percent(livre["integralizado_estimado"], livre["exigido"]),
            "estimated",
        ),
        _metric_card(
            "Componentes reconhecidos",
            str(auditoria.get("componentes_curriculo_concluidos_projetados", auditoria["componentes_curriculo_concluidos"])),
            f"{auditoria.get('componentes_curriculo_concluidos_confirmados', auditoria['componentes_curriculo_concluidos'])} confirmados · "
            f"{auditoria['componentes_historico_concluidos']} componentes concluídos no histórico",
        ),
    ]

    grades_html = "".join(
        _grade_card_html(
            grade, curriculo, f"Opção padrão {indice}", creditos_alvo,
            situacao.concluidas, cumpridas_projetadas,
            estimativas_formatura.get(_grade_chave(grade), {}),
            projecoes_valem_como_cumpridas, aberta=(indice == 1)
        )
        for indice, grade in enumerate(resultado.grades_padrao, start=1)
    ) or "<div class='empty'>Nenhuma grade viável foi encontrada.</div>"

    perfis_html = "".join(
        _grade_card_html(
            grade, curriculo, PERFIS_ROTULOS[perfil], creditos_alvo,
            situacao.concluidas, cumpridas_projetadas,
            estimativas_formatura.get(_grade_chave(grade), {}),
            projecoes_valem_como_cumpridas
        )
        for perfil, grade in resultado.grades_por_perfil.items()
    ) or "<p class='muted'>Nenhuma alternativa adicional foi gerada.</p>"

    pendentes_obrigatorias = [
        d for d in curriculo.values()
        if d.categoria == Categoria.OBRIGATORIA and d.codigo not in cumpridas_projetadas
    ]
    pendencias_rows: list[str] = []
    for d in sorted(pendentes_obrigatorias, key=lambda x: (x.quadrimestre_recomendado or 99, x.codigo)):
        atraso = max(0, (quadrimestre_planejado or 0) - (d.quadrimestre_recomendado or (quadrimestre_planejado or 0)))
        diag = resultado.diagnosticos.get(d.codigo)
        motivo = "; ".join(diag.motivos) if diag and diag.motivos else "Elegível para análise curricular"
        pendencias_rows.append(
            f"<tr><td>{_esc(d.codigo)}</td><td>{_esc(d.nome)}</td><td>Q{d.quadrimestre_recomendado or '?'}</td>"
            f"<td>{d.creditos}</td><td>{atraso}Q</td><td>{_esc(motivo)}</td></tr>"
        )

    especiais_cards_lista = []
    for tipo, rotulo in (
        ("engenharia_unificada", "Engenharia Unificada"),
        ("trabalho_graduacao", "Trabalho de Graduação"),
        ("estagio", "Estágio curricular"),
    ):
        dados_especial = auditoria["especiais"][tipo]
        detalhe = (
            f"{dados_especial.get('integralizado_confirmado', dados_especial['integralizado'])} cr confirmados · "
            f"Pendentes na projeção: "
            f"{', '.join(dados_especial.get('pendentes_projetados', dados_especial['pendentes'])) or 'nenhum'}"
        )
        if tipo == "estagio":
            status = dados_especial.get("status_informado", "nao_iniciado")
            detalhe += " · " + ESTAGIO_STATUS_ROTULOS.get(status, status)
        especiais_cards_lista.append(_metric_card(
            rotulo,
            f"{dados_especial.get('integralizado_projetado', dados_especial['integralizado'])} / {dados_especial['exigido']} cr",
            detalhe,
            _progress_percent(
                dados_especial.get('integralizado_projetado', dados_especial['integralizado']),
                dados_especial['exigido'],
            ),
            "estimated" if dados_especial.get('integralizado_projetado', 0) != dados_especial.get('integralizado_confirmado', 0) else "",
        ))
    especiais_cards = "".join(especiais_cards_lista)

    andamento_items = "".join(
        f"<li>{_esc(curriculo[c].nome if c in curriculo else c)} <span>{_esc(c)}</span></li>"
        for c in sorted(situacao.em_andamento)
    ) or "<li>Nenhuma disciplina em andamento identificada.</li>"

    reservas_html = ""
    if resultado.grades_reserva and resultado.grade_principal:
        reservas_html = "<div class='list-cards'>" + "".join(
            f"<article><strong>Sem {_esc(codigo)}</strong><p>{_esc(', '.join(grade.assinatura_disciplinas))}</p></article>"
            for codigo, grade in resultado.grades_reserva
        ) + "</div>"

    cenarios_html = "".join(
        f"<article class='scenario'><h4>{_esc(c.nome)}</h4>"
        f"<strong>{c.pendentes_obrigatorias} obrigatórias pendentes</strong>"
        f"<p>{_esc(', '.join(c.melhor_grade.assinatura_disciplinas) if c.melhor_grade else 'Nenhuma grade encontrada')}</p></article>"
        for c in resultado.cenarios
    )

    futuro_html = "".join(
        f"<article class='timeline-item'><span>Q{plano.indice or '?'}</span><div><h4>{_esc(plano.rotulo)}</h4>"
        f"<p><strong>{plano.creditos} cr</strong> · {_esc(_nomes_codigos(plano.codigos, curriculo))}</p>"
        f"<small>{_esc(plano.observacao)}</small></div></article>"
        for plano in resultado.planos_futuros
    )

    ol_pendentes = [
        d for d in curriculo.values()
        if d.categoria == Categoria.OPCAO_LIMITADA and d.codigo not in cumpridas_projetadas
    ]
    ol_html = "".join(
        f"<article class='option-card'><span>{_esc(d.codigo)}</span><h4>{_esc(d.nome)}</h4>"
        f"<p>{d.creditos} cr · {', '.join(classificar_area_formacao(d))}</p></article>"
        for d in sorted(ol_pendentes, key=lambda x: (x.quadrimestre_recomendado or 99, x.nome))
    )

    avisos = list(dict.fromkeys(list(avisos_ofertas) + list(resultado.avisos)))
    avisos_html = "".join(f"<li>{_esc(a)}</li>" for a in avisos) or "<li>Nenhum aviso técnico adicional.</li>"

    avaliacoes_unicas: dict[tuple[str, str, str], dict] = {}
    grades_com_avaliacoes = list(resultado.grades_padrao) + list(resultado.grades_por_perfil.values())
    for grade in grades_com_avaliacoes:
        for codigo, avaliacoes in grade.avaliacoes_docentes_por_disciplina.items():
            for avaliacao in avaliacoes:
                chave = (
                    str(avaliacao.get("professor", "")),
                    codigo,
                    str(avaliacao.get("fonte", "")),
                )
                avaliacoes_unicas[chave] = avaliacao
    avaliacoes_rows = "".join(
        f"<tr><td>{_esc(professor)}</td><td>{_esc(codigo)}</td>"
        f"<td>{_esc(av.get('classificacao', 'sem classificação'))}</td>"
        f"<td>{_esc(av.get('qualidade_pedagogica', 'sem dados'))}</td>"
        f"<td>{_esc(av.get('risco_academico', 'sem dados'))}</td>"
        f"<td>{int(av.get('conceitos') or 0)}</td><td>{int(av.get('comentarios') or 0)}</td>"
        f"<td>{float(av.get('efeito_ranking_aplicado') or 0):+g}</td></tr>"
        for (professor, codigo, _), av in sorted(avaliacoes_unicas.items())
    ) or "<tr><td colspan='8'>Nenhuma avaliação docente foi associada às grades apresentadas.</td></tr>"

    livres_componentes = auditoria.get("componentes_livres_potenciais", [])
    livres_html = "".join(
        f"<tr><td>{_esc(item['codigo'])}</td><td>{_esc(item['nome'])}</td><td>{item['creditos']}</td></tr>"
        for item in livres_componentes
    ) or "<tr><td colspan='3'>Nenhum componente potencial identificado.</td></tr>"

    documento = f"""<!doctype html>
<html lang='pt-BR'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Planejador de Matrícula UFABC</title>
<style>
:root{{--green-900:#153f31;--green-800:#1f5b45;--green-700:#287358;--green-100:#e8f3ed;--ink:#17211c;--muted:#607068;--line:#dce5df;--surface:#fff;--bg:#f3f6f4;--gold:#b98716;--danger:#9f3a38;}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:var(--bg);color:var(--ink);line-height:1.5}}
a{{color:inherit}}header{{background:linear-gradient(135deg,var(--green-900),var(--green-700));color:white;padding:38px max(24px,calc((100vw - 1240px)/2));position:relative;overflow:hidden}}header:after{{content:"";position:absolute;width:380px;height:380px;border-radius:50%;background:#ffffff12;right:-120px;top:-220px}}header h1{{font-size:clamp(1.8rem,4vw,2.8rem);margin:0 0 8px;letter-spacing:-.03em}}header p{{margin:0;color:#e4f1eb}}nav{{position:sticky;top:0;z-index:20;background:#ffffffee;backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}}nav .nav-inner{{max-width:1240px;margin:auto;padding:10px 24px;display:flex;gap:8px;overflow:auto}}nav a{{text-decoration:none;white-space:nowrap;padding:8px 12px;border-radius:999px;font-size:.9rem;color:#395047}}nav a:hover{{background:var(--green-100)}}main{{max-width:1240px;margin:auto;padding:28px 24px 70px}}section{{scroll-margin-top:72px;margin:34px 0}}.section-heading{{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:16px}}.section-heading h2{{margin:0;font-size:1.55rem;letter-spacing:-.02em}}.section-heading p{{margin:5px 0 0;color:var(--muted);max-width:760px}}.notice{{background:#fff8dc;border:1px solid #ecdca3;border-left:5px solid var(--gold);padding:16px 18px;border-radius:10px;margin-bottom:26px}}.metrics-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}.metric-card{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 7px 25px #203c2c0b;min-height:120px;display:flex;flex-direction:column;gap:6px}}.metric-label{{font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700}}.metric-value{{font-size:1.45rem;letter-spacing:-.03em}}.metric-card small{{color:var(--muted)}}.metric-card.estimated{{border-style:dashed}}.progress{{height:6px;background:#edf1ef;border-radius:999px;overflow:hidden;margin-top:auto}}.progress span{{display:block;height:100%;background:var(--green-700);border-radius:999px}}.compare-note{{background:#eaf2ff;border:1px solid #c6daf8;border-radius:12px;padding:15px;margin:14px 0;color:#304863}}.grade-card{{background:var(--surface);border:1px solid var(--line);border-radius:18px;margin:16px 0;box-shadow:0 12px 35px #173f2e0a;overflow:hidden}}.grade-card summary{{list-style:none;cursor:pointer;padding:22px;display:flex;align-items:center;justify-content:space-between;gap:20px}}.grade-card summary::-webkit-details-marker{{display:none}}.grade-card[open] summary{{border-bottom:1px solid var(--line)}}.grade-card h3{{margin:2px 0 8px;font-size:1.35rem}}.eyebrow{{text-transform:uppercase;font-size:.72rem;letter-spacing:.1em;color:var(--green-700);font-weight:800}}.open-label{{font-size:.85rem;color:var(--green-700);font-weight:700}}.chips{{display:flex;gap:6px;flex-wrap:wrap}}.pill{{display:inline-flex;background:#eef2f0;border-radius:999px;padding:4px 9px;font-size:.76rem;font-weight:700;color:#52635b}}.pill.green{{background:#e1f3e8;color:#246242}}.pill.gold{{background:#fff3cc;color:#775a0c}}.grade-content{{padding:22px}}.section-subtitle{{font-size:1.1rem;margin:28px 0 12px}}.course-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}.course-card{{background:linear-gradient(90deg,var(--course) 0 7px,#fff 7px);border:1px solid var(--line);border-radius:13px;padding:16px 16px 14px 22px}}.course-head{{display:flex;justify-content:space-between;gap:12px;align-items:start}}.course-card h4{{margin:3px 0 12px;font-size:1rem}}.course-code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.78rem;color:var(--muted);font-weight:700}}.course-badges{{display:flex;gap:5px;flex-wrap:wrap;justify-content:end}}dl{{margin:0;display:grid;gap:7px}}dl div{{display:grid;grid-template-columns:92px 1fr;gap:8px;font-size:.86rem}}dt{{font-weight:700;color:#4e5e56}}dd{{margin:0}}.schedule-list{{padding-left:18px;font-size:.87rem}}.inline-alert{{background:#fff4e7;border-radius:8px;padding:8px 10px;font-size:.82rem;margin-top:7px;color:#6e4b1a}}.schedule-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px}}.schedule{{width:100%;border-collapse:collapse;table-layout:fixed;min-width:760px}}.schedule th,.schedule td{{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:8px;vertical-align:middle;text-align:center}}.schedule thead th{{background:#edf4f0;font-size:.82rem}}.schedule .time{{background:#f7f9f8;width:115px;font-size:.8rem}}.schedule-course{{border-radius:9px;padding:8px;display:flex;flex-direction:column;gap:2px;min-height:72px;justify-content:center}}.schedule-course span{{font-size:.72rem;line-height:1.2}}.schedule-course small{{font-size:.68rem;color:#516057}}.free-cell{{background:repeating-linear-gradient(135deg,#fafcfb,#fafcfb 8px,#f5f8f6 8px,#f5f8f6 16px);color:#9aa6a0;font-size:.75rem}}.schedule-note{{font-size:.84rem;color:var(--muted);background:#f6f8f7;border-radius:9px;padding:10px 12px;margin-top:9px}}.reading{{background:#f7faf8;border:1px solid var(--line);border-radius:12px;padding:16px;margin-top:18px}}.reading h4{{margin:0 0 8px}}.reading ul{{margin:0;padding-left:20px}}.positive{{color:#285f43}}.negative{{color:#6a5047}}.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px;background:white}}.data-table{{border-collapse:collapse;width:100%;min-width:800px}}.data-table th,.data-table td{{padding:11px 13px;border-bottom:1px solid var(--line);text-align:left;font-size:.85rem}}.data-table th{{background:#edf4f0;position:sticky;top:0}}.list-cards,.scenarios,.options-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}.list-cards article,.scenario,.option-card{{background:white;border:1px solid var(--line);border-radius:12px;padding:15px}}.list-cards p,.scenario p,.option-card p{{color:var(--muted);margin-bottom:0;font-size:.86rem}}.option-card span{{font-family:ui-monospace,monospace;color:var(--green-700);font-weight:700;font-size:.78rem}}.option-card h4{{margin:5px 0}}.timeline{{display:grid;gap:10px}}.timeline-item{{display:grid;grid-template-columns:58px 1fr;gap:14px;background:white;border:1px solid var(--line);border-radius:12px;padding:14px}}.timeline-item>span{{width:48px;height:48px;border-radius:50%;background:var(--green-100);display:grid;place-items:center;font-weight:800;color:var(--green-700)}}.timeline-item h4,.timeline-item p{{margin:0 0 4px}}.muted{{color:var(--muted)}}.empty{{padding:25px;background:white;border:1px dashed var(--line);border-radius:12px;color:var(--muted)}}.warning-list{{background:white;border:1px solid var(--line);border-radius:12px;padding:18px 18px 18px 38px}}details.simple{{background:white;border:1px solid var(--line);border-radius:12px;margin:10px 0;padding:14px}}details.simple summary{{cursor:pointer;font-weight:700}}
.recommendations{{margin-top:12px;padding:11px 12px;border-radius:10px;background:#f5f8f6;border:1px solid var(--line);font-size:.82rem}}.recommendations>strong{{display:block;margin-bottom:6px}}.recommendations ul{{list-style:none;padding:0;margin:0;display:grid;gap:6px}}.recommendations li{{display:flex;gap:5px;flex-wrap:wrap}}.recommendations li small{{display:block;width:100%;padding-left:20px;color:var(--muted)}}.rec-ok strong{{color:#207249}}.rec-projected strong{{color:#8a650d}}.rec-missing strong{{color:var(--danger)}}.empty-rec{{color:var(--muted)}}
.graduation-box{{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;background:linear-gradient(135deg,#edf7f1,#fff8dc);border:1px solid #cfe0d6;border-radius:14px;padding:18px;margin:18px 0}}.graduation-box h4{{font-size:1.15rem;margin:4px 0 6px}}.graduation-box p,.graduation-box ul{{margin:0}}.graduation-box small{{grid-column:1/-1;color:var(--muted)}}
.search-certificate{{background:white;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 12px 35px #173f2e0a}}.certificate-ok{{border-left:7px solid #2f8f5b}}.certificate-warning{{border-left:7px solid var(--gold)}}.certificate-head{{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:16px}}.certificate-head h3{{margin:3px 0}}.certificate-head p{{margin:0;color:var(--muted)}}.certificate-seal{{width:54px;height:54px;border-radius:50%;display:grid;place-items:center;background:var(--green-100);font-size:1.6rem;color:var(--green-700);font-weight:900}}
.analytics-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:16px 0}}.chart-card{{background:white;border:1px solid var(--line);border-radius:15px;padding:18px;box-shadow:0 8px 25px #173f2e08}}.chart-card h3{{margin:0 0 14px}}.chart-card.wide{{margin-top:14px}}.donut{{--pct:0;width:170px;height:170px;border-radius:50%;margin:14px auto;background:conic-gradient(var(--green-700) calc(var(--pct)*1%),#e7ede9 0);position:relative;display:grid;place-items:center}}.donut:after{{content:"";position:absolute;inset:23px;background:white;border-radius:50%}}.donut span{{position:relative;z-index:1;font-size:1.55rem;font-weight:800}}.concept-row{{display:grid;grid-template-columns:24px 1fr 30px;gap:9px;align-items:center;margin:9px 0}}.concept-track,.period-track{{height:12px;background:#edf1ef;border-radius:999px;overflow:hidden;display:flex}}.concept-track span{{display:block;height:100%;background:linear-gradient(90deg,var(--green-700),#76a98e)}}.concept-row em{{font-style:normal;text-align:right}}.period-chart{{display:grid;gap:10px}}.period-row{{display:grid;grid-template-columns:64px 1fr 120px;gap:10px;align-items:center}}.period-track i{{height:100%;display:block}}.period-track .approved{{background:#3b8f64}}.period-track .failed{{background:#c96b63}}.period-row small{{color:var(--muted)}}.legend{{display:flex;gap:16px;font-size:.82rem;color:var(--muted);margin-bottom:12px}}.legend span:before{{content:"";display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}}.leg-approved:before{{background:#3b8f64}}.leg-failed:before{{background:#c96b63}}.recovery-list span{{color:var(--muted);font-size:.82rem}}
footer{{color:var(--muted);font-size:.82rem;padding-top:28px;border-top:1px solid var(--line)}}
@media(max-width:700px){{header{{padding:28px 20px}}main{{padding:20px 14px 50px}}.grade-card summary{{align-items:flex-start}}.open-label{{display:none}}.grade-content{{padding:14px}}dl div{{grid-template-columns:1fr}}.graduation-box{{grid-template-columns:1fr}}.period-row{{grid-template-columns:54px 1fr}}.period-row small{{grid-column:2}}}}
.teacher-review{{margin:14px 0;padding:12px;border:1px solid #dbe5e0;border-radius:12px;background:#f8fbf9}}.teacher-review-title{{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px}}.teacher-review-title span{{font-size:12px;color:#607068}}.teacher-review-item{{border-left:4px solid #94a3b8;padding:9px 11px;margin-top:8px;background:white;border-radius:8px}}.teacher-review-item.review-positive{{border-left-color:#2f855a}}.teacher-review-item.review-alert{{border-left-color:#c2410c}}.teacher-review-item.review-neutral{{border-left-color:#64748b}}.teacher-review-head{{display:flex;justify-content:space-between;gap:12px}}.teacher-review-head span{{font-weight:800}}.teacher-review-badges{{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0}}.teacher-review small{{color:#607068}}.empty-rec.teacher-review{{color:#607068;font-size:13px}}</style>
</head>
<body>
<header><h1>Planejador de Matrícula — UFABC</h1>
<p>{_esc(metadados.get('curso',''))} · Matriz {_esc(metadados.get('versao',''))} · {_esc(periodo_planejamento or 'período não informado')} · Q{quadrimestre_planejado or '?'}</p></header>
<nav><div class='nav-inner'><a href='#validacao'>Validação</a><a href='#desempenho'>Desempenho</a><a href='#integralizacao'>Integralização</a><a href='#docentes'>Docentes</a><a href='#grades'>Grades</a><a href='#alternativas'>Alternativas</a><a href='#planejamento'>Planejamento</a><a href='#pendencias'>Pendências</a><a href='#avisos'>Avisos</a></div></nav>
<main>
<div class='notice'><strong>Apoio à decisão:</strong> as categorias do vínculo atual e da matriz selecionada são apresentadas separadamente. Vagas, projeções e ofertas futuras não são garantias.</div>
<section id='validacao'><div class='section-heading'><div><h2>Validação da busca</h2><p>Indica se todas as combinações viáveis dentro dos filtros foram percorridas ou se algum limite técnico restringiu a busca.</p></div></div>{_validacao_html(validacao_busca)}</section>
<section id='desempenho'><div class='section-heading'><div><h2>Análise do histórico acadêmico</h2><p>Aprovações, reprovações, conceitos e evolução por quadrimestre. Dispensas e transferências são mostradas separadamente.</p></div></div>{_desempenho_html(analise_desempenho)}</section>
<section id='integralizacao'><div class='section-heading'><div><h2>Integralização acadêmica</h2><p>Primeiro, o quadro oficial impresso no histórico do vínculo atual. Depois, a reclassificação estimada para a matriz selecionada.</p></div></div>
<h3>Histórico oficial do vínculo atual</h3><div class='metrics-grid'>{''.join(sigaa_cards)}</div>
<div class='compare-note'><strong>Por que os números mudam?</strong> {_esc(auditoria.get('observacao_categorias',''))} O histórico mostra, por exemplo, optativos e livres do BC&T. A matriz selecionada pode reclassificar parte desses componentes como obrigatórios.</div>
<h3>Estimativa — {_esc(metadados.get('curso', 'matriz selecionada'))} {_esc(metadados.get('versao', ''))}</h3><div class='metrics-grid'>{''.join(engenharia_cards)}</div>
<details class='simple'><summary>Ver componentes usados como potenciais créditos livres</summary><div class='table-wrap'><table class='data-table'><thead><tr><th>Código</th><th>Componente</th><th>Créditos</th></tr></thead><tbody>{livres_html}</tbody></table></div><p class='muted'>A confirmação final depende do SIGAA e da coordenação. O sistema encontrou {auditoria['livres_potenciais_fora_da_matriz']} créditos fora das listas explícitas e alocou provisoriamente até o limite de {livre['exigido']} créditos livres.</p></details>
<h3>Atividades especiais</h3><div class='metrics-grid'>{especiais_cards}{_metric_card('Atividades complementares', f"{_fmt_numero(auditoria.get('atividades_complementares_horas') or 0)} h", 'valor lido do histórico')}</div>
</section>
<section id='docentes'><div class='section-heading'><div><h2>Avaliações docentes utilizadas</h2><p>A avaliação da disciplina específica tem prioridade sobre a avaliação geral. Qualidade pedagógica e risco acadêmico são exibidos separadamente; o efeito é flexível e nunca elimina automaticamente uma turma.</p></div></div><div class='table-wrap'><table class='data-table'><thead><tr><th>Docente</th><th>Disciplina</th><th>Recomendação</th><th>Qualidade</th><th>Risco</th><th>Conceitos</th><th>Comentários</th><th>Efeito</th></tr></thead><tbody>{avaliacoes_rows}</tbody></table></div><div class='compare-note'><strong>Interpretação:</strong> uma avaliação pedagógica favorável pode coexistir com risco acadêmico alto quando a disciplina é historicamente exigente. O ranking prioriza progressão curricular e usa o docente para desempatar ou reordenar alternativas academicamente semelhantes.</div></section>
<section><div class='section-heading'><div><h2>Situação atual</h2><p>Projeção selecionada: <strong>{_esc(modo_projecao)}</strong>. {'Disciplinas em andamento presumidas aprovadas são tratadas como recomendações cumpridas no ranking.' if projecoes_valem_como_cumpridas else 'Aprovações projetadas recebem penalidade de risco no ranking.'} Há {len(pendentes_obrigatorias)} obrigatórias pendentes no cenário utilizado.</p></div></div><div class='metrics-grid'>{_metric_card('Em andamento', str(len(situacao.em_andamento)), 'componentes matriculados ou em recuperação')}{_metric_card('Pendências obrigatórias', str(len(pendentes_obrigatorias)), 'inclui atividades especiais')}{_metric_card('Opções padrão', str(len(resultado.grades_padrao)), 'mínimo desejado: 3')}{_metric_card('Carga-alvo', f'{creditos_alvo} cr', 'usada no ranking')}</div><details class='simple'><summary>Ver disciplinas em andamento</summary><ul>{andamento_items}</ul></details></section>
<section id='grades'><div class='section-heading'><div><h2>Grades padrão</h2><p>O modelo original foi preservado: o sistema tenta apresentar cinco opções e nunca menos de três quando existirem combinações viáveis.</p></div></div>{grades_html}</section>
<section id='alternativas'><div class='section-heading'><div><h2>Alternativas por objetivo</h2><p>Opções especializadas para progressão, compactação, equilíbrio, menor carga, maior avanço e menor risco.</p></div></div>{perfis_html}</section>
<section><div class='section-heading'><div><h2>Plano principal e reservas</h2><p>Substituições sugeridas caso uma disciplina do plano principal não seja obtida.</p></div></div>{reservas_html or '<p class="muted">Nenhuma reserva adicional foi gerada.</p>'}</section>
<section><div class='section-heading'><div><h2>Cenários de aprovação</h2><p>Comparação entre projeção conservadora, personalizada e otimista.</p></div></div><div class='scenarios'>{cenarios_html or '<p class="muted">Cenários comparativos desativados.</p>'}</div></section>
<section id='planejamento'><div class='section-heading'><div><h2>Planejamento multiquadrimestral</h2><p>Somente o primeiro quadrimestre usa ofertas e horários reais; os seguintes são projeções curriculares.</p></div></div><div class='timeline'>{futuro_html or '<p class="muted">Planejamento futuro desativado.</p>'}</div></section>
<section><div class='section-heading'><div><h2>Opções limitadas e áreas de formação</h2><p>Disciplinas ainda pendentes na lista de opção limitada da matriz selecionada.</p></div></div><div class='options-grid'>{ol_html or '<p class="muted">Nenhuma opção limitada pendente.</p>'}</div></section>
<section id='pendencias'><div class='section-heading'><div><h2>Pendências e diagnóstico</h2><p>Quadrimestre do PPC, atraso aproximado e motivo de presença ou ausência nas combinações.</p></div></div><div class='table-wrap'><table class='data-table'><thead><tr><th>Código</th><th>Disciplina</th><th>PPC</th><th>Cr.</th><th>Atraso</th><th>Diagnóstico</th></tr></thead><tbody>{''.join(pendencias_rows)}</tbody></table></div></section>
<section id='avisos'><div class='section-heading'><div><h2>Avisos e conferências</h2><p>Itens que merecem validação manual antes da matrícula.</p></div></div><ul class='warning-list'>{avisos_html}</ul></section>
<footer>Processamento local. O relatório não reproduz CPF, RG ou outros dados pessoais. Confirme no SIGAA as regras de matrícula, equivalências, estágio e Trabalho de Graduação.</footer>
</main></body></html>"""
    Path(caminho).write_text(documento, encoding="utf-8")
