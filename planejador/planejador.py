from __future__ import annotations

from collections import defaultdict
import math
from dataclasses import dataclass, field, replace
from statistics import mean

from .academico import calcular_desbloqueios, pontuacao_interesse
from .avaliacoes_docentes import BaseAvaliacoesDocentes, avaliacoes_para_oferta
from .configuracao import PreferenciasConfig, RestricoesConfig
from .modelos import (
    Categoria,
    DiagnosticoDisciplina,
    DisciplinaCurricular,
    Grade,
    MetricasGrade,
    Oferta,
    PerfilPlanejamento,
    Recorrencia,
    ResultadoPlanejamento,
    SugestaoAdicao,
    TipoComponente,
)
from .ofertas import ofertas_conflitam


@dataclass(frozen=True)
class ConfiguracaoBusca:
    min_creditos: int
    max_creditos: int
    creditos_alvo: int
    top_n: int = 5
    min_opcoes_padrao: int = 3
    incluir_opcao_limitada: bool = True
    max_disciplinas_candidatas: int = 24
    max_solucoes_pool: int = 5000
    quadrimestre_planejado: int | None = None
    restricoes: RestricoesConfig = RestricoesConfig()
    preferencias: PreferenciasConfig = PreferenciasConfig()
    perfis_gerados: tuple[PerfilPlanejamento, ...] = ()
    gerar_fronteira_pareto: bool = True
    gerar_grades_reserva: bool = True
    avaliacoes_docentes: BaseAvaliacoesDocentes = field(default_factory=BaseAvaliacoesDocentes.vazia)


def disciplinas_pendentes(
    curriculo: dict[str, DisciplinaCurricular],
    codigos_cumpridos: set[str],
) -> dict[str, DisciplinaCurricular]:
    return {
        codigo: disciplina
        for codigo, disciplina in curriculo.items()
        if codigo not in codigos_cumpridos
    }


def _recomendacoes_faltantes(
    disciplina: DisciplinaCurricular,
    cumpridas: set[str],
) -> tuple[str, ...]:
    return tuple(codigo for codigo in disciplina.recomendacoes if codigo not in cumpridas)


def _intervalos_por_dia_e_recorrencia(
    ofertas: tuple[Oferta, ...],
) -> dict[tuple[int, str], list[tuple[int, int]]]:
    agenda: dict[tuple[int, str], list[tuple[int, int]]] = defaultdict(list)
    for oferta in ofertas:
        for horario in oferta.horarios:
            # Aula semanal ocupa as duas quinzenas. Buracos e permanência são
            # medidos separadamente em uma semana I e outra II e depois promediados.
            if horario.recorrencia in {Recorrencia.SEMANAL, Recorrencia.DESCONHECIDA}:
                chaves = ((horario.dia, "I"), (horario.dia, "II"))
            elif horario.recorrencia == Recorrencia.QUINZENAL_I:
                chaves = ((horario.dia, "I"),)
            else:
                chaves = ((horario.dia, "II"),)
            for chave in chaves:
                agenda[chave].append((horario.inicio, horario.fim))
    return agenda


def _mesclar_intervalos(intervalos: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervalos:
        return []
    ordenados = sorted(intervalos)
    mesclados: list[list[int]] = [[ordenados[0][0], ordenados[0][1]]]
    for inicio, fim in ordenados[1:]:
        atual = mesclados[-1]
        if inicio <= atual[1]:
            atual[1] = max(atual[1], fim)
        else:
            mesclados.append([inicio, fim])
    return [(inicio, fim) for inicio, fim in mesclados]


def calcular_logistica(
    ofertas: tuple[Oferta, ...],
    inicio_periodo: int = 0,
    fim_periodo: int = 24 * 60,
) -> tuple[int, int, int, int, int]:
    """Retorna janelas internas, permanência, tempo em aula, bordas livres e dias parciais.

    As aulas semanais são consideradas nas duas quinzenas. Os totais em minutos
    são a média entre semana I e semana II. Espaços antes da primeira aula ou
    depois da última não são janelas internas: o aluno pode chegar mais tarde ou
    ir embora mais cedo. Eles são informados separadamente como bordas livres.
    """
    agenda = _intervalos_por_dia_e_recorrencia(ofertas)
    janelas = permanencia = em_aula = bordas = 0
    dias_parciais: set[int] = set()

    for (dia, _quinzena), intervalos in agenda.items():
        mesclados = _mesclar_intervalos(intervalos)
        if not mesclados:
            continue
        primeiro = mesclados[0][0]
        ultimo = mesclados[-1][1]
        duracao_aulas = sum(fim - inicio for inicio, fim in mesclados)
        duracao_permanencia = ultimo - primeiro
        janela = max(0, duracao_permanencia - duracao_aulas)

        # Só usa o intervalo configurado quando ele é plausível para a grade.
        inicio_ref = inicio_periodo if inicio_periodo <= primeiro else primeiro
        fim_ref = fim_periodo if fim_periodo >= ultimo else ultimo
        borda = max(0, primeiro - inicio_ref) + max(0, fim_ref - ultimo)

        janelas += janela
        permanencia += duracao_permanencia
        em_aula += duracao_aulas
        bordas += borda
        if borda > 0:
            dias_parciais.add(dia)

    return (janelas // 2, permanencia // 2, em_aula // 2, bordas // 2, len(dias_parciais))


def calcular_buracos(ofertas: tuple[Oferta, ...]) -> int:
    return calcular_logistica(ofertas)[0]


def calcular_permanencia(ofertas: tuple[Oferta, ...]) -> int:
    return calcular_logistica(ofertas)[1]


def contar_dias(ofertas: tuple[Oferta, ...]) -> int:
    return len({horario.dia for oferta in ofertas for horario in oferta.horarios})


def _oferta_atende_restricoes(oferta: Oferta, restricoes: RestricoesConfig) -> tuple[bool, str]:
    if oferta.codigo_curriculo in restricoes.disciplinas_proibidas:
        return False, "disciplina proibida na configuração"
    for horario in oferta.horarios:
        if horario.dia in restricoes.dias_indisponiveis:
            return False, "possui aula em dia indisponível"
        if horario.inicio < restricoes.horario_mais_cedo:
            return False, "inicia antes do horário permitido"
        if horario.fim > restricoes.horario_mais_tarde:
            return False, "termina depois do horário permitido"
    return True, ""


def filtrar_ofertas_por_restricoes(
    ofertas: tuple[Oferta, ...],
    curriculo: dict[str, DisciplinaCurricular],
    restricoes: RestricoesConfig,
    diagnosticos: dict[str, DiagnosticoDisciplina],
) -> tuple[tuple[Oferta, ...], dict[str, DiagnosticoDisciplina]]:
    validas: list[Oferta] = []
    motivos_por_codigo: defaultdict[str, set[str]] = defaultdict(set)
    rejeitadas_por_codigo: defaultdict[str, int] = defaultdict(int)

    for oferta in ofertas:
        disciplina = curriculo[oferta.codigo_curriculo]
        if (
            disciplina.tipo_componente != TipoComponente.DISCIPLINA_REGULAR
            and not restricoes.incluir_componentes_especiais_na_grade
        ):
            motivos_por_codigo[disciplina.codigo].add(
                "componente especial tratado fora da grade regular"
            )
            rejeitadas_por_codigo[disciplina.codigo] += 1
            continue
        aceita, motivo = _oferta_atende_restricoes(oferta, restricoes)
        if not aceita:
            motivos_por_codigo[disciplina.codigo].add(motivo)
            rejeitadas_por_codigo[disciplina.codigo] += 1
            continue
        validas.append(oferta)

    atualizados: dict[str, DiagnosticoDisciplina] = {}
    for codigo, diag in diagnosticos.items():
        motivos = list(diag.motivos)
        motivos.extend(sorted(motivos_por_codigo.get(codigo, set())))
        atualizados[codigo] = replace(
            diag,
            rejeitadas_por_restricao=diag.rejeitadas_por_restricao
            + rejeitadas_por_codigo.get(codigo, 0),
            motivos=tuple(dict.fromkeys(motivos)),
        )
    return tuple(validas), atualizados


def calcular_metricas(
    ofertas: tuple[Oferta, ...],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_projetadas: set[str],
    concluidas_reais: set[str],
    quadrimestre_planejado: int | None,
    desbloqueios: dict[str, int],
    preferencias: PreferenciasConfig,
    base_avaliacoes_docentes: BaseAvaliacoesDocentes,
) -> tuple[
    MetricasGrade,
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[dict, ...]],
]:
    obrigatorios = 0
    limitados = 0
    faltantes_por_disciplina: dict[str, tuple[str, ...]] = {}
    dependencias_andamento_por_disciplina: dict[str, tuple[str, ...]] = {}
    soma_quadrimestres = 0
    atraso_total = 0
    atraso_maximo = 0
    disciplinas_futuras = 0
    desbloqueios_total = 0
    interesse_total = 0
    codigos_escolhidos = {oferta.codigo_curriculo for oferta in ofertas}

    preferencias_docentes = set(preferencias.professores_preferidos)
    evitar_docentes = set(preferencias.professores_a_evitar)
    docentes_preferidos = 0
    docentes_evitar = 0
    ajuste_avaliacao_docente = 0.0
    docentes_avaliados = 0
    docentes_favoraveis = 0
    docentes_alerta = 0
    scores_qualidade: list[float] = []
    scores_risco: list[float] = []
    avaliacoes_por_disciplina: dict[str, tuple[dict, ...]] = {}

    for oferta in ofertas:
        disciplina = curriculo[oferta.codigo_curriculo]
        if disciplina.categoria == Categoria.OBRIGATORIA:
            obrigatorios += oferta.creditos
        elif disciplina.categoria == Categoria.OPCAO_LIMITADA:
            limitados += oferta.creditos

        faltantes = _recomendacoes_faltantes(disciplina, cumpridas_projetadas)
        if faltantes:
            faltantes_por_disciplina[disciplina.codigo] = faltantes

        dependencias_andamento = tuple(
            codigo
            for codigo in disciplina.recomendacoes
            if codigo in cumpridas_projetadas and codigo not in concluidas_reais
        )
        if dependencias_andamento:
            dependencias_andamento_por_disciplina[disciplina.codigo] = dependencias_andamento

        q = disciplina.quadrimestre_recomendado or 99
        soma_quadrimestres += q
        if quadrimestre_planejado is not None and disciplina.quadrimestre_recomendado is not None:
            atraso = max(0, quadrimestre_planejado - disciplina.quadrimestre_recomendado)
            atraso_total += atraso
            atraso_maximo = max(atraso_maximo, atraso)
            if disciplina.quadrimestre_recomendado > quadrimestre_planejado:
                disciplinas_futuras += 1

        desbloqueios_total += desbloqueios.get(disciplina.codigo, 0)
        if disciplina.categoria == Categoria.OPCAO_LIMITADA:
            interesse_total += pontuacao_interesse(
                disciplina, preferencias.interesses_formacao
            )

        docentes_oferta = set(oferta.docentes)
        docentes_preferidos += len(docentes_oferta & preferencias_docentes)
        docentes_evitar += len(docentes_oferta & evitar_docentes)

        avaliacoes = avaliacoes_para_oferta(oferta, base_avaliacoes_docentes)
        if avaliacoes:
            avaliacoes_por_disciplina[disciplina.codigo] = tuple(a.para_dict() for a in avaliacoes)
        for avaliacao in avaliacoes:
            docentes_avaliados += 1
            ajuste_avaliacao_docente += avaliacao.efeito_ranking_aplicado
            if avaliacao.efeito_ranking_aplicado > 0:
                docentes_favoraveis += 1
            elif avaliacao.efeito_ranking_aplicado < 0:
                docentes_alerta += 1
            if avaliacao.score_0_100 is not None:
                scores_qualidade.append(avaliacao.score_0_100)
            if avaliacao.risco_score_0_100 is not None:
                scores_risco.append(avaliacao.risco_score_0_100)

    cumpridas_apos_grade = set(cumpridas_projetadas) | codigos_escolhidos
    pendencias_futuras_impactadas = 0
    disciplinas_totalmente_destravadas = 0
    for codigo, disciplina in curriculo.items():
        if codigo in cumpridas_apos_grade or disciplina.categoria == Categoria.LIVRE:
            continue
        recomendacoes = set(disciplina.recomendacoes)
        if not recomendacoes:
            continue
        if recomendacoes & codigos_escolhidos:
            pendencias_futuras_impactadas += 1
        if (
            recomendacoes.issubset(cumpridas_apos_grade)
            and not recomendacoes.issubset(cumpridas_projetadas)
        ):
            disciplinas_totalmente_destravadas += 1

    vagas = [o.vagas_veteranos for o in ofertas if o.vagas_veteranos is not None]
    dias_ocupados = {h.dia for o in ofertas for h in o.horarios}
    (
        janelas_internas,
        permanencia_total,
        tempo_em_aula,
        tempo_livre_extremidades,
        dias_jornada_parcial,
    ) = calcular_logistica(
        ofertas,
        preferencias.horario_referencia_inicio,
        preferencias.horario_referencia_fim,
    )

    metricas = MetricasGrade(
        creditos_totais=sum(oferta.creditos for oferta in ofertas),
        creditos_obrigatorios=obrigatorios,
        creditos_opcao_limitada=limitados,
        carga_teorica=sum(o.t for o in ofertas),
        carga_pratica=sum(o.p for o in ofertas),
        carga_extensao=sum(o.e for o in ofertas),
        carga_individual=sum(o.i for o in ofertas),
        carga_total_referencia=sum(o.carga_total_referencia for o in ofertas),
        disciplinas_praticas=sum(1 for o in ofertas if o.possui_pratica),
        buracos_minutos=janelas_internas,
        permanencia_total_minutos=permanencia_total,
        tempo_em_aula_minutos=tempo_em_aula,
        tempo_livre_extremidades_minutos=tempo_livre_extremidades,
        dias_com_jornada_parcial=dias_jornada_parcial,
        dias_com_aula=contar_dias(ofertas),
        recomendacoes_faltantes=sum(len(v) for v in faltantes_por_disciplina.values()),
        dependencias_em_andamento=sum(
            len(v) for v in dependencias_andamento_por_disciplina.values()
        ),
        quadrimestres_prioridade=soma_quadrimestres,
        atraso_curricular_total=atraso_total,
        atraso_curricular_maximo=atraso_maximo,
        disciplinas_futuras=disciplinas_futuras,
        desbloqueios_diretos=desbloqueios_total,
        pendencias_futuras_impactadas=pendencias_futuras_impactadas,
        disciplinas_totalmente_destravadas=disciplinas_totalmente_destravadas,
        dias_preferidos_ocupados=len(dias_ocupados & set(preferencias.dias_preferidos_sem_aula)),
        docentes_preferidos=docentes_preferidos,
        docentes_a_evitar=docentes_evitar,
        ajuste_avaliacao_docente=round(ajuste_avaliacao_docente, 3),
        docentes_avaliados=docentes_avaliados,
        docentes_favoraveis=docentes_favoraveis,
        docentes_alerta=docentes_alerta,
        qualidade_docente_media=round(mean(scores_qualidade), 2) if scores_qualidade else None,
        risco_docente_medio=round(mean(scores_risco), 2) if scores_risco else None,
        interesse_formacao=interesse_total,
        vagas_veteranos_minimas=min(vagas) if vagas else None,
        vagas_veteranos_media=mean(vagas) if vagas else None,
    )
    return metricas, faltantes_por_disciplina, dependencias_andamento_por_disciplina, avaliacoes_por_disciplina


def _penalidade_preferencias(m: MetricasGrade, preferencias: PreferenciasConfig) -> tuple:
    excedente_dias = (
        max(0, m.dias_com_aula - preferencias.maximo_dias_preferido)
        if preferencias.maximo_dias_preferido is not None
        else 0
    )
    excedente_individual = (
        max(0, m.carga_individual - preferencias.max_carga_individual_preferida)
        if preferencias.max_carga_individual_preferida is not None
        else 0
    )
    excedente_praticas = (
        max(0, m.disciplinas_praticas - preferencias.max_disciplinas_praticas_preferida)
        if preferencias.max_disciplinas_praticas_preferida is not None
        else 0
    )
    return (
        m.docentes_a_evitar,
        -m.docentes_preferidos,
        -m.ajuste_avaliacao_docente,
        m.dias_preferidos_ocupados,
        excedente_dias,
        excedente_individual,
        excedente_praticas,
        -m.interesse_formacao,
    )


def chave_ordenacao(
    grade: Grade,
    creditos_alvo: int,
    perfil: PerfilPlanejamento,
    preferencias: PreferenciasConfig,
) -> tuple:
    m = grade.metricas
    preferencias_chave = _penalidade_preferencias(m, preferencias)
    vagas_chave = -m.vagas_veteranos_minimas if m.vagas_veteranos_minimas is not None else 0

    dependencia_projetada_penalidade = (
        0
        if preferencias.considerar_aprovacoes_projetadas_como_cumpridas
        else m.dependencias_em_andamento
    )
    base_seguranca = (
        m.recomendacoes_faltantes,
        dependencia_projetada_penalidade,
        m.disciplinas_futuras,
    )

    if perfil == PerfilPlanejamento.PROGRESSAO:
        chave = base_seguranca + (
            -m.atraso_curricular_total,
            -m.disciplinas_totalmente_destravadas,
            -m.pendencias_futuras_impactadas,
            -m.desbloqueios_diretos,
            -m.creditos_obrigatorios,
            abs(m.creditos_totais - creditos_alvo),
            m.quadrimestres_prioridade,
            *preferencias_chave,
            m.buracos_minutos,
            m.dias_com_aula,
        )
    elif perfil == PerfilPlanejamento.COMPACTA:
        chave = base_seguranca + (
            m.dias_com_aula,
            m.buracos_minutos,
            m.permanencia_total_minutos,
            abs(m.creditos_totais - creditos_alvo),
            *preferencias_chave,
            -m.atraso_curricular_total,
            -m.desbloqueios_diretos,
        )
    elif perfil == PerfilPlanejamento.EQUILIBRADA:
        chave = base_seguranca + (
            abs(m.creditos_totais - creditos_alvo),
            m.disciplinas_praticas,
            m.carga_individual,
            m.carga_total_referencia,
            m.buracos_minutos,
            m.dias_com_aula,
            *preferencias_chave,
            -m.atraso_curricular_total,
        )
    elif perfil == PerfilPlanejamento.MENOR_CARGA:
        chave = base_seguranca + (
            m.carga_total_referencia,
            m.carga_individual,
            m.disciplinas_praticas,
            m.dias_com_aula,
            m.buracos_minutos,
            *preferencias_chave,
            -m.creditos_obrigatorios,
        )
    elif perfil == PerfilPlanejamento.MAIOR_AVANCO:
        chave = base_seguranca + (
            -m.creditos_totais,
            -m.creditos_obrigatorios,
            -m.atraso_curricular_total,
            -m.disciplinas_totalmente_destravadas,
            -m.pendencias_futuras_impactadas,
            -m.desbloqueios_diretos,
            *preferencias_chave,
            m.buracos_minutos,
            m.dias_com_aula,
        )
    elif perfil == PerfilPlanejamento.MENOR_RISCO:
        chave = (
            m.recomendacoes_faltantes,
            m.dependencias_em_andamento,
            m.disciplinas_futuras,
            m.docentes_alerta,
            m.risco_docente_medio if m.risco_docente_medio is not None else 50.0,
            -m.ajuste_avaliacao_docente,
            m.disciplinas_praticas,
            m.carga_total_referencia,
            abs(m.creditos_totais - creditos_alvo),
            *preferencias_chave,
            -m.atraso_curricular_total,
            vagas_chave,
        )
    else:  # modelo padrão: carga-alvo + ordem do PPC + progressão
        chave = base_seguranca + (
            abs(m.creditos_totais - creditos_alvo),
            -m.atraso_curricular_total,
            -m.disciplinas_totalmente_destravadas,
            -m.pendencias_futuras_impactadas,
            -m.desbloqueios_diretos,
            -m.creditos_obrigatorios,
            *preferencias_chave,
            m.buracos_minutos,
            m.dias_com_aula,
            m.carga_total_referencia,
            vagas_chave,
            m.quadrimestres_prioridade,
        )
    return chave + (grade.assinatura_turmas,)


def _domina(a: Grade, b: Grade, creditos_alvo: int) -> bool:
    ma, mb = a.metricas, b.metricas
    va = (
        ma.recomendacoes_faltantes,
        ma.dependencias_em_andamento,
        abs(ma.creditos_totais - creditos_alvo),
        -ma.creditos_obrigatorios,
        ma.dias_com_aula,
        ma.buracos_minutos,
        ma.carga_total_referencia,
        -ma.atraso_curricular_total,
        -ma.desbloqueios_diretos,
        -ma.ajuste_avaliacao_docente,
    )
    vb = (
        mb.recomendacoes_faltantes,
        mb.dependencias_em_andamento,
        abs(mb.creditos_totais - creditos_alvo),
        -mb.creditos_obrigatorios,
        mb.dias_com_aula,
        mb.buracos_minutos,
        mb.carga_total_referencia,
        -mb.atraso_curricular_total,
        -mb.desbloqueios_diretos,
        -mb.ajuste_avaliacao_docente,
    )
    return all(x <= y for x, y in zip(va, vb)) and any(x < y for x, y in zip(va, vb))


def fronteira_pareto(grades: list[Grade], creditos_alvo: int, limite: int = 8) -> list[Grade]:
    fronteira: list[Grade] = []
    for grade in grades:
        if any(_domina(outra, grade, creditos_alvo) for outra in grades if outra is not grade):
            continue
        fronteira.append(grade)
    # Ordenação apenas para apresentação; todas são não dominadas.
    return sorted(
        fronteira,
        key=lambda g: (
            g.metricas.recomendacoes_faltantes,
            abs(g.metricas.creditos_totais - creditos_alvo),
            g.metricas.dias_com_aula,
            -g.metricas.atraso_curricular_total,
        ),
    )[:limite]


def _escolher_grade_perfil_unica(
    grades: list[Grade],
    perfil: PerfilPlanejamento,
    config: ConfiguracaoBusca,
    assinaturas_usadas: set[tuple[str, ...]],
) -> Grade | None:
    ordenadas = sorted(
        grades,
        key=lambda g: chave_ordenacao(g, config.creditos_alvo, perfil, config.preferencias),
    )
    for grade in ordenadas:
        if grade.assinatura_disciplinas not in assinaturas_usadas:
            assinaturas_usadas.add(grade.assinatura_disciplinas)
            return replace(grade, perfil=perfil)
    if ordenadas:
        return replace(ordenadas[0], perfil=perfil)
    return None


def _grades_reserva(
    principal: Grade | None,
    pool: list[Grade],
    config: ConfiguracaoBusca,
) -> list[tuple[str, Grade]]:
    if principal is None:
        return []
    resultado: list[tuple[str, Grade]] = []
    principal_codigos = set(principal.assinatura_disciplinas)
    usadas: set[tuple[str, ...]] = {principal.assinatura_disciplinas}

    for codigo_removido in principal.assinatura_disciplinas:
        candidatas = [
            grade
            for grade in pool
            if codigo_removido not in grade.assinatura_disciplinas
            and grade.assinatura_disciplinas not in usadas
        ]
        if not candidatas:
            continue
        candidatas.sort(
            key=lambda g: (
                -len(principal_codigos & set(g.assinatura_disciplinas)),
                chave_ordenacao(
                    g,
                    config.creditos_alvo,
                    PerfilPlanejamento.PADRAO,
                    config.preferencias,
                ),
            )
        )
        escolhida = candidatas[0]
        usadas.add(escolhida.assinatura_disciplinas)
        resultado.append((codigo_removido, escolhida))
        if len(resultado) >= 3:
            break
    return resultado


def _complementar_diagnosticos(
    diagnosticos: dict[str, DiagnosticoDisciplina],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas: set[str],
    grades_padrao: list[Grade],
    principal: Grade | None,
    ofertas_validas: tuple[Oferta, ...],
) -> dict[str, DiagnosticoDisciplina]:
    presentes = {
        codigo
        for grade in grades_padrao
        for codigo in grade.assinatura_disciplinas
    }
    por_codigo: defaultdict[str, list[Oferta]] = defaultdict(list)
    for oferta in ofertas_validas:
        por_codigo[oferta.codigo_curriculo].append(oferta)

    resultado: dict[str, DiagnosticoDisciplina] = {}
    for codigo, diag in diagnosticos.items():
        motivos = list(diag.motivos)
        if codigo in cumpridas:
            resultado[codigo] = diag
            continue
        if diag.ofertas_validas > 0 and codigo not in presentes:
            conflito_principal = False
            if principal is not None:
                conflito_principal = all(
                    any(ofertas_conflitam(oferta, p) for p in principal.ofertas)
                    for oferta in por_codigo.get(codigo, [])
                )
            if conflito_principal:
                motivos.append("todas as turmas conflitam com a grade principal")
            else:
                motivos.append(
                    "ofertada, mas ficou fora das opções padrão por prioridade, carga ou logística"
                )
        resultado[codigo] = replace(diag, motivos=tuple(dict.fromkeys(motivos)))
    return resultado


def gerar_planejamento(
    ofertas: tuple[Oferta, ...],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_projetadas: set[str],
    concluidas_reais: set[str],
    configuracao: ConfiguracaoBusca,
    diagnosticos: dict[str, DiagnosticoDisciplina],
) -> ResultadoPlanejamento:
    ofertas, diagnosticos = filtrar_ofertas_por_restricoes(
        ofertas, curriculo, configuracao.restricoes, diagnosticos
    )

    por_disciplina: dict[str, list[Oferta]] = defaultdict(list)
    for oferta in ofertas:
        disciplina = curriculo[oferta.codigo_curriculo]
        if disciplina.categoria == Categoria.LIVRE:
            continue
        if (
            disciplina.categoria == Categoria.OPCAO_LIMITADA
            and not configuracao.incluir_opcao_limitada
        ):
            continue
        if oferta.codigo_curriculo in cumpridas_projetadas:
            continue
        por_disciplina[oferta.codigo_curriculo].append(oferta)

    pendentes = {
        codigo
        for codigo, disciplina in curriculo.items()
        if codigo not in cumpridas_projetadas
        and disciplina.categoria != Categoria.LIVRE
    }
    desbloqueios = calcular_desbloqueios(curriculo, pendentes)

    codigos_todos = sorted(
        por_disciplina,
        key=lambda codigo: (
            0 if curriculo[codigo].categoria == Categoria.OBRIGATORIA else 1,
            -(max(0, (configuracao.quadrimestre_planejado or 0) - (curriculo[codigo].quadrimestre_recomendado or 99))),
            -desbloqueios.get(codigo, 0),
            curriculo[codigo].quadrimestre_recomendado or 99,
            len(por_disciplina[codigo]),
            codigo,
        ),
    )
    codigos = codigos_todos[: configuracao.max_disciplinas_candidatas]

    exigidas = set(configuracao.restricoes.disciplinas_obrigatorias_na_grade)
    indisponiveis_exigidas = exigidas - set(codigos)
    avisos: list[str] = []
    if indisponiveis_exigidas:
        avisos.append(
            "Disciplinas exigidas na grade sem oferta válida: "
            + ", ".join(sorted(indisponiveis_exigidas))
        )

    melhores_por_assinatura: dict[tuple[str, ...], Grade] = {}
    limite_atingido = False
    nos_visitados = 0
    podas_creditos = 0
    podas_conflitos = 0
    grades_concretas_validas = 0

    def registrar(escolhidas: list[Oferta]) -> None:
        nonlocal limite_atingido, grades_concretas_validas
        ofertas_grade = tuple(escolhidas)
        creditos = sum(o.creditos for o in ofertas_grade)
        if not (configuracao.min_creditos <= creditos <= configuracao.max_creditos):
            return
        codigos_grade = {o.codigo_curriculo for o in ofertas_grade}
        if not exigidas.issubset(codigos_grade):
            return
        praticas = sum(1 for o in ofertas_grade if o.possui_pratica)
        if (
            configuracao.restricoes.max_disciplinas_praticas is not None
            and praticas > configuracao.restricoes.max_disciplinas_praticas
        ):
            return

        grades_concretas_validas += 1
        metricas, faltantes, dependencias, avaliacoes_docentes = calcular_metricas(
            ofertas_grade,
            curriculo,
            cumpridas_projetadas,
            concluidas_reais,
            configuracao.quadrimestre_planejado,
            desbloqueios,
            configuracao.preferencias,
            configuracao.avaliacoes_docentes,
        )
        grade = Grade(
            ofertas_grade,
            metricas,
            faltantes,
            dependencias,
            avaliacoes_docentes_por_disciplina=avaliacoes_docentes,
        )
        assinatura = grade.assinatura_disciplinas
        anterior = melhores_por_assinatura.get(assinatura)
        if anterior is None or chave_ordenacao(
            grade,
            configuracao.creditos_alvo,
            PerfilPlanejamento.PADRAO,
            configuracao.preferencias,
        ) < chave_ordenacao(
            anterior,
            configuracao.creditos_alvo,
            PerfilPlanejamento.PADRAO,
            configuracao.preferencias,
        ):
            melhores_por_assinatura[assinatura] = grade

    def backtracking(indice: int, escolhidas: list[Oferta], creditos: int) -> None:
        nonlocal nos_visitados, podas_creditos, podas_conflitos
        nos_visitados += 1
        if creditos > configuracao.max_creditos:
            podas_creditos += 1
            return
        if creditos >= configuracao.min_creditos:
            registrar(escolhidas)
        if indice >= len(codigos):
            return

        codigo = codigos[indice]

        # Se uma disciplina é obrigatória na grade, não há ramo de exclusão.
        if codigo not in exigidas:
            backtracking(indice + 1, escolhidas, creditos)

        for oferta in por_disciplina[codigo]:
            if any(ofertas_conflitam(oferta, existente) for existente in escolhidas):
                podas_conflitos += 1
                continue
            escolhidas.append(oferta)
            backtracking(indice + 1, escolhidas, creditos + oferta.creditos)
            escolhidas.pop()

    backtracking(0, [], 0)
    pool_completo = list(melhores_por_assinatura.values())
    pool_completo.sort(
        key=lambda grade: chave_ordenacao(
            grade,
            configuracao.creditos_alvo,
            PerfilPlanejamento.PADRAO,
            configuracao.preferencias,
        )
    )
    # O limite do pool é agora um limite de retenção/apresentação, não de exploração.
    # Assim, todas as ramificações dos candidatos analisados são percorridas e as
    # melhores grades padrão e por perfil permanecem exatas.
    limite_atingido = len(pool_completo) > configuracao.max_solucoes_pool
    pool_retido = pool_completo[: configuracao.max_solucoes_pool]

    grades_padrao = [replace(g, perfil=PerfilPlanejamento.PADRAO) for g in pool_completo[: configuracao.top_n]]
    if pool_completo and len(grades_padrao) < configuracao.min_opcoes_padrao:
        avisos.append(
            f"Só foi possível gerar {len(grades_padrao)} opção(ões) padrão com as restrições atuais."
        )

    assinaturas_usadas = {g.assinatura_disciplinas for g in grades_padrao[:1]}
    grades_por_perfil: dict[PerfilPlanejamento, Grade] = {}
    for perfil in configuracao.perfis_gerados:
        grade = _escolher_grade_perfil_unica(
            pool_completo,
            perfil,
            configuracao,
            assinaturas_usadas,
        )
        if grade is not None:
            grades_por_perfil[perfil] = grade

    principal = grades_padrao[0] if grades_padrao else None
    # A fronteira de Pareto pode ser quadrática; quando o pool completo excede o
    # limite configurado, ela usa o conjunto retido. As grades padrão, os perfis e
    # as reservas continuam sendo escolhidos sobre o conjunto completo.
    pareto_base = pool_completo if not limite_atingido else pool_retido
    pareto = (
        fronteira_pareto(pareto_base, configuracao.creditos_alvo)
        if configuracao.gerar_fronteira_pareto
        else []
    )
    reservas = (
        _grades_reserva(principal, pool_completo, configuracao)
        if configuracao.gerar_grades_reserva
        else []
    )
    diagnosticos = _complementar_diagnosticos(
        diagnosticos,
        curriculo,
        cumpridas_projetadas,
        grades_padrao,
        principal,
        ofertas,
    )

    if limite_atingido:
        avisos.append(
            "Todas as combinações dos candidatos analisados foram percorridas, mas o pool completo "
            "excedeu o limite de retenção. As grades padrão e por perfil são exatas; a fronteira de "
            "Pareto foi calculada sobre o subconjunto retido."
        )

    combinacoes_teoricas = math.prod(1 + len(por_disciplina[c]) for c in codigos)
    busca_completa = len(codigos_todos) <= configuracao.max_disciplinas_candidatas
    validacao_busca = {
        "disciplinas_candidatas_encontradas": len(codigos_todos),
        "disciplinas_analisadas": len(codigos),
        "limite_disciplinas_candidatas": configuracao.max_disciplinas_candidatas,
        "limite_candidatas_atingido": len(codigos_todos) > len(codigos),
        "combinacoes_teoricas": combinacoes_teoricas,
        "nos_visitados": nos_visitados,
        "podas_por_creditos": podas_creditos,
        "podas_por_conflito": podas_conflitos,
        "grades_concretas_validas": grades_concretas_validas,
        "conjuntos_unicos_validos": len(pool_completo),
        "conjuntos_retidos_no_pool": len(pool_retido),
        "limite_pool": configuracao.max_solucoes_pool,
        "limite_pool_atingido": limite_atingido,
        # A enumeração é sempre completa para o conjunto efetivamente analisado.
        # A garantia global só existe quando nenhuma disciplina candidata foi truncada.
        "busca_completa": busca_completa,
        "busca_completa_nos_candidatos_analisados": True,
        "ranking_padrao_exato": True,
        "ranking_global_garantido": busca_completa,
        "perfis_exatos": True,
        "perfis_globais_garantidos": busca_completa,
        "fronteira_pareto_completa": not limite_atingido,
        "fronteira_pareto_global_garantida": busca_completa and not limite_atingido,
        "min_creditos_efetivo": configuracao.min_creditos,
        "max_creditos_efetivo": configuracao.max_creditos,
        "creditos_alvo": configuracao.creditos_alvo,
        "avaliacoes_docentes_carregadas": configuracao.avaliacoes_docentes.quantidade,
    }

    return ResultadoPlanejamento(
        grades_pool=pool_retido,
        grades_padrao=grades_padrao,
        grades_por_perfil=grades_por_perfil,
        fronteira_pareto=pareto,
        grade_principal=principal,
        grades_reserva=reservas,
        diagnosticos=diagnosticos,
        avisos=avisos,
        validacao_busca=validacao_busca,
    )


# Compatibilidade com chamadas da primeira versão.
def gerar_grades(
    ofertas: tuple[Oferta, ...],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas: set[str],
    configuracao: ConfiguracaoBusca,
) -> list[Grade]:
    diagnosticos = {
        codigo: DiagnosticoDisciplina(codigo=codigo, nome=disciplina.nome)
        for codigo, disciplina in curriculo.items()
    }
    return gerar_planejamento(
        ofertas,
        curriculo,
        cumpridas,
        cumpridas,
        configuracao,
        diagnosticos,
    ).grades_padrao


# ---------------------------------------------------------------------------
# Editor interativo de grades
# ---------------------------------------------------------------------------

def montar_grade_personalizada(
    ofertas: tuple[Oferta, ...],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_projetadas: set[str],
    concluidas_reais: set[str],
    configuracao: ConfiguracaoBusca,
    rotulo: str = "Grade personalizada",
) -> Grade:
    """Valida e recalcula uma grade montada manualmente na interface.

    A função aceita grades abaixo do mínimo de créditos durante a edição, mas
    mantém as restrições rígidas: uma turma por disciplina, ausência de
    conflitos, limite máximo de créditos, horários permitidos e limite de
    disciplinas práticas.
    """
    codigos = [oferta.codigo_curriculo for oferta in ofertas]
    if len(codigos) != len(set(codigos)):
        raise ValueError("A grade contém mais de uma turma da mesma disciplina.")

    creditos = sum(oferta.creditos for oferta in ofertas)
    if creditos > configuracao.max_creditos:
        raise ValueError(
            f"A grade possui {creditos} créditos, acima do máximo de "
            f"{configuracao.max_creditos}."
        )

    for oferta in ofertas:
        aceita, motivo = _oferta_atende_restricoes(oferta, configuracao.restricoes)
        if not aceita:
            raise ValueError(f"{oferta.codigo_curriculo}: {motivo}.")
        if oferta.codigo_curriculo in cumpridas_projetadas:
            raise ValueError(
                f"{oferta.codigo_curriculo} já está cumprida no cenário selecionado."
            )

    for indice, oferta in enumerate(ofertas):
        for outra in ofertas[indice + 1:]:
            if ofertas_conflitam(oferta, outra):
                raise ValueError(
                    "Conflito entre "
                    f"{oferta.codigo_curriculo} ({oferta.nome_turma}) e "
                    f"{outra.codigo_curriculo} ({outra.nome_turma})."
                )

    praticas = sum(1 for oferta in ofertas if oferta.possui_pratica)
    limite_praticas = configuracao.restricoes.max_disciplinas_praticas
    if limite_praticas is not None and praticas > limite_praticas:
        raise ValueError(
            f"A grade possui {praticas} disciplinas práticas, acima do limite "
            f"de {limite_praticas}."
        )

    pendencias = {
        codigo
        for codigo, disciplina in curriculo.items()
        if codigo not in cumpridas_projetadas
        and disciplina.categoria != Categoria.LIVRE
    }
    desbloqueios = calcular_desbloqueios(curriculo, pendencias)
    metricas, faltantes, dependencias, avaliacoes = calcular_metricas(
        ofertas,
        curriculo,
        cumpridas_projetadas,
        concluidas_reais,
        configuracao.quadrimestre_planejado,
        desbloqueios,
        configuracao.preferencias,
        configuracao.avaliacoes_docentes,
    )
    return Grade(
        ofertas=ofertas,
        metricas=metricas,
        recomendacoes_faltantes_por_disciplina=faltantes,
        dependencias_em_andamento_por_disciplina=dependencias,
        avaliacoes_docentes_por_disciplina=avaliacoes,
        perfil=PerfilPlanejamento.PADRAO,
        rotulo=rotulo,
    )


def sugerir_adicoes_grade(
    grade_atual: Grade,
    ofertas_disponiveis: tuple[Oferta, ...],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_projetadas: set[str],
    concluidas_reais: set[str],
    configuracao: ConfiguracaoBusca,
    limite: int = 80,
) -> list[SugestaoAdicao]:
    """Retorna turmas compatíveis ordenadas pela qualidade da grade resultante.

    Mantém mais de uma turma da mesma disciplina quando elas geram horários ou
    avaliações docentes diferentes, permitindo que o aluno escolha a turma.
    """
    atuais = tuple(grade_atual.ofertas)
    codigos_atuais = {oferta.codigo_curriculo for oferta in atuais}
    sugestoes: list[SugestaoAdicao] = []

    for oferta in ofertas_disponiveis:
        codigo = oferta.codigo_curriculo
        if codigo in codigos_atuais or codigo in cumpridas_projetadas:
            continue
        disciplina = curriculo.get(codigo)
        if disciplina is None or disciplina.categoria == Categoria.LIVRE:
            continue
        if (
            disciplina.tipo_componente != TipoComponente.DISCIPLINA_REGULAR
            and not configuracao.restricoes.incluir_componentes_especiais_na_grade
        ):
            continue
        if (
            disciplina.categoria == Categoria.OPCAO_LIMITADA
            and not configuracao.incluir_opcao_limitada
        ):
            continue
        aceita, _ = _oferta_atende_restricoes(oferta, configuracao.restricoes)
        if not aceita:
            continue
        if sum(o.creditos for o in atuais) + oferta.creditos > configuracao.max_creditos:
            continue
        if any(ofertas_conflitam(oferta, existente) for existente in atuais):
            continue

        candidatas = atuais + (oferta,)
        try:
            grade_resultante = montar_grade_personalizada(
                candidatas,
                curriculo,
                cumpridas_projetadas,
                concluidas_reais,
                configuracao,
                rotulo=f"Adicionar {codigo}",
            )
        except ValueError:
            continue
        sugestoes.append(SugestaoAdicao(oferta=oferta, grade_resultante=grade_resultante))

    sugestoes.sort(
        key=lambda item: chave_ordenacao(
            item.grade_resultante,
            configuracao.creditos_alvo,
            PerfilPlanejamento.PADRAO,
            configuracao.preferencias,
        )
    )
    return sugestoes[:limite]


def diagnosticar_adicoes_grade(
    grade_atual: Grade,
    ofertas_disponiveis: tuple[Oferta, ...],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_projetadas: set[str],
    configuracao: ConfiguracaoBusca,
) -> dict[str, tuple[str, ...]]:
    """Explica por que disciplinas pendentes não podem ser adicionadas agora."""
    atuais = tuple(grade_atual.ofertas)
    codigos_atuais = {oferta.codigo_curriculo for oferta in atuais}
    por_codigo: dict[str, list[Oferta]] = defaultdict(list)
    for oferta in ofertas_disponiveis:
        por_codigo[oferta.codigo_curriculo].append(oferta)

    diagnosticos: dict[str, tuple[str, ...]] = {}
    for codigo, disciplina in curriculo.items():
        if codigo in codigos_atuais or codigo in cumpridas_projetadas:
            continue
        if disciplina.categoria == Categoria.LIVRE:
            continue
        if (
            disciplina.tipo_componente != TipoComponente.DISCIPLINA_REGULAR
            and not configuracao.restricoes.incluir_componentes_especiais_na_grade
        ):
            continue
        if disciplina.categoria == Categoria.OPCAO_LIMITADA and not configuracao.incluir_opcao_limitada:
            continue
        ofertas_codigo = por_codigo.get(codigo, [])
        if not ofertas_codigo:
            diagnosticos[codigo] = ("não há turma no campus/turno selecionado",)
            continue

        motivos: set[str] = set()
        alguma_compativel = False
        for oferta in ofertas_codigo:
            aceita, motivo = _oferta_atende_restricoes(oferta, configuracao.restricoes)
            if not aceita:
                motivos.add(motivo)
                continue
            if sum(o.creditos for o in atuais) + oferta.creditos > configuracao.max_creditos:
                motivos.add("ultrapassaria o máximo de créditos")
                continue
            conflitos = [
                existente.codigo_curriculo
                for existente in atuais
                if ofertas_conflitam(oferta, existente)
            ]
            if conflitos:
                motivos.add("conflita com " + ", ".join(sorted(set(conflitos))))
                continue
            alguma_compativel = True
            break
        if not alguma_compativel:
            diagnosticos[codigo] = tuple(sorted(motivos)) or ("não compatível com a grade atual",)
    return diagnosticos
