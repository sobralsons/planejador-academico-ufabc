from __future__ import annotations

import math
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any, Iterable

from .academico import proximo_periodo
from .curriculo import carregar_curriculo
from .modelos import Categoria, DisciplinaCurricular
from .multicurso import RegistroCurriculo, resolver_curriculo
from .utils import normalizar_texto


ESTRATEGIAS_VALIDAS = {"simultanea", "hibrida", "sequencial"}


def _chave_disciplina(disciplina: DisciplinaCurricular) -> str:
    """Identidade curricular estável para comparar versões e cursos.

    O nome normalizado é preferido porque códigos mudam entre matrizes. As
    equivalências oficiais continuam sendo aplicadas antes, durante a leitura do
    histórico; esta chave serve somente para identificar sobreposição entre os
    pacotes curriculares já estruturados.
    """
    return normalizar_texto(disciplina.nome)


def _dados_curso(
    base: Path,
    registro: RegistroCurriculo,
    analise: dict[str, Any],
) -> dict[str, Any]:
    metadados, curriculo, _, _ = resolver_curriculo(base, registro)
    cumpridas = set(analise.get("cumpridas_apos_grade", analise.get("cumpridas_projetadas", [])))
    return {
        "registro": registro,
        "metadados": metadados,
        "curriculo": curriculo,
        "cumpridas": cumpridas,
        "analise": analise,
    }


def _criar_tarefas_e_flexiveis(
    cursos: dict[str, dict[str, Any]],
    ordem_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, int]], list[dict[str, Any]], int]:
    obrigatorias: dict[str, dict[str, Any]] = {}
    indices_por_curso: dict[str, dict[str, DisciplinaCurricular]] = {}

    for curso_id, dados in cursos.items():
        curriculo: dict[str, DisciplinaCurricular] = dados["curriculo"]
        cumpridas: set[str] = dados["cumpridas"]
        indices_por_curso[curso_id] = {_chave_disciplina(d): d for d in curriculo.values()}
        for codigo, disciplina in curriculo.items():
            if (
                disciplina.categoria == Categoria.OBRIGATORIA
                and codigo not in cumpridas
            ):
                chave = _chave_disciplina(disciplina)
                item = obrigatorias.setdefault(
                    chave,
                    {
                        "chave": chave,
                        "nome": disciplina.nome,
                        "creditos": disciplina.creditos,
                        "quadrimestre": disciplina.quadrimestre_recomendado,
                        "obrigatoria_em": {},
                        "flexivel_em": {},
                        "tipo": "obrigatoria",
                    },
                )
                item["creditos"] = max(int(item["creditos"]), int(disciplina.creditos))
                qs = [q for q in (item.get("quadrimestre"), disciplina.quadrimestre_recomendado) if q]
                item["quadrimestre"] = min(qs) if qs else None
                item["obrigatoria_em"][curso_id] = {
                    "codigo": codigo,
                    "creditos": disciplina.creditos,
                }

    # Uma obrigatória de um curso pode preencher OL/livre de outro.
    for item in obrigatorias.values():
        chave = item["chave"]
        for curso_id, dados in cursos.items():
            disciplina = indices_por_curso[curso_id].get(chave)
            if not disciplina or disciplina.codigo in dados["cumpridas"]:
                continue
            if disciplina.categoria in {Categoria.OPCAO_LIMITADA, Categoria.LIVRE}:
                item["flexivel_em"][curso_id] = {
                    "categoria": disciplina.categoria.value,
                    "creditos": disciplina.creditos,
                    "codigo": disciplina.codigo,
                }

    deficits: dict[str, dict[str, int]] = {}
    for curso_id, dados in cursos.items():
        est = dados["analise"]["estimativa_formatura"]
        deficits[curso_id] = {
            "opcao_limitada": max(0, int(est.get("opcao_limitada_pendente", 0))),
            "livre": max(0, int(est.get("livres_pendentes", 0))),
        }

    # Aplica o crédito flexível que virá das obrigatórias da união.
    for item in obrigatorias.values():
        for curso_id, cobertura in item["flexivel_em"].items():
            categoria = cobertura["categoria"]
            if categoria in deficits[curso_id]:
                deficits[curso_id][categoria] = max(
                    0,
                    deficits[curso_id][categoria] - int(cobertura["creditos"]),
                )

    candidatos: dict[str, dict[str, Any]] = {}
    chaves_obrigatorias = set(obrigatorias)
    for curso_id, dados in cursos.items():
        for codigo, disciplina in dados["curriculo"].items():
            if disciplina.categoria not in {Categoria.OPCAO_LIMITADA, Categoria.LIVRE}:
                continue
            if codigo in dados["cumpridas"]:
                continue
            chave = _chave_disciplina(disciplina)
            if chave in chaves_obrigatorias:
                continue
            item = candidatos.setdefault(
                chave,
                {
                    "chave": chave,
                    "nome": disciplina.nome,
                    "creditos": disciplina.creditos,
                    "quadrimestre": disciplina.quadrimestre_recomendado,
                    "cobertura": {},
                    "tipo": "flexivel",
                },
            )
            item["creditos"] = max(int(item["creditos"]), int(disciplina.creditos))
            qs = [q for q in (item.get("quadrimestre"), disciplina.quadrimestre_recomendado) if q]
            item["quadrimestre"] = min(qs) if qs else None
            item["cobertura"][curso_id] = {
                "categoria": disciplina.categoria.value,
                "creditos": disciplina.creditos,
                "codigo": codigo,
            }

    escolhidas: list[dict[str, Any]] = []
    disponiveis = dict(candidatos)
    while any(v > 0 for d in deficits.values() for v in d.values()):
        melhor = None
        melhor_chave = None
        melhor_score = None
        for chave, candidato in disponiveis.items():
            ganho = 0
            cursos_atingidos = 0
            for curso_id, cobertura in candidato["cobertura"].items():
                categoria = cobertura["categoria"]
                restante = deficits[curso_id].get(categoria, 0)
                reducao = min(restante, int(cobertura["creditos"]))
                if reducao > 0:
                    ganho += reducao
                    cursos_atingidos += 1
            if ganho <= 0:
                continue
            custo = max(1, int(candidato["creditos"]))
            score = (
                ganho / custo,
                cursos_atingidos,
                ganho,
                -(candidato.get("quadrimestre") or 99),
                candidato["nome"],
            )
            if melhor_score is None or score > melhor_score:
                melhor_score = score
                melhor = candidato
                melhor_chave = chave
        if melhor is None or melhor_chave is None:
            break
        disponiveis.pop(melhor_chave, None)
        escolhidas.append(melhor)
        for curso_id, cobertura in melhor["cobertura"].items():
            categoria = cobertura["categoria"]
            deficits[curso_id][categoria] = max(
                0,
                deficits[curso_id][categoria] - int(cobertura["creditos"]),
            )

    desconhecidos: list[dict[str, Any]] = []
    creditos_desconhecidos = 0
    for curso_id in ordem_ids:
        for categoria, restante in deficits.get(curso_id, {}).items():
            if restante <= 0:
                continue
            creditos_desconhecidos += restante
            desconhecidos.append(
                {
                    "chave": f"PENDENCIA_{curso_id}_{categoria}",
                    "nome": f"Créditos {categoria.replace('_', ' ')} ainda não associados — {cursos[curso_id]['registro'].rotulo}",
                    "creditos": restante,
                    "quadrimestre": None,
                    "cobertura": {
                        curso_id: {
                            "categoria": categoria,
                            "creditos": restante,
                            "codigo": None,
                        }
                    },
                    "tipo": "flexivel_nao_mapeado",
                }
            )

    compartilhadas = []
    for item in [*obrigatorias.values(), *escolhidas]:
        cursos_impactados = set(item.get("obrigatoria_em", {})) | set(item.get("flexivel_em", {})) | set(item.get("cobertura", {}))
        if len(cursos_impactados) >= 2:
            compartilhadas.append(
                {
                    "disciplina": item["nome"],
                    "creditos_unicos": item["creditos"],
                    "cursos": [cursos[c]["registro"].rotulo for c in ordem_ids if c in cursos_impactados],
                    "quantidade_cursos": len(cursos_impactados),
                    "tipo": "Obrigatória compartilhada" if len(item.get("obrigatoria_em", {})) >= 2 else "Aproveitamento entre categorias",
                }
            )
    compartilhadas.sort(key=lambda x: (-x["quantidade_cursos"], -x["creditos_unicos"], x["disciplina"]))

    return list(obrigatorias.values()), escolhidas, deficits, compartilhadas, creditos_desconhecidos


def _contribuicoes_tarefa(tarefa: dict[str, Any]) -> set[str]:
    return (
        set(tarefa.get("obrigatoria_em", {}))
        | set(tarefa.get("flexivel_em", {}))
        | set(tarefa.get("cobertura", {}))
    )


def _ordenar_tarefas(tarefas: list[dict[str, Any]], ordem_ids: list[str], estrategia: str) -> list[dict[str, Any]]:
    prioridade = {id_: i for i, id_ in enumerate(ordem_ids)}

    def chave(tarefa: dict[str, Any]):
        cursos = _contribuicoes_tarefa(tarefa)
        cobertura = len(cursos)
        menor_prioridade = min((prioridade.get(c, 999) for c in cursos), default=999)
        q = tarefa.get("quadrimestre") or 99
        obrigatoria = 0 if tarefa.get("tipo") == "obrigatoria" else 1
        if estrategia == "sequencial":
            return (menor_prioridade, obrigatoria, -cobertura, q, tarefa["nome"])
        if estrategia == "hibrida":
            compartilhada = 0 if cobertura >= 2 else 1
            return (compartilhada, menor_prioridade, obrigatoria, q, tarefa["nome"])
        return (-cobertura, obrigatoria, menor_prioridade, q, tarefa["nome"])

    return sorted(tarefas, key=chave)


def _simular_roadmap(
    tarefas: list[dict[str, Any]],
    cursos: dict[str, dict[str, Any]],
    ordem_ids: list[str],
    estrategia: str,
    ritmo: int,
    periodo_planejamento: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    tarefas_ordenadas = _ordenar_tarefas(tarefas, ordem_ids, estrategia)
    obrigatorias_restantes: dict[str, set[str]] = {}
    flex_restante: dict[str, dict[str, int]] = {}
    minimos_especiais: dict[str, int] = {}
    for curso_id, dados in cursos.items():
        obrigatorias_restantes[curso_id] = {
            t["chave"] for t in tarefas
            if curso_id in t.get("obrigatoria_em", {})
        }
        est = dados["analise"]["estimativa_formatura"]
        flex_restante[curso_id] = {
            "opcao_limitada": max(0, int(est.get("opcao_limitada_pendente", 0))),
            "livre": max(0, int(est.get("livres_pendentes", 0))),
        }
        minimos_especiais[curso_id] = max(
            int(est.get("quadrimestres_cadeia", 0)),
            int(est.get("quadrimestres_tg", 0)),
            int(est.get("quadrimestres_estagio", 0)),
        )

    pendentes = list(tarefas_ordenadas)
    roadmap: list[dict[str, Any]] = []
    concluidos_em: dict[str, int] = {}
    quadrimestre = 0
    ritmo = max(1, int(ritmo))

    while pendentes and quadrimestre < 60:
        quadrimestre += 1
        selecionadas: list[dict[str, Any]] = []
        carga = 0
        while pendentes and (carga < ritmo or not selecionadas):
            tarefa = pendentes.pop(0)
            selecionadas.append(tarefa)
            carga += int(tarefa["creditos"])
            if carga >= ritmo:
                break

        cursos_impactados: set[str] = set()
        for tarefa in selecionadas:
            chave = tarefa["chave"]
            for curso_id in ordem_ids:
                if chave in obrigatorias_restantes.get(curso_id, set()):
                    obrigatorias_restantes[curso_id].remove(chave)
                    cursos_impactados.add(curso_id)
                cobertura = tarefa.get("flexivel_em", {}).get(curso_id) or tarefa.get("cobertura", {}).get(curso_id)
                if cobertura:
                    categoria = cobertura["categoria"]
                    if categoria in flex_restante[curso_id]:
                        flex_restante[curso_id][categoria] = max(
                            0,
                            flex_restante[curso_id][categoria] - int(cobertura["creditos"]),
                        )
                        cursos_impactados.add(curso_id)

        marcos = []
        for curso_id in ordem_ids:
            if curso_id in concluidos_em:
                continue
            regular_concluido = not obrigatorias_restantes[curso_id] and all(v <= 0 for v in flex_restante[curso_id].values())
            if regular_concluido and quadrimestre >= minimos_especiais[curso_id]:
                concluidos_em[curso_id] = quadrimestre
                marcos.append(cursos[curso_id]["registro"].rotulo)

        roadmap.append(
            {
                "numero": quadrimestre,
                "periodo": proximo_periodo(periodo_planejamento, quadrimestre - 1),
                "creditos_estimados": carga,
                "focos": [t["nome"] for t in selecionadas],
                "cursos_impactados": [cursos[c]["registro"].rotulo for c in ordem_ids if c in cursos_impactados],
                "diplomas_estimados": marcos,
            }
        )

    # Componentes finais podem impor uma data mesmo depois das tarefas regulares.
    for curso_id in ordem_ids:
        if curso_id not in concluidos_em:
            concluidos_em[curso_id] = max(len(roadmap), minimos_especiais[curso_id], 1)
    total_q = max(concluidos_em.values(), default=1)
    while len(roadmap) < total_q:
        q = len(roadmap) + 1
        marcos = [cursos[c]["registro"].rotulo for c, v in concluidos_em.items() if v == q]
        roadmap.append(
            {
                "numero": q,
                "periodo": proximo_periodo(periodo_planejamento, q - 1),
                "creditos_estimados": 0,
                "focos": ["Conclusão de trabalho final, estágio, extensão ou validações pendentes"],
                "cursos_impactados": marcos,
                "diplomas_estimados": marcos,
            }
        )

    return roadmap, concluidos_em


def _nivel_confianca(
    quantidade_cursos: int,
    comparacoes: list[dict[str, Any]],
    ofertas_historicas: int,
    creditos_nao_mapeados: int,
) -> dict[str, Any]:
    score = 92
    fatores: list[str] = []
    if quantidade_cursos > 1:
        reducao = 7 * (quantidade_cursos - 1)
        score -= reducao
        fatores.append(f"−{reducao}: múltiplos cursos aumentam a dependência de ofertas e encaixes")
    if ofertas_historicas <= 0:
        score -= 10
        fatores.append("−10: não há histórico de ofertas futuras para estimar frequência")
    if creditos_nao_mapeados > 0:
        score -= 8
        fatores.append("−8: há créditos flexíveis sem disciplina estratégica identificada")
    if any(x["estimativa_formatura"].get("extensao_pendente_maxima_horas", 0) > 0 for x in comparacoes):
        score -= 7
        fatores.append("−7: extensão depende de validação e atividades que podem não estar no histórico")
    if any(x["estimativa_formatura"].get("atividades_complementares_pendentes_horas", 0) > 0 for x in comparacoes):
        score -= 4
        fatores.append("−4: atividades complementares ainda não integralizadas")
    score = max(35, min(95, score))
    classificacao = "alta" if score >= 80 else "média" if score >= 60 else "baixa"
    return {
        "score_0_100": score,
        "classificacao": classificacao,
        "fatores": fatores,
        "observacao": "A confiança mede a estabilidade da projeção, não a probabilidade de aprovação nas disciplinas.",
    }


def construir_plano_trajetoria(
    base: Path,
    comparacoes: list[dict[str, Any]],
    registro_curriculos: dict[str, RegistroCurriculo],
    ordem_ids: Iterable[str],
    periodo_planejamento: str,
    ritmo: int,
    margem: int,
    estrategia: str = "hibrida",
    curso_atual_id: str | None = None,
    ofertas_historicas: int = 0,
) -> dict[str, Any]:
    ordem = [x for x in ordem_ids if x in registro_curriculos]
    if not ordem:
        raise ValueError("Selecione ao menos um currículo para a trajetória.")
    if len(ordem) > 3:
        raise ValueError("A trajetória interativa aceita até três cursos por cenário.")
    estrategia = estrategia if estrategia in ESTRATEGIAS_VALIDAS else "hibrida"
    por_id = {x["id"]: x for x in comparacoes}
    faltantes = [x for x in ordem if x not in por_id]
    if faltantes:
        raise ValueError("Não há análise curricular para: " + ", ".join(faltantes))
    cursos = {id_: _dados_curso(base, registro_curriculos[id_], por_id[id_]) for id_ in ordem}

    obrigatorias, flexiveis, deficits_finais, compartilhadas, creditos_nao_mapeados = _criar_tarefas_e_flexiveis(cursos, ordem)
    tarefas = [*obrigatorias, *flexiveis]
    for curso_id, deficits in deficits_finais.items():
        for categoria, restante in deficits.items():
            if restante > 0:
                tarefas.append(
                    {
                        "chave": f"PENDENCIA_{curso_id}_{categoria}",
                        "nome": f"Créditos {categoria.replace('_', ' ')} — {registro_curriculos[curso_id].rotulo}",
                        "creditos": restante,
                        "quadrimestre": None,
                        "cobertura": {curso_id: {"categoria": categoria, "creditos": restante, "codigo": None}},
                        "tipo": "flexivel_nao_mapeado",
                    }
                )

    roadmap, concluidos_em = _simular_roadmap(
        tarefas, cursos, ordem, estrategia, ritmo, periodo_planejamento
    )
    q_todos = max(concluidos_em.values(), default=1)
    q_prudente = q_todos + max(0, int(margem))

    soma_individual = sum(
        int(por_id[id_]["estimativa_formatura"].get("creditos_regulares_pendentes", 0))
        for id_ in ordem
    )
    creditos_unicos = sum(int(t["creditos"]) for t in tarefas)
    economia = max(0, soma_individual - creditos_unicos)
    eficiencia = round((economia / soma_individual * 100) if soma_individual else 0, 1)

    cursos_resultado = []
    for id_ in ordem:
        item = por_id[id_]
        q = concluidos_em[id_]
        est = item["estimativa_formatura"]
        cursos_resultado.append(
            {
                "id": id_,
                "rotulo": item["rotulo"],
                "grupo": item["grupo"],
                "prioridade": ordem.index(id_) + 1,
                "percentual_conclusao": est.get("percentual_conclusao", 0),
                "creditos_regulares_pendentes": est.get("creditos_regulares_pendentes", 0),
                "periodo_se_cursado_isoladamente": est.get("periodo_estimado_minimo"),
                "periodo_no_plano_conjunto": proximo_periodo(periodo_planejamento, max(0, q - 1)),
                "periodo_prudente_no_plano": proximo_periodo(periodo_planejamento, max(0, q + margem - 1)),
                "quadrimestres_no_plano": q,
                "gargalos": est.get("gargalos", []),
            }
        )

    confianca = _nivel_confianca(
        len(ordem), comparacoes, ofertas_historicas, creditos_nao_mapeados
    )
    objetivo = (
        "curso único" if len(ordem) == 1 else
        "dupla formação" if len(ordem) == 2 else
        "tríplice formação"
    )
    return {
        "objetivo": objetivo,
        "curso_atual_id": curso_atual_id,
        "estrategia": estrategia,
        "ordem_prioridade": ordem,
        "cursos": cursos_resultado,
        "periodo_inicio": periodo_planejamento,
        "ritmo_creditos_por_quadrimestre": int(ritmo),
        "margem_quadrimestres": int(margem),
        "creditos_regulares_somados_separadamente": soma_individual,
        "creditos_regulares_unicos_estimados": creditos_unicos,
        "creditos_economizados_por_sobreposicao": economia,
        "eficiencia_sobreposicao_percentual": eficiencia,
        "disciplinas_obrigatorias_unicas": len(obrigatorias),
        "disciplinas_flexiveis_estrategicas": len(flexiveis),
        "creditos_flexiveis_nao_mapeados": creditos_nao_mapeados,
        "periodo_conclusao_todos_minimo": proximo_periodo(periodo_planejamento, max(0, q_todos - 1)),
        "periodo_conclusao_todos_prudente": proximo_periodo(periodo_planejamento, max(0, q_prudente - 1)),
        "quadrimestres_para_todos_minimo": q_todos,
        "quadrimestres_para_todos_prudente": q_prudente,
        "disciplinas_compartilhadas": compartilhadas[:30],
        "roadmap": roadmap,
        "confianca": confianca,
        "premissas": [
            "Os créditos compartilhados são identificados por equivalências já aplicadas e pelo nome normalizado das disciplinas nos PPCs estruturados.",
            "O roteiro futuro é acadêmico: não garante que cada disciplina será ofertada no quadrimestre sugerido.",
            "Opções limitadas e livres são escolhidas por uma heurística de cobertura que prioriza disciplinas válidas em mais de um currículo.",
            "Trabalho final e estágio são tratados em paralelo às disciplinas quando o PPC permite.",
            "A conclusão de cursos específicos não é prevista antes do curso de ingresso correspondente.",
        ],
    }


def gerar_cenarios_trajetoria(
    base: Path,
    comparacoes: list[dict[str, Any]],
    registro_curriculos: dict[str, RegistroCurriculo],
    curso_atual_id: str,
    alvo_ids: Iterable[str],
    periodo_planejamento: str,
    ritmo: int,
    margem: int,
    estrategia: str,
    ofertas_historicas: int = 0,
) -> list[dict[str, Any]]:
    alvos = []
    for id_ in alvo_ids:
        if id_ in registro_curriculos and id_ not in alvos:
            alvos.append(id_)
    cenarios: list[tuple[str, list[str], str]] = []
    if curso_atual_id in registro_curriculos:
        cenarios.append(("Continuar somente no curso atual", [curso_atual_id], "sequencial"))
    for alvo in alvos:
        if alvo != curso_atual_id:
            cenarios.append((f"Mudar para {registro_curriculos[alvo].rotulo}", [alvo], "sequencial"))
            if curso_atual_id in registro_curriculos:
                cenarios.append((f"Concluir {registro_curriculos[curso_atual_id].rotulo} e também {registro_curriculos[alvo].rotulo}", [curso_atual_id, alvo], estrategia))
    combinacao = []
    for id_ in [curso_atual_id, *alvos]:
        if id_ in registro_curriculos and id_ not in combinacao:
            combinacao.append(id_)
    if len(combinacao) >= 3:
        cenarios.append(("Plano com três formações", combinacao[:3], estrategia))

    por_id = {x["id"]: x for x in comparacoes}
    resultados = []
    vistos = set()
    for nome, ids, estrategia_cenario in cenarios:
        chave = tuple(ids)
        if chave in vistos or any(x not in por_id for x in ids):
            continue
        vistos.add(chave)
        plano = construir_plano_trajetoria(
            base=base,
            comparacoes=[por_id[x] for x in ids],
            registro_curriculos=registro_curriculos,
            ordem_ids=ids,
            periodo_planejamento=periodo_planejamento,
            ritmo=ritmo,
            margem=margem,
            estrategia=estrategia_cenario,
            curso_atual_id=curso_atual_id,
            ofertas_historicas=ofertas_historicas,
        )
        resultados.append(
            {
                "nome": nome,
                "cursos": [registro_curriculos[x].rotulo for x in ids],
                "quantidade_cursos": len(ids),
                "periodo_minimo": plano["periodo_conclusao_todos_minimo"],
                "periodo_prudente": plano["periodo_conclusao_todos_prudente"],
                "quadrimestres_minimos": plano["quadrimestres_para_todos_minimo"],
                "creditos_unicos": plano["creditos_regulares_unicos_estimados"],
                "economia_sobreposicao": plano["creditos_economizados_por_sobreposicao"],
                "eficiencia_sobreposicao": plano["eficiencia_sobreposicao_percentual"],
                "confianca": plano["confianca"]["classificacao"],
            }
        )
    return resultados


def gerar_relatorio_trajetoria_html(caminho: Path, plano: dict[str, Any], cenarios: list[dict[str, Any]] | None = None) -> None:
    cursos_html = []
    for curso in plano["cursos"]:
        gargalos = "".join(f"<li>{escape(str(x))}</li>" for x in curso.get("gargalos", [])) or "<li>Nenhum gargalo adicional identificado.</li>"
        cursos_html.append(
            f"""
            <article class='course-card'>
              <div class='course-head'><div><span>Prioridade {curso['prioridade']}</span><h3>{escape(curso['rotulo'])}</h3></div><b>{escape(str(curso['periodo_no_plano_conjunto']))}</b></div>
              <div class='bar'><i style='width:{min(100,float(curso['percentual_conclusao']))}%'></i></div>
              <p>{curso['percentual_conclusao']}% estimado · {curso['creditos_regulares_pendentes']} cr regulares pendentes</p>
              <div class='dates'><span>Sozinho <strong>{escape(str(curso['periodo_se_cursado_isoladamente']))}</strong></span><span>No plano <strong>{escape(str(curso['periodo_no_plano_conjunto']))}</strong></span><span>Prudente <strong>{escape(str(curso['periodo_prudente_no_plano']))}</strong></span></div>
              <details><summary>Gargalos desta formação</summary><ul>{gargalos}</ul></details>
            </article>"""
        )

    compartilhadas = "".join(
        "<tr>"
        f"<td><strong>{escape(x['disciplina'])}</strong><br><small>{escape(x['tipo'])}</small></td>"
        f"<td>{x['creditos_unicos']}</td><td>{x['quantidade_cursos']}</td>"
        f"<td>{escape(' · '.join(x['cursos']))}</td>"
        "</tr>"
        for x in plano.get("disciplinas_compartilhadas", [])[:20]
    ) or "<tr><td colspan='4'>Nenhuma sobreposição relevante identificada.</td></tr>"

    roadmap = "".join(
        "<tr>"
        f"<td><strong>{escape(x['periodo'])}</strong></td>"
        f"<td>{x['creditos_estimados']}</td>"
        f"<td>{escape(' · '.join(x['focos']))}</td>"
        f"<td>{escape(' · '.join(x['diplomas_estimados']) or '—')}</td>"
        "</tr>"
        for x in plano.get("roadmap", [])
    )

    cenarios_html = ""
    if cenarios:
        linhas = "".join(
            "<tr>"
            f"<td><strong>{escape(c['nome'])}</strong><br><small>{escape(' · '.join(c['cursos']))}</small></td>"
            f"<td>{c['periodo_minimo']}</td><td>{c['periodo_prudente']}</td>"
            f"<td>{c['creditos_unicos']}</td><td>{c['economia_sobreposicao']}</td><td>{escape(c['confianca'])}</td>"
            "</tr>"
            for c in cenarios
        )
        cenarios_html = f"""
        <section class='panel'><h2>Comparador de cenários</h2><div class='table-wrap'><table><thead><tr><th>Cenário</th><th>Mínimo</th><th>Prudente</th><th>Créditos únicos</th><th>Economia</th><th>Confiança</th></tr></thead><tbody>{linhas}</tbody></table></div></section>
        """

    fatores = "".join(f"<li>{escape(str(x))}</li>" for x in plano["confianca"].get("fatores", [])) or "<li>Nenhum redutor relevante aplicado.</li>"
    premissas = "".join(f"<li>{escape(str(x))}</li>" for x in plano.get("premissas", []))
    html = f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Plano de trajetória acadêmica</title>
<style>
:root{{--navy:#123f5a;--teal:#176b62;--green:#2b8a67;--ink:#17312d;--muted:#63746f;--line:#dbe6e1;--bg:#f3f7f6;--gold:#c18b16}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font-family:Inter,Segoe UI,Arial,sans-serif;color:var(--ink)}}header{{background:linear-gradient(135deg,var(--navy),var(--teal));color:white;padding:46px max(5vw,28px)}}header h1{{font-size:2.4rem;margin:0 0 10px}}header p{{max-width:900px;margin:0;color:#e4f1ef;line-height:1.55}}.wrap{{max-width:1350px;margin:28px auto;padding:0 22px}}.hero-grid{{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:14px;margin-bottom:22px}}.hero-card,.panel,.course-card{{background:white;border:1px solid var(--line);border-radius:18px;box-shadow:0 10px 28px #123f5a10}}.hero-card{{padding:22px}}.hero-card span{{display:block;color:var(--muted);font-size:.8rem;text-transform:uppercase;font-weight:700;letter-spacing:.05em}}.hero-card b{{font-size:1.65rem;display:block;margin-top:7px}}.hero-card.primary{{background:linear-gradient(135deg,#ecf6f2,#fff)}}.panel{{padding:22px;margin:20px 0}}.panel h2{{margin-top:0}}.courses{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:17px}}.course-card{{padding:20px}}.course-head{{display:flex;justify-content:space-between;gap:15px}}.course-head span{{font-size:.75rem;color:var(--muted);text-transform:uppercase}}.course-head h3{{margin:4px 0 12px}}.course-head>b{{background:#e8f4ef;padding:10px;border-radius:10px;height:max-content}}.bar{{height:9px;background:#e6eeeb;border-radius:99px;overflow:hidden}}.bar i{{height:100%;display:block;background:linear-gradient(90deg,var(--teal),#76bc9c)}}.course-card p{{color:var(--muted)}}.dates{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}.dates span{{background:#f4f7f6;padding:9px;border-radius:9px;font-size:.78rem}}.dates strong{{display:block;font-size:.95rem;margin-top:2px}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:780px}}th,td{{padding:11px 12px;border-bottom:1px solid #edf2ef;text-align:left;vertical-align:top}}th{{font-size:.76rem;text-transform:uppercase;color:#536b63}}small{{color:var(--muted)}}details{{margin-top:12px;border-top:1px solid #edf2ef;padding-top:10px}}summary{{cursor:pointer;font-weight:700}}li{{line-height:1.5}}.confidence{{display:grid;grid-template-columns:170px 1fr;gap:20px;align-items:center}}.score{{width:130px;height:130px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--green) {plano['confianca']['score_0_100']}%,#e6ece9 0);position:relative}}.score:after{{content:'';position:absolute;inset:13px;background:white;border-radius:50%}}.score b{{position:relative;z-index:1;font-size:1.65rem}}footer{{max-width:1350px;margin:28px auto 45px;padding:0 22px;color:var(--muted);font-size:.86rem}}@media(max-width:900px){{.hero-grid{{grid-template-columns:1fr 1fr}}.hero-card.primary{{grid-column:1/-1}}.confidence{{grid-template-columns:1fr}}}}@media(max-width:580px){{.hero-grid{{grid-template-columns:1fr}}.dates{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>Plano de trajetória acadêmica — UFABC</h1><p>Simulação de {escape(plano['objetivo'])}, iniciando em {escape(plano['periodo_inicio'])}, com estratégia {escape(plano['estrategia'])} e ritmo de {plano['ritmo_creditos_por_quadrimestre']} créditos por quadrimestre.</p></header><div class='wrap'>
<section class='hero-grid'><div class='hero-card primary'><span>Conclusão de todas as formações</span><b>{escape(plano['periodo_conclusao_todos_minimo'])}–{escape(plano['periodo_conclusao_todos_prudente'])}</b><p>{plano['quadrimestres_para_todos_minimo']}–{plano['quadrimestres_para_todos_prudente']} quadrimestres incluindo o período inicial.</p></div><div class='hero-card'><span>Créditos únicos estimados</span><b>{plano['creditos_regulares_unicos_estimados']}</b></div><div class='hero-card'><span>Economia por sobreposição</span><b>{plano['creditos_economizados_por_sobreposicao']} cr</b></div><div class='hero-card'><span>Eficiência curricular</span><b>{plano['eficiencia_sobreposicao_percentual']}%</b></div></section>
<section class='panel'><h2>Quando cada diploma tende a ser concluído?</h2><div class='courses'>{''.join(cursos_html)}</div></section>
{cenarios_html}
<section class='panel'><h2>Disciplinas com maior aproveitamento conjunto</h2><div class='table-wrap'><table><thead><tr><th>Disciplina</th><th>Créditos</th><th>Cursos</th><th>Onde contribui</th></tr></thead><tbody>{compartilhadas}</tbody></table></div></section>
<section class='panel'><h2>Roteiro acadêmico aproximado</h2><p>Esta sequência prioriza sobreposição e ordem curricular; os horários e a oferta real devem ser recalculados em cada matrícula.</p><div class='table-wrap'><table><thead><tr><th>Quadrimestre</th><th>Créditos</th><th>Focos sugeridos</th><th>Marco de conclusão</th></tr></thead><tbody>{roadmap}</tbody></table></div></section>
<section class='panel confidence'><div class='score'><b>{plano['confianca']['score_0_100']}</b></div><div><h2>Confiança {escape(plano['confianca']['classificacao'])}</h2><p>{escape(plano['confianca']['observacao'])}</p><ul>{fatores}</ul><details><summary>Premissas de cálculo</summary><ul>{premissas}</ul></details></div></section>
</div><footer>Estimativa de apoio à decisão. Confirme regras de integralização, convalidações, extensão, estágio e trabalho final no SIGAA e com as coordenações dos cursos.</footer></body></html>"""
    caminho.write_text(html, encoding="utf-8")
