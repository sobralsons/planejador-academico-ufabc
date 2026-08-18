from __future__ import annotations

import argparse
import json
import re
from dataclasses import replace
from pathlib import Path

from planejador.analise import analisar_desempenho_historico, estimar_formatura_por_grade
from planejador.avaliacoes_docentes import carregar_avaliacoes_docentes, resumo_avaliacoes
from planejador.academico import (
    analisar_frequencia_ofertas,
    auditoria_integralizacao,
    estimar_quadrimestre_planejado,
    planejar_multiquadrimestres,
)
from planejador.configuracao import ConfiguracaoAplicacao, carregar_configuracao
from planejador.curriculo import (
    carregar_aliases_oferta,
    carregar_curriculo,
    carregar_equivalencias,
)
from planejador.historico import consolidar_historico, ler_historico_sigaa
from planejador.modelos import PerfilPlanejamento, ResultadoCenario
from planejador.multicurso import (
    aplicar_estagio, carregar_registro_curriculos, comparar_curriculos,
    gerar_relatorio_multicurso_html, resolver_curriculo, selecionar_melhor_sobreposicao,
)
from planejador.ofertas import ler_ofertas
from planejador.planejador import ConfiguracaoBusca, gerar_planejamento
from planejador.relatorio import gerar_relatorio_html, gerar_relatorio_texto
from planejador.trajetorias import (
    construir_plano_trajetoria, gerar_cenarios_trajetoria,
    gerar_relatorio_trajetoria_html,
)


def resolver(base: Path, caminho: str) -> Path:
    path = Path(caminho)
    return path if path.is_absolute() else base / path


def _aplicar_status_estagio(cumpridas: set[str], registro_curriculo, status: str) -> set[str]:
    return aplicar_estagio(cumpridas, registro_curriculo, status)


def _status_estagio_principal(config: ConfiguracaoAplicacao) -> str:
    """Resolve a situação efetiva do estágio do currículo principal.

    A configuração multicurso por currículo tem prioridade sobre o campo legado
    ``estagio_status``, preservado apenas por compatibilidade com versões antigas.
    """
    return config.estagios_status.get(config.curriculo_principal_id, config.estagio_status)


def _inferir_periodo(config: ConfiguracaoAplicacao) -> str:
    if config.periodo_planejamento:
        return config.periodo_planejamento
    achado = re.search(r"(20\d{2})[_\-. ]([123])", Path(config.arquivo_ofertas).stem)
    return f"{achado.group(1)}.{achado.group(2)}" if achado else ""


def _config_busca(
    config: ConfiguracaoAplicacao,
    quadrimestre_planejado: int | None,
    avaliacoes_docentes,
    min_creditos: int | None = None,
    top_n: int | None = None,
    simplificada: bool = False,
) -> ConfiguracaoBusca:
    return ConfiguracaoBusca(
        min_creditos=config.min_creditos if min_creditos is None else min_creditos,
        max_creditos=config.max_creditos,
        creditos_alvo=config.creditos_alvo,
        top_n=config.top_n if top_n is None else top_n,
        min_opcoes_padrao=config.min_opcoes_padrao,
        incluir_opcao_limitada=config.incluir_opcao_limitada,
        max_disciplinas_candidatas=config.max_disciplinas_candidatas,
        max_solucoes_pool=(min(config.max_solucoes_pool, 1500) if simplificada else config.max_solucoes_pool),
        quadrimestre_planejado=quadrimestre_planejado,
        restricoes=config.restricoes,
        preferencias=config.preferencias,
        perfis_gerados=() if simplificada else config.perfis_gerados,
        gerar_fronteira_pareto=False if simplificada else config.gerar_fronteira_pareto,
        gerar_grades_reserva=False if simplificada else config.gerar_grades_reserva,
        avaliacoes_docentes=avaliacoes_docentes,
    )


def _contar_pendentes_obrigatorias(curriculo, cumpridas) -> int:
    return sum(
        1
        for d in curriculo.values()
        if d.categoria.value == "obrigatoria" and d.codigo not in cumpridas
    )


def _gerar_cenarios(
    config: ConfiguracaoAplicacao,
    situacao,
    ofertas_resultado,
    curriculo,
    quadrimestre_planejado,
    avaliacoes_docentes,
    registro_curriculo,
) -> list[ResultadoCenario]:
    if not config.gerar_cenarios_comparativos:
        return []
    cenarios_def = [
        ("Conservador — nenhuma aprovação presumida", "nenhuma", ()),
        ("Otimista — todas as matrículas aprovadas", "todas", ()),
    ]
    if config.disciplinas_em_andamento_assumidas_aprovadas:
        cenarios_def.insert(
            1,
            (
                "Personalizado — somente aprovações selecionadas",
                "personalizada",
                config.disciplinas_em_andamento_assumidas_aprovadas,
            ),
        )

    resultados: list[ResultadoCenario] = []
    assinaturas_cenarios = set()
    for nome, modo, codigos in cenarios_def:
        cumpridas = situacao.codigos_projetados(modo, codigos)
        cumpridas = _aplicar_status_estagio(cumpridas, registro_curriculo, _status_estagio_principal(config))
        assinatura = frozenset(cumpridas)
        if assinatura in assinaturas_cenarios:
            continue
        assinaturas_cenarios.add(assinatura)
        planejamento = gerar_planejamento(
            ofertas_resultado.ofertas,
            curriculo,
            cumpridas,
            situacao.concluidas,
            _config_busca(config, quadrimestre_planejado, avaliacoes_docentes, top_n=1, simplificada=True),
            ofertas_resultado.diagnosticos,
        )
        resultados.append(
            ResultadoCenario(
                nome=nome,
                cumpridas=frozenset(cumpridas),
                pendentes_obrigatorias=_contar_pendentes_obrigatorias(curriculo, cumpridas),
                melhor_grade=planejamento.grade_principal,
            )
        )
    return resultados


def _grade_chave(grade) -> str:
    return "|".join(grade.assinatura_disciplinas)


def _salvar_resumo_json(
    caminho: Path,
    resultado,
    auditoria,
    quadrimestre,
    periodo,
    config: ConfiguracaoAplicacao,
    analise_desempenho: dict,
    estimativas_formatura: dict[str, dict],
    avaliacoes_docentes,
    comparacao_curriculos: list[dict] | None = None,
    comparacoes_por_grade: dict[str, list[dict]] | None = None,
    plano_trajetoria: dict | None = None,
    cenarios_trajetoria: list[dict] | None = None,
) -> None:
    def grade_json(g):
        return {
            "disciplinas": list(g.assinatura_disciplinas),
            "turmas": list(g.assinatura_turmas),
            "metricas": g.metricas.__dict__,
            "estimativa_formatura": estimativas_formatura.get(_grade_chave(g), {}),
            "avaliacoes_docentes_por_disciplina": g.avaliacoes_docentes_por_disciplina,
        }

    melhor_sobreposicao = selecionar_melhor_sobreposicao(comparacoes_por_grade or {})

    bruto = {
        "periodo_planejamento": periodo,
        "quadrimestre_planejado": quadrimestre,
        "configuracao_efetiva": {
            "campus": config.campus,
            "turno": config.turno,
            "min_creditos": resultado.validacao_busca.get("min_creditos_efetivo", config.min_creditos),
            "max_creditos": config.max_creditos,
            "creditos_alvo": config.creditos_alvo,
            "top_n": config.top_n,
            "max_disciplinas_candidatas": config.max_disciplinas_candidatas,
            "max_solucoes_pool": config.max_solucoes_pool,
            "projecao_em_andamento": config.projecao_em_andamento,
            "considerar_aprovacoes_projetadas_como_cumpridas": config.preferencias.considerar_aprovacoes_projetadas_como_cumpridas,
            "creditos_futuros_por_quadrimestre": config.creditos_futuros_por_quadrimestre,
            "margem_formatura_quadrimestres": config.margem_formatura_quadrimestres,
            "estagio_status": _status_estagio_principal(config),
            "curriculo_principal_id": config.curriculo_principal_id,
            "curriculos_comparacao": list(config.curriculos_comparacao),
            "modo_multicurso": config.modo_multicurso,
            "trajetoria": {
                "curso_atual_id": config.trajetoria_curso_atual_id,
                "ordem_ids": list(config.trajetoria_ordem_ids),
                "estrategia": config.trajetoria_estrategia,
            },
            "estagios_status": dict(config.estagios_status),
            "avaliacoes_docentes": {
                "habilitado": config.avaliacoes_docentes.habilitado,
                "importancia": config.avaliacoes_docentes.importancia,
                "arquivo": config.avaliacoes_docentes.arquivo,
                "registros_carregados": avaliacoes_docentes.quantidade,
            },
            "restricoes": {
                "dias_indisponiveis": list(config.restricoes.dias_indisponiveis),
                "horario_mais_cedo": config.restricoes.horario_mais_cedo,
                "horario_mais_tarde": config.restricoes.horario_mais_tarde,
                "disciplinas_obrigatorias_na_grade": list(config.restricoes.disciplinas_obrigatorias_na_grade),
                "disciplinas_proibidas": list(config.restricoes.disciplinas_proibidas),
            },
            "preferencias": {
                "dias_preferidos_sem_aula": list(config.preferencias.dias_preferidos_sem_aula),
                "maximo_dias_preferido": config.preferencias.maximo_dias_preferido,
                "professores_preferidos": list(config.preferencias.professores_preferidos),
                "professores_a_evitar": list(config.preferencias.professores_a_evitar),
                "interesses_formacao": list(config.preferencias.interesses_formacao),
            },
        },
        "validacao_busca": resultado.validacao_busca,
        "auditoria": auditoria,
        "analise_desempenho": analise_desempenho,
        "avaliacoes_docentes": resumo_avaliacoes(avaliacoes_docentes),
        "comparacao_curriculos": comparacao_curriculos or [],
        "comparacoes_por_grade": comparacoes_por_grade or {},
        "melhor_sobreposicao_multicurso": melhor_sobreposicao,
        "plano_trajetoria": plano_trajetoria or {},
        "cenarios_trajetoria": cenarios_trajetoria or [],
        "grades_padrao": [grade_json(g) for g in resultado.grades_padrao],
        "grades_por_perfil": {
            perfil.value: grade_json(g) for perfil, g in resultado.grades_por_perfil.items()
        },
        "grades_reserva": [
            {
                "sem_disciplina": codigo,
                **grade_json(g),
            }
            for codigo, g in resultado.grades_reserva
        ],
        "planejamento_multiquadrimestral": [plano.__dict__ for plano in resultado.planos_futuros],
    }
    caminho.write_text(json.dumps(bruto, ensure_ascii=False, indent=2), encoding="utf-8")


def executar(config_path: Path, retornar_contexto: bool = False):
    config = carregar_configuracao(config_path)
    base = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent

    registro_curriculos = carregar_registro_curriculos(base, config.arquivo_registro_curriculos)
    if config.curriculo_principal_id not in registro_curriculos:
        raise ValueError(f"Currículo principal não registrado: {config.curriculo_principal_id}")
    registro_principal = registro_curriculos[config.curriculo_principal_id]
    metadados, curriculo, equivalencias, equivalencias_compostas = resolver_curriculo(base, registro_principal)
    aliases = carregar_aliases_oferta(resolver(base, config.arquivo_aliases_oferta))
    # As tabelas de transição também funcionam como aliases de ofertas atuais/antigas.
    for codigo_ofertado, codigo_curriculo in equivalencias.items():
        if codigo_curriculo in curriculo:
            aliases.setdefault(codigo_ofertado, codigo_curriculo)
    avaliacoes_docentes = carregar_avaliacoes_docentes(
        resolver(base, config.avaliacoes_docentes.arquivo),
        habilitado=config.avaliacoes_docentes.habilitado,
        importancia=config.avaliacoes_docentes.importancia,
        minimo_conceitos=config.avaliacoes_docentes.minimo_conceitos,
        minimo_comentarios=config.avaliacoes_docentes.minimo_comentarios,
        usar_avaliacao_especifica=config.avaliacoes_docentes.usar_avaliacao_especifica,
    )

    registros, convalidacoes_historico, resumo_historico = ler_historico_sigaa(
        resolver(base, config.arquivo_historico)
    )
    situacao = consolidar_historico(
        registros,
        equivalencias,
        equivalencias_compostas,
        convalidacoes_historico,
        resumo_historico,
    )

    periodo_planejamento = _inferir_periodo(config)
    quadrimestre_planejado = estimar_quadrimestre_planejado(
        situacao.resumo.periodo_inicial,
        periodo_planejamento,
        config.quadrimestre_planejado,
    )
    cumpridas_confirmadas = set(situacao.concluidas)
    cumpridas = situacao.codigos_projetados(
        config.projecao_em_andamento,
        config.disciplinas_em_andamento_assumidas_aprovadas,
    )
    estagio_status_principal = _status_estagio_principal(config)
    cumpridas = _aplicar_status_estagio(cumpridas, registro_principal, estagio_status_principal)

    resultado_ofertas = ler_ofertas(
        resolver(base, config.arquivo_ofertas),
        codigos_curriculo=set(curriculo),
        nomes_curriculo={c: d.nome for c, d in curriculo.items()},
        aliases_oferta=aliases,
        campus=config.campus,
        turno=config.turno,
        professores_bloqueados=set(config.professores_bloqueados),
    )

    busca = _config_busca(config, quadrimestre_planejado, avaliacoes_docentes)
    resultado = gerar_planejamento(
        resultado_ofertas.ofertas,
        curriculo,
        cumpridas,
        situacao.concluidas,
        busca,
        resultado_ofertas.diagnosticos,
    )

    # Se as restrições geraram menos de três opções, tenta o mínimo flexível.
    if (
        len(resultado.grades_padrao) < config.min_opcoes_padrao
        and config.min_creditos_flexivel < config.min_creditos
    ):
        flexivel = gerar_planejamento(
            resultado_ofertas.ofertas,
            curriculo,
            cumpridas,
            situacao.concluidas,
            _config_busca(
                config,
                quadrimestre_planejado,
                avaliacoes_docentes,
                min_creditos=config.min_creditos_flexivel,
            ),
            resultado_ofertas.diagnosticos,
        )
        if len(flexivel.grades_padrao) > len(resultado.grades_padrao):
            flexivel.avisos.insert(
                0,
                f"Foi usado o mínimo flexível de {config.min_creditos_flexivel} créditos "
                "para ampliar o número de alternativas.",
            )
            resultado = flexivel

    historicos_paths = [resolver(base, p) for p in config.arquivos_ofertas_historicas]
    frequencias, avisos_frequencia = analisar_frequencia_ofertas(historicos_paths, aliases)
    resultado.avisos.extend(avisos_frequencia)
    resultado.avisos.extend(avaliacoes_docentes.avisos)

    resultado.cenarios = _gerar_cenarios(
        config,
        situacao,
        resultado_ofertas,
        curriculo,
        quadrimestre_planejado,
        avaliacoes_docentes,
        registro_principal,
    )
    if config.gerar_planejamento_multiquadrimestral:
        resultado.planos_futuros = planejar_multiquadrimestres(
            curriculo=curriculo,
            cumpridas_iniciais=cumpridas,
            grade_principal=resultado.grade_principal,
            periodo_planejamento=periodo_planejamento,
            quadrimestre_planejado=quadrimestre_planejado,
            horizonte=config.horizonte_quadrimestres,
            creditos_alvo=config.creditos_alvo,
            max_creditos=config.max_creditos,
            incluir_opcao_limitada=config.incluir_opcao_limitada,
            interesses=config.preferencias.interesses_formacao,
        )

    auditoria = auditoria_integralizacao(
        metadados,
        curriculo,
        situacao,
        cumpridas,
        cumpridas_confirmadas=cumpridas_confirmadas,
        estagio_status=estagio_status_principal,
    )
    analise_desempenho = (
        analisar_desempenho_historico(situacao)
        if config.gerar_analise_desempenho
        else {}
    )
    grades_para_estimar = list(resultado.grades_padrao) + list(resultado.grades_por_perfil.values())
    grades_para_estimar += [g for _, g in resultado.grades_reserva]
    estimativas_formatura: dict[str, dict] = {}
    for grade in grades_para_estimar:
        chave = _grade_chave(grade)
        if chave not in estimativas_formatura:
            estimativas_formatura[chave] = estimar_formatura_por_grade(
                grade=grade,
                curriculo=curriculo,
                cumpridas_projetadas=cumpridas,
                auditoria=auditoria,
                periodo_planejamento=periodo_planejamento,
                creditos_futuros_por_quadrimestre=config.creditos_futuros_por_quadrimestre,
                margem_quadrimestres=config.margem_formatura_quadrimestres,
                quadrimestre_planejado=quadrimestre_planejado,
                estagio_status=estagio_status_principal,
            )

    ids_comparacao = []
    for id_ in (config.curriculo_principal_id, *config.curriculos_comparacao, *config.trajetoria_ordem_ids, config.trajetoria_curso_atual_id):
        if id_ not in ids_comparacao and id_ in registro_curriculos:
            ids_comparacao.append(id_)
    estagios_status = dict(config.estagios_status)
    estagios_status.setdefault(config.curriculo_principal_id, estagio_status_principal)
    grade_referencia = resultado.grade_principal
    comparacao_curriculos = comparar_curriculos(
        base=base,
        ids=ids_comparacao,
        registro_curriculos=registro_curriculos,
        registros_historico=registros,
        convalidacoes_historico=convalidacoes_historico,
        resumo_historico=resumo_historico,
        modo_projecao=config.projecao_em_andamento,
        codigos_personalizados=config.disciplinas_em_andamento_assumidas_aprovadas,
        estagios_status=estagios_status,
        grade=grade_referencia,
        curriculo_origem=curriculo,
        periodo_planejamento=periodo_planejamento,
        ritmo=config.creditos_futuros_por_quadrimestre,
        margem=config.margem_formatura_quadrimestres,
        quadrimestre_planejado=quadrimestre_planejado,
    )
    comparacoes_por_grade: dict[str, list[dict]] = {}
    for grade in resultado.grades_padrao:
        comparacoes_por_grade[_grade_chave(grade)] = comparar_curriculos(
            base=base, ids=ids_comparacao, registro_curriculos=registro_curriculos,
            registros_historico=registros, convalidacoes_historico=convalidacoes_historico,
            resumo_historico=resumo_historico, modo_projecao=config.projecao_em_andamento,
            codigos_personalizados=config.disciplinas_em_andamento_assumidas_aprovadas,
            estagios_status=estagios_status, grade=grade, curriculo_origem=curriculo,
            periodo_planejamento=periodo_planejamento,
            ritmo=config.creditos_futuros_por_quadrimestre,
            margem=config.margem_formatura_quadrimestres,
            quadrimestre_planejado=quadrimestre_planejado,
        )

    ordem_trajetoria = [x for x in config.trajetoria_ordem_ids if x in registro_curriculos]
    if not ordem_trajetoria:
        ordem_trajetoria = [config.curriculo_principal_id]
    comparacoes_trajetoria = [x for x in comparacao_curriculos if x.get("id") in ordem_trajetoria]
    plano_trajetoria = construir_plano_trajetoria(
        base=base,
        comparacoes=comparacoes_trajetoria,
        registro_curriculos=registro_curriculos,
        ordem_ids=ordem_trajetoria,
        periodo_planejamento=periodo_planejamento,
        ritmo=config.creditos_futuros_por_quadrimestre,
        margem=config.margem_formatura_quadrimestres,
        estrategia=config.trajetoria_estrategia,
        curso_atual_id=config.trajetoria_curso_atual_id,
        ofertas_historicas=len(config.arquivos_ofertas_historicas),
    )
    cenarios_trajetoria = gerar_cenarios_trajetoria(
        base=base,
        comparacoes=comparacao_curriculos,
        registro_curriculos=registro_curriculos,
        curso_atual_id=config.trajetoria_curso_atual_id,
        alvo_ids=ordem_trajetoria,
        periodo_planejamento=periodo_planejamento,
        ritmo=config.creditos_futuros_por_quadrimestre,
        margem=config.margem_formatura_quadrimestres,
        estrategia=config.trajetoria_estrategia,
        ofertas_historicas=len(config.arquivos_ofertas_historicas),
    )

    saidas = base / "saidas"
    saidas.mkdir(parents=True, exist_ok=True)
    txt = saidas / "relatorio_planejamento.txt"
    html = saidas / "relatorio_planejamento.html"
    resumo_json = saidas / "resultado_resumo.json"
    html_multicurso = saidas / "relatorio_multicurso.html"
    html_trajetoria = saidas / "relatorio_trajetoria_academica.html"

    gerar_relatorio_texto(
        txt,
        metadados,
        curriculo,
        situacao,
        cumpridas,
        resultado,
        auditoria,
        resultado_ofertas.avisos,
        config.projecao_em_andamento,
        quadrimestre_planejado,
        periodo_planejamento,
        config.creditos_alvo,
        frequencias,
        analise_desempenho,
        estimativas_formatura,
        resultado.validacao_busca,
        config.preferencias.considerar_aprovacoes_projetadas_como_cumpridas,
    )
    gerar_relatorio_html(
        html,
        metadados,
        curriculo,
        situacao,
        cumpridas,
        resultado,
        auditoria,
        resultado_ofertas.avisos,
        config.projecao_em_andamento,
        quadrimestre_planejado,
        periodo_planejamento,
        config.creditos_alvo,
        frequencias,
        analise_desempenho,
        estimativas_formatura,
        resultado.validacao_busca,
        config.preferencias.considerar_aprovacoes_projetadas_como_cumpridas,
    )
    gerar_relatorio_multicurso_html(html_multicurso, comparacao_curriculos, periodo_planejamento)
    if config.gerar_relatorio_trajetoria:
        gerar_relatorio_trajetoria_html(html_trajetoria, plano_trajetoria, cenarios_trajetoria)
    _salvar_resumo_json(
        resumo_json, resultado, auditoria, quadrimestre_planejado, periodo_planejamento,
        config, analise_desempenho, estimativas_formatura, avaliacoes_docentes,
        comparacao_curriculos, comparacoes_por_grade, plano_trajetoria, cenarios_trajetoria,
    )
    if retornar_contexto:
        contexto_editor = {
            "resultado": resultado,
            "ofertas_disponiveis": resultado_ofertas.ofertas,
            "curriculo": curriculo,
            "cumpridas_projetadas": set(cumpridas),
            "concluidas_reais": set(situacao.concluidas),
            "configuracao_busca": busca,
            "periodo_planejamento": periodo_planejamento,
            "quadrimestre_planejado": quadrimestre_planejado,
            "registro_curriculos": registro_curriculos,
            "ids_comparacao": ids_comparacao,
            "registros_historico": registros,
            "convalidacoes_historico": convalidacoes_historico,
            "resumo_historico": resumo_historico,
            "estagios_status": estagios_status,
            "comparacao_curriculos": comparacao_curriculos,
            "relatorio_multicurso": html_multicurso,
            "plano_trajetoria": plano_trajetoria,
            "cenarios_trajetoria": cenarios_trajetoria,
            "relatorio_trajetoria": html_trajetoria,
        }
        return txt, html, resumo_json, contexto_editor
    return txt, html, resumo_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Planejador de matrícula da UFABC")
    parser.add_argument(
        "--config",
        default="config/config.json",
        help="Caminho para o arquivo JSON de configuração",
    )
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    txt, html, resumo_json = executar(config_path)
    print(txt.read_text(encoding="utf-8"))
    print(f"\nRelatório textual salvo em: {txt}")
    print(f"Relatório visual salvo em: {html}")
    print(f"Resumo JSON salvo em: {resumo_json}")


if __name__ == "__main__":
    main()
