from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from .academico import proximo_periodo
from .historico import STATUS_CONCLUIDOS, STATUS_EM_ANDAMENTO, STATUS_NAO_CONCLUIDOS
from .modelos import Categoria, DisciplinaCurricular, Grade, SituacaoAcademica, TipoComponente

CONCEITO_PONTOS = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0, "O": 0}
STATUS_APROVACAO_ACADEMICA = {"APR", "APRN"}
STATUS_REPROVACAO = {"REP", "REPF", "REPMF", "REPN", "REPNF"}
STATUS_APROVEITAMENTO = {"DISP", "TRANS", "INCORP", "CUMP"}


def _periodo_chave(periodo: str) -> tuple[int, int]:
    try:
        ano, quad = periodo.split(".", 1)
        return int(ano), int(quad)
    except (ValueError, AttributeError):
        return 9999, 9


def analisar_desempenho_historico(situacao: SituacaoAcademica) -> dict[str, Any]:
    """Produz métricas descritivas sem reinterpretar os coeficientes oficiais.

    A taxa de aprovação considera somente tentativas acadêmicas com resultado de
    aprovação/reprovação. Dispensas e transferências são apresentadas à parte.
    """
    registros = [r for tentativas in situacao.tentativas.values() for r in tentativas]
    aprovacoes = [r for r in registros if r.situacao in STATUS_APROVACAO_ACADEMICA]
    reprovacoes = [r for r in registros if r.situacao in STATUS_REPROVACAO]
    aproveitamentos = [r for r in registros if r.situacao in STATUS_APROVEITAMENTO]
    em_andamento = [r for r in registros if r.situacao in STATUS_EM_ANDAMENTO]

    tentativas_avaliadas = len(aprovacoes) + len(reprovacoes)
    taxa_aprovacao = (len(aprovacoes) / tentativas_avaliadas * 100) if tentativas_avaliadas else 0.0

    conceitos = Counter()
    for registro in aprovacoes + reprovacoes:
        conceito = (registro.conceito or "").strip().upper()
        if conceito in CONCEITO_PONTOS:
            conceitos[conceito] += 1

    por_periodo: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "aprovacoes": 0,
            "reprovacoes": 0,
            "aproveitamentos": 0,
            "em_andamento": 0,
            "creditos_aprovados": 0,
            "indices_conceito": [],
        }
    )
    for registro in registros:
        if not registro.periodo:
            continue
        dados = por_periodo[registro.periodo]
        if registro.situacao in STATUS_APROVACAO_ACADEMICA:
            dados["aprovacoes"] += 1
            dados["creditos_aprovados"] += registro.creditos
        elif registro.situacao in STATUS_REPROVACAO:
            dados["reprovacoes"] += 1
        elif registro.situacao in STATUS_APROVEITAMENTO:
            dados["aproveitamentos"] += 1
        elif registro.situacao in STATUS_EM_ANDAMENTO:
            dados["em_andamento"] += 1
        conceito = (registro.conceito or "").strip().upper()
        if conceito in CONCEITO_PONTOS:
            dados["indices_conceito"].append(CONCEITO_PONTOS[conceito])

    periodos = []
    for periodo in sorted(por_periodo, key=_periodo_chave):
        dados = por_periodo[periodo]
        indices = dados.pop("indices_conceito")
        dados["indice_medio_conceito"] = (
            round(sum(indices) / len(indices), 2) if indices else None
        )
        periodos.append({"periodo": periodo, **dados})

    recuperadas = []
    for codigo, tentativas in situacao.tentativas.items():
        teve_reprovacao = any(t.situacao in STATUS_REPROVACAO for t in tentativas)
        aprovacao_posterior = any(t.situacao in STATUS_CONCLUIDOS for t in tentativas)
        if teve_reprovacao and aprovacao_posterior:
            nome = next((t.nome for t in reversed(tentativas) if t.nome), codigo)
            recuperadas.append({"codigo": codigo, "nome": nome, "tentativas": len(tentativas)})

    media_indice = None
    total_conceitos = sum(conceitos.values())
    if total_conceitos:
        media_indice = round(
            sum(CONCEITO_PONTOS[c] * n for c, n in conceitos.items()) / total_conceitos,
            2,
        )

    return {
        "tentativas_avaliadas": tentativas_avaliadas,
        "aprovacoes": len(aprovacoes),
        "reprovacoes": len(reprovacoes),
        "taxa_aprovacao_percentual": round(taxa_aprovacao, 1),
        "aproveitamentos_dispensas": len(aproveitamentos),
        "em_andamento": len(em_andamento),
        "creditos_aprovados_em_turmas": sum(r.creditos for r in aprovacoes),
        "creditos_aproveitados": sum(r.creditos for r in aproveitamentos),
        "distribuicao_conceitos": {c: conceitos.get(c, 0) for c in ("A", "B", "C", "D", "F", "O")},
        "indice_medio_conceitos": media_indice,
        "coeficientes_oficiais": dict(situacao.resumo.coeficientes),
        "evolucao_por_periodo": periodos,
        "disciplinas_recuperadas_apos_reprovacao": recuperadas,
    }


def _recomendacoes_com_requisitos_manuais(
    curriculo: dict[str, DisciplinaCurricular],
) -> dict[str, set[str]]:
    recs = {codigo: set(d.recomendacoes) for codigo, d in curriculo.items()}
    # Requisitos explícitos do PPC que estão em texto livre na base.
    if "ESTM903-17" in recs:
        recs["ESTM903-17"].add("ESTM902-17")
    if "ESTM904-17" in recs:
        recs["ESTM904-17"].add("ESTM903-17")
    return recs


def _maior_cadeia_pendente(
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas: set[str],
    ignorar_tipos: set | None = None,
) -> int:
    ignorar_tipos = set(ignorar_tipos or set())
    pendentes = {
        codigo
        for codigo, disciplina in curriculo.items()
        if disciplina.categoria == Categoria.OBRIGATORIA
        and codigo not in cumpridas
        and disciplina.tipo_componente not in ignorar_tipos
    }
    recs = _recomendacoes_com_requisitos_manuais(curriculo)
    memoria: dict[str, int] = {}
    visitando: set[str] = set()

    def profundidade(codigo: str) -> int:
        if codigo in memoria:
            return memoria[codigo]
        if codigo in visitando:
            return 1
        visitando.add(codigo)
        predecessores = [p for p in recs.get(codigo, set()) if p in pendentes]
        valor = 1 + max((profundidade(p) for p in predecessores), default=0)
        visitando.remove(codigo)
        memoria[codigo] = valor
        return valor

    return max((profundidade(c) for c in pendentes), default=0)


def estimar_formatura_por_grade(
    grade: Grade,
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_projetadas: set[str],
    auditoria: dict,
    periodo_planejamento: str,
    creditos_futuros_por_quadrimestre: int,
    margem_quadrimestres: int = 1,
    quadrimestre_planejado: int | None = None,
    estagio_status: str = "nao_iniciado",
) -> dict[str, Any]:
    """Estima a conclusão separando carga regular, TG e estágio.

    Estágio e Trabalho de Graduação são obrigatórios e contam para a
    integralização, mas normalmente podem ocorrer em paralelo às disciplinas.
    Por isso eles não são simplesmente somados à carga regular e divididos pelo
    ritmo de créditos. A previsão usa o maior entre: carga regular restante,
    cadeia curricular, sequência de TG e janela mínima do estágio.
    """
    selecionadas = set(grade.assinatura_disciplinas)
    cumpridas_apos = set(cumpridas_projetadas) | selecionadas
    cat = auditoria["por_categoria"]

    obrig_regulares_pendentes = sum(
        d.creditos
        for codigo, d in curriculo.items()
        if d.categoria == Categoria.OBRIGATORIA
        and codigo not in cumpridas_apos
        and d.tipo_componente not in {
            TipoComponente.TRABALHO_GRADUACAO,
            TipoComponente.ESTAGIO,
        }
    )

    tg_pendentes = sorted(
        (
            d for codigo, d in curriculo.items()
            if d.categoria == Categoria.OBRIGATORIA
            and d.tipo_componente == TipoComponente.TRABALHO_GRADUACAO
            and codigo not in cumpridas_apos
        ),
        key=lambda d: (d.quadrimestre_recomendado or 99, d.codigo),
    )
    estagios_pendentes = [
        d for codigo, d in curriculo.items()
        if d.categoria == Categoria.OBRIGATORIA
        and d.tipo_componente == TipoComponente.ESTAGIO and codigo not in cumpridas_apos
    ]
    tg_creditos_pendentes = sum(d.creditos for d in tg_pendentes)
    estagio_creditos_pendentes = sum(d.creditos for d in estagios_pendentes)

    ol_dados = cat["opcao_limitada"]
    ol_integralizado = ol_dados.get(
        "integralizado_estimado",
        ol_dados.get("integralizado_confirmado", ol_dados.get("integralizado", 0)),
    )
    ol_ja = ol_integralizado + grade.metricas.creditos_opcao_limitada
    ol_pendentes = max(0, cat["opcao_limitada"]["exigido"] - ol_ja)
    livre_dados = cat["livre"]
    livres_pendentes = max(
        0,
        livre_dados.get(
            "pendente_estimado",
            livre_dados.get("pendente", max(0, livre_dados.get("exigido", 0) - livre_dados.get("integralizado", 0))),
        ),
    )

    creditos_regulares_pendentes = obrig_regulares_pendentes + ol_pendentes + livres_pendentes
    creditos_totais_pendentes = (
        creditos_regulares_pendentes + tg_creditos_pendentes + estagio_creditos_pendentes
    )

    ritmo = max(1, int(creditos_futuros_por_quadrimestre))
    limite_creditos_regulares = (
        math.ceil(creditos_regulares_pendentes / ritmo)
        if creditos_regulares_pendentes else 0
    )
    cadeia_regular = _maior_cadeia_pendente(
        curriculo,
        cumpridas_apos,
        ignorar_tipos={TipoComponente.TRABALHO_GRADUACAO, TipoComponente.ESTAGIO},
    )

    # TG I -> TG II -> TG III: as etapas são sequenciais, porém podem ser
    # cursadas junto com outras disciplinas. Considera também o quadrimestre
    # recomendado para o início da primeira etapa ainda pendente.
    limite_tg = 0
    atraso_inicio_tg = 0
    if tg_pendentes:
        primeiro_q = tg_pendentes[0].quadrimestre_recomendado
        if quadrimestre_planejado is not None and primeiro_q is not None:
            proximo_q = quadrimestre_planejado + 1
            atraso_inicio_tg = max(0, primeiro_q - proximo_q)
        limite_tg = atraso_inicio_tg + len(tg_pendentes)

    # O estágio exige ao menos um quadrimestre de matrícula, mas pode ocorrer
    # em paralelo. Quando informado como em andamento ou concluído, seu código
    # já está em cumpridas_apos e o limite é zero.
    limite_estagio = 0
    atraso_inicio_estagio = 0
    if estagios_pendentes:
        primeiro_q = min(
            (d.quadrimestre_recomendado for d in estagios_pendentes if d.quadrimestre_recomendado is not None),
            default=None,
        )
        if quadrimestre_planejado is not None and primeiro_q is not None:
            proximo_q = quadrimestre_planejado + 1
            atraso_inicio_estagio = max(0, primeiro_q - proximo_q)
        limite_estagio = atraso_inicio_estagio + 1

    futuros_minimos = max(
        limite_creditos_regulares,
        cadeia_regular,
        limite_tg,
        limite_estagio,
    )
    total_incluindo_atual = 1 + futuros_minimos
    total_prudente = total_incluindo_atual + max(0, margem_quadrimestres)

    periodo_minimo = proximo_periodo(periodo_planejamento, max(0, total_incluindo_atual - 1))
    periodo_prudente = proximo_periodo(periodo_planejamento, max(0, total_prudente - 1))

    gargalos = []
    if limite_creditos_regulares:
        gargalos.append(
            f"carga regular restante exige cerca de {limite_creditos_regulares} quadrimestre(s) "
            f"a {ritmo} cr/quadrimestre"
        )
    if cadeia_regular > limite_creditos_regulares:
        gargalos.append(
            f"cadeia curricular regular mínima estimada de {cadeia_regular} quadrimestre(s)"
        )
    if ol_pendentes:
        gargalos.append(f"faltam aproximadamente {ol_pendentes} cr de opção limitada")
    if tg_pendentes:
        gargalos.append(
            f"faltam {len(tg_pendentes)} etapa(s) de TG, com conclusão mínima em "
            f"{limite_tg} quadrimestre(s) futuro(s)"
        )
    if estagios_pendentes:
        gargalos.append(
            f"estágio curricular ainda pendente; janela mínima estimada de {limite_estagio} "
            "quadrimestre(s), podendo ocorrer em paralelo"
        )
    elif estagio_status == "em_andamento":
        gargalos.append("estágio em andamento considerado cumprido na projeção")
    elif estagio_status == "concluido":
        gargalos.append("estágio informado como concluído/validado")

    return {
        "creditos_pendentes_apos_grade": creditos_totais_pendentes,
        "creditos_totais_pendentes_apos_grade": creditos_totais_pendentes,
        "creditos_regulares_pendentes_apos_grade": creditos_regulares_pendentes,
        "obrigatorios_regulares_pendentes_apos_grade": obrig_regulares_pendentes,
        "creditos_tg_pendentes_apos_grade": tg_creditos_pendentes,
        "creditos_estagio_pendentes_apos_grade": estagio_creditos_pendentes,
        "opcao_limitada_pendente_apos_grade": ol_pendentes,
        "livres_pendentes_estimados_apos_grade": livres_pendentes,
        "ritmo_futuro_creditos_por_quadrimestre": ritmo,
        "limite_por_creditos_quadrimestres_futuros": limite_creditos_regulares,
        "limite_por_creditos_regulares_quadrimestres_futuros": limite_creditos_regulares,
        "gargalo_sequencial_quadrimestres_futuros": cadeia_regular,
        "tg_etapas_pendentes": len(tg_pendentes),
        "tg_quadrimestres_futuros_minimos": limite_tg,
        "estagio_status": estagio_status,
        "estagio_quadrimestres_futuros_minimos": limite_estagio,
        "quadrimestres_estimados_incluindo_atual": total_incluindo_atual,
        "quadrimestres_estimados_prudente": total_prudente,
        "periodo_estimado_minimo": periodo_minimo,
        "periodo_estimado_prudente": periodo_prudente,
        "gargalos": gargalos,
        "observacao": (
            "A previsão separa disciplinas regulares, TG e estágio. TG e estágio contam para "
            "a integralização, mas podem ocorrer em paralelo; a data é determinada pelo maior "
            "gargalo entre carga regular, sequência curricular, TG e estágio. Ofertas futuras "
            "e validações administrativas ainda podem alterar o prazo."
        ),
    }

