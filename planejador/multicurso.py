from __future__ import annotations

import json
import math
from html import escape
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .academico import auditoria_integralizacao, proximo_periodo
from .analise import _maior_cadeia_pendente
from .curriculo import carregar_curriculo, carregar_equivalencias
from .historico import consolidar_historico
from .modelos import Categoria, DisciplinaCurricular, Grade, RegistroHistorico, ResumoHistorico, TipoComponente
from .utils import normalizar_texto


@dataclass(frozen=True)
class RegistroCurriculo:
    id: str
    rotulo: str
    arquivo: str
    equivalencias: str
    grupo: str
    estagio_codigo: str | None = None
    curso_base_id: str | None = None


def carregar_registro_curriculos(base: Path, caminho: str = "dados/registro_curriculos.json") -> dict[str, RegistroCurriculo]:
    path = Path(caminho)
    if not path.is_absolute():
        path = base / path
    bruto = json.loads(path.read_text(encoding="utf-8"))
    resultado: dict[str, RegistroCurriculo] = {}
    for id_, item in bruto.get("curriculos", {}).items():
        resultado[id_] = RegistroCurriculo(
            id=id_,
            rotulo=str(item["rotulo"]),
            arquivo=str(item["arquivo"]),
            equivalencias=str(item["equivalencias"]),
            grupo=str(item.get("grupo", "Outros")),
            estagio_codigo=item.get("estagio_codigo"),
            curso_base_id=item.get("curso_base_id"),
        )
    return resultado


def resolver_curriculo(base: Path, registro: RegistroCurriculo):
    arquivo = Path(registro.arquivo)
    eq = Path(registro.equivalencias)
    if not arquivo.is_absolute():
        arquivo = base / arquivo
    if not eq.is_absolute():
        eq = base / eq
    metadados, curriculo = carregar_curriculo(arquivo)
    equivalencias, compostas = carregar_equivalencias(eq)
    return metadados, curriculo, equivalencias, compostas


def aplicar_estagio(codigos: set[str], registro: RegistroCurriculo, status: str) -> set[str]:
    resultado = set(codigos)
    if registro.estagio_codigo and status in {"em_andamento", "concluido"}:
        resultado.add(registro.estagio_codigo)
    return resultado


def _mapear_codigo_para_curriculo(
    codigo: str,
    nome: str,
    curriculo: dict[str, DisciplinaCurricular],
    equivalencias: dict[str, str],
) -> str | None:
    if codigo in curriculo:
        return codigo
    destino = equivalencias.get(codigo)
    if destino in curriculo:
        return destino
    nome_n = normalizar_texto(nome)
    candidatos = [d.codigo for d in curriculo.values() if normalizar_texto(d.nome) == nome_n]
    return candidatos[0] if len(candidatos) == 1 else None


def mapear_grade_detalhada_para_curriculo(
    grade: Grade | None,
    curriculo: dict[str, DisciplinaCurricular],
    equivalencias: dict[str, str],
    curriculo_origem: dict[str, DisciplinaCurricular] | None = None,
) -> tuple[set[str], int]:
    """Mapeia a grade e informa os créditos realmente não reconhecidos na matriz.

    A contagem é feita oferta a oferta. Isso evita classificar como livre uma
    disciplina cujo código antigo foi corretamente convertido por equivalência.
    """
    if grade is None:
        return set(), 0
    resultado: set[str] = set()
    creditos_nao_mapeados = 0
    for oferta in grade.ofertas:
        nome = ""
        if curriculo_origem and oferta.codigo_curriculo in curriculo_origem:
            nome = curriculo_origem[oferta.codigo_curriculo].nome
        codigo = _mapear_codigo_para_curriculo(oferta.codigo_curriculo, nome, curriculo, equivalencias)
        if codigo:
            resultado.add(codigo)
        else:
            creditos_nao_mapeados += oferta.creditos
    return resultado, creditos_nao_mapeados


def mapear_grade_para_curriculo(
    grade: Grade | None,
    curriculo: dict[str, DisciplinaCurricular],
    equivalencias: dict[str, str],
    curriculo_origem: dict[str, DisciplinaCurricular] | None = None,
) -> set[str]:
    return mapear_grade_detalhada_para_curriculo(
        grade, curriculo, equivalencias, curriculo_origem
    )[0]


def _creditos_categoria(cumpridas: set[str], curriculo: dict[str, DisciplinaCurricular], categoria: Categoria) -> int:
    return sum(d.creditos for c, d in curriculo.items() if c in cumpridas and d.categoria == categoria)


def creditos_novos_da_grade(
    grade_mapeada: set[str],
    cumpridas_antes_da_grade: set[str],
    curriculo: dict[str, DisciplinaCurricular],
) -> int:
    """Conta somente o avanço marginal da grade na trajetória analisada."""
    return sum(
        curriculo[codigo].creditos
        for codigo in grade_mapeada - cumpridas_antes_da_grade
        if codigo in curriculo
    )


def _livres_potenciais(
    situacao,
    curriculo: dict[str, DisciplinaCurricular],
    creditos_grade_nao_mapeados: int = 0,
) -> int:
    creditos = 0
    for codigo, tentativas in situacao.tentativas.items():
        if codigo in curriculo:
            continue
        concluidas = [r for r in tentativas if r.situacao in {"APR", "APRN", "DISP", "TRANS", "INCORP", "CUMP"}]
        if concluidas:
            creditos += max(r.creditos for r in concluidas)
    return creditos + max(0, int(creditos_grade_nao_mapeados))


def estimar_formatura_curriculo(
    metadados: dict[str, Any],
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_projetadas: set[str],
    grade_mapeada: set[str],
    situacao,
    grade: Grade | None,
    creditos_grade_nao_mapeados: int,
    periodo_planejamento: str,
    ritmo: int,
    margem: int,
    quadrimestre_planejado: int | None,
    estagio_status: str,
) -> dict[str, Any]:
    apos = set(cumpridas_projetadas) | set(grade_mapeada)
    exig_obr = int(metadados.get("creditos_obrigatorios", 0))
    exig_ol = int(metadados.get("creditos_opcao_limitada", 0))
    exig_livres = int(metadados.get("creditos_livres", 0))

    obrig_regular = sum(
        d.creditos for c, d in curriculo.items()
        if d.categoria == Categoria.OBRIGATORIA and c not in apos
        and d.tipo_componente not in {TipoComponente.TRABALHO_GRADUACAO, TipoComponente.ESTAGIO}
    )
    tg_pendentes = [d for c, d in curriculo.items() if d.categoria == Categoria.OBRIGATORIA and d.tipo_componente == TipoComponente.TRABALHO_GRADUACAO and c not in apos]
    estagio_pendentes = [d for c, d in curriculo.items() if d.categoria == Categoria.OBRIGATORIA and d.tipo_componente == TipoComponente.ESTAGIO and c not in apos]

    ol_feitos = min(exig_ol, _creditos_categoria(apos, curriculo, Categoria.OPCAO_LIMITADA))
    ol_pendente = max(0, exig_ol - ol_feitos)
    livre_direto = _creditos_categoria(apos, curriculo, Categoria.LIVRE)
    livre_potencial = _livres_potenciais(situacao, curriculo, creditos_grade_nao_mapeados)
    livres_feitos = min(exig_livres, livre_direto + livre_potencial)
    livres_pendentes = max(0, exig_livres - livres_feitos)

    regulares = obrig_regular + ol_pendente + livres_pendentes
    ritmo = max(1, int(ritmo))
    por_creditos = math.ceil(regulares / ritmo) if regulares else 0
    cadeia = _maior_cadeia_pendente(
        curriculo, apos,
        ignorar_tipos={TipoComponente.TRABALHO_GRADUACAO, TipoComponente.ESTAGIO},
    )
    duracoes = metadados.get("duracoes_especiais", {}) or {}
    tg_min = 0
    if tg_pendentes:
        duracao_tg = int(duracoes.get("trabalho_final_quadrimestres", len(tg_pendentes) or 1))
        primeiro_q = min((d.quadrimestre_recomendado for d in tg_pendentes if d.quadrimestre_recomendado), default=None)
        # Alguns PPCs registram somente a disciplina final de TCC, embora o trabalho seja
        # desenvolvido em vários quadrimestres. Nesses casos o pacote curricular informa
        # explicitamente o quadrimestre de início para não somar espera e duração duas vezes.
        inicio_tg = duracoes.get("trabalho_final_quadrimestre_inicio", primeiro_q)
        tg_min = duracao_tg
        if inicio_tg and quadrimestre_planejado:
            tg_min += max(0, int(inicio_tg) - (quadrimestre_planejado + 1))
    estagio_min = 0
    if estagio_pendentes:
        estagio_min = int(duracoes.get("estagio_quadrimestres", 1))
        primeiro_q = min((d.quadrimestre_recomendado for d in estagio_pendentes if d.quadrimestre_recomendado), default=None)
        if primeiro_q and quadrimestre_planejado:
            estagio_min += max(0, primeiro_q - (quadrimestre_planejado + 1))

    futuros = max(por_creditos, cadeia, tg_min, estagio_min)
    incluindo_atual = 1 + futuros
    prudente = incluindo_atual + max(0, int(margem))
    total_req = exig_obr + exig_ol + exig_livres
    realizado = min(exig_obr, _creditos_categoria(apos, curriculo, Categoria.OBRIGATORIA)) + ol_feitos + livres_feitos

    atividades_exigidas = int(metadados.get("atividades_complementares_horas", 0) or 0)
    atividades_realizadas = float(situacao.resumo.atividades_complementares_horas or 0)
    atividades_pendentes = max(0.0, atividades_exigidas - atividades_realizadas)
    extensao_exigida = int(metadados.get("extensao_horas", 0) or 0)
    # É uma estimativa mínima baseada apenas em disciplinas mapeadas com componente E.
    # Ações de extensão externas às disciplinas e regras de transição dependem de validação oficial.
    extensao_reconhecida_minima = min(
        extensao_exigida,
        sum(max(0, curriculo[c].e) * 12 for c in apos if c in curriculo),
    ) if extensao_exigida else 0
    extensao_pendente_maxima = max(0, extensao_exigida - extensao_reconhecida_minima)

    gargalos: list[str] = []
    if regulares:
        gargalos.append(f"{regulares} cr regulares pendentes; cerca de {por_creditos} quadrimestre(s) no ritmo selecionado")
    if cadeia > por_creditos:
        gargalos.append(f"cadeia curricular mínima de {cadeia} quadrimestre(s)")
    if tg_pendentes:
        gargalos.append(f"trabalho final pendente, com janela mínima de {tg_min} quadrimestre(s)")
    if estagio_pendentes:
        gargalos.append(f"estágio obrigatório pendente, podendo ocorrer em paralelo")
    elif estagio_status == "em_andamento":
        gargalos.append("estágio em andamento considerado cumprido na projeção")
    if atividades_pendentes > 0:
        gargalos.append(f"{atividades_pendentes:g} h de atividades complementares ainda não reconhecidas no histórico")
    if extensao_exigida:
        gargalos.append(
            f"extensão: ao menos {extensao_reconhecida_minima:g} de {extensao_exigida:g} h reconhecidas pelas disciplinas mapeadas; "
            "ações externas e transições exigem conferência"
        )

    return {
        "creditos_requisitos": total_req,
        "creditos_realizados_apos_grade": realizado,
        "percentual_conclusao": round((realizado / total_req * 100) if total_req else 0, 1),
        "creditos_regulares_pendentes": regulares,
        "obrigatorios_regulares_pendentes": obrig_regular,
        "opcao_limitada_pendente": ol_pendente,
        "livres_pendentes": livres_pendentes,
        "tg_creditos_pendentes": sum(d.creditos for d in tg_pendentes),
        "estagio_creditos_pendentes": sum(d.creditos for d in estagio_pendentes),
        "quadrimestres_por_creditos": por_creditos,
        "quadrimestres_cadeia": cadeia,
        "quadrimestres_tg": tg_min,
        "quadrimestres_estagio": estagio_min,
        "quadrimestres_estimados_incluindo_atual": incluindo_atual,
        "quadrimestres_estimados_prudente": prudente,
        "atividades_complementares_exigidas_horas": atividades_exigidas,
        "atividades_complementares_realizadas_horas": atividades_realizadas,
        "atividades_complementares_pendentes_horas": atividades_pendentes,
        "extensao_exigida_horas": extensao_exigida,
        "extensao_reconhecida_minima_horas": extensao_reconhecida_minima,
        "extensao_pendente_maxima_horas": extensao_pendente_maxima,
        "periodo_estimado_minimo": proximo_periodo(periodo_planejamento, max(0, incluindo_atual - 1)),
        "periodo_estimado_prudente": proximo_periodo(periodo_planejamento, max(0, prudente - 1)),
        "gargalos": gargalos,
        "observacao": "Estimativa indicativa: considera carga regular, cadeia de recomendações, trabalho final e estágio em paralelo; ofertas futuras podem alterar o prazo.",
    }


def analisar_curriculo(
    base: Path,
    registro: RegistroCurriculo,
    registros_historico: list[RegistroHistorico],
    convalidacoes_historico: dict[str, str],
    resumo_historico: ResumoHistorico,
    modo_projecao: str,
    codigos_personalizados: Iterable[str],
    estagio_status: str,
    grade: Grade | None,
    curriculo_origem: dict[str, DisciplinaCurricular] | None,
    periodo_planejamento: str,
    ritmo: int,
    margem: int,
    quadrimestre_planejado: int | None,
) -> dict[str, Any]:
    metadados, curriculo, equivalencias, compostas = resolver_curriculo(base, registro)
    situacao = consolidar_historico(
        registros_historico, equivalencias, compostas, convalidacoes_historico, resumo_historico
    )
    confirmadas = aplicar_estagio(set(situacao.concluidas), registro, "concluido" if estagio_status == "concluido" else "nao_iniciado")
    projetadas = situacao.codigos_projetados(modo_projecao, codigos_personalizados)
    projetadas = aplicar_estagio(projetadas, registro, estagio_status)
    auditoria = auditoria_integralizacao(
        metadados, curriculo, situacao, projetadas,
        cumpridas_confirmadas=confirmadas, estagio_status=estagio_status,
    )
    grade_mapeada, creditos_grade_nao_mapeados = mapear_grade_detalhada_para_curriculo(
        grade, curriculo, equivalencias, curriculo_origem
    )
    estimativa = estimar_formatura_curriculo(
        metadados, curriculo, projetadas, grade_mapeada, situacao, grade,
        creditos_grade_nao_mapeados, periodo_planejamento, ritmo, margem,
        quadrimestre_planejado, estagio_status,
    )
    pendentes = [
        {"codigo": d.codigo, "nome": d.nome, "creditos": d.creditos, "quadrimestre": d.quadrimestre_recomendado}
        for d in curriculo.values()
        if d.categoria == Categoria.OBRIGATORIA and d.codigo not in (projetadas | grade_mapeada)
    ]
    return {
        "id": registro.id,
        "rotulo": registro.rotulo,
        "grupo": registro.grupo,
        "curso": metadados.get("curso", registro.rotulo),
        "versao": metadados.get("versao", ""),
        "auditoria": auditoria,
        "estimativa_formatura": estimativa,
        "disciplinas_grade_reconhecidas": sorted(grade_mapeada),
        "disciplinas_grade_ja_cumpridas": sorted(grade_mapeada & projetadas),
        "cumpridas_projetadas": sorted(projetadas),
        "cumpridas_apos_grade": sorted(projetadas | grade_mapeada),
        "creditos_grade_aproveitados": creditos_novos_da_grade(grade_mapeada, projetadas, curriculo),
        "pendencias_obrigatorias": sorted(pendentes, key=lambda x: (x["quadrimestre"] or 99, x["codigo"])),
        "metadados": metadados,
    }


def _ajustar_previsao_pelo_curso_base(
    analise: dict[str, Any],
    analise_base: dict[str, Any],
    periodo_planejamento: str,
) -> dict[str, Any]:
    """Impede que um curso específico seja previsto antes do curso de ingresso.

    Os créditos podem se sobrepor, portanto não são somados. A data final usa o
    maior dos dois relógios: integralização do curso específico ou do curso-base.
    """
    est = analise["estimativa_formatura"]
    est_base = analise_base["estimativa_formatura"]
    minimo = max(
        int(est.get("quadrimestres_estimados_incluindo_atual", 1)),
        int(est_base.get("quadrimestres_estimados_incluindo_atual", 1)),
    )
    prudente = max(
        int(est.get("quadrimestres_estimados_prudente", minimo)),
        int(est_base.get("quadrimestres_estimados_prudente", minimo)),
    )
    if minimo > int(est.get("quadrimestres_estimados_incluindo_atual", 1)):
        est.setdefault("gargalos", []).append(
            f"conclusão do curso de ingresso {analise_base['rotulo']} exige ao menos {minimo} quadrimestre(s) incluindo o atual"
        )
    est["quadrimestres_estimados_incluindo_atual"] = minimo
    est["quadrimestres_estimados_prudente"] = prudente
    est["periodo_estimado_minimo"] = proximo_periodo(periodo_planejamento, max(0, minimo - 1))
    est["periodo_estimado_prudente"] = proximo_periodo(periodo_planejamento, max(0, prudente - 1))
    est["curso_base_id"] = analise_base["id"]
    est["curso_base_rotulo"] = analise_base["rotulo"]
    est["quadrimestres_curso_base"] = est_base.get("quadrimestres_estimados_incluindo_atual")
    return analise


def comparar_curriculos(
    base: Path,
    ids: Iterable[str],
    registro_curriculos: dict[str, RegistroCurriculo],
    registros_historico: list[RegistroHistorico],
    convalidacoes_historico: dict[str, str],
    resumo_historico: ResumoHistorico,
    modo_projecao: str,
    codigos_personalizados: Iterable[str],
    estagios_status: dict[str, str],
    grade: Grade | None,
    curriculo_origem: dict[str, DisciplinaCurricular] | None,
    periodo_planejamento: str,
    ritmo: int,
    margem: int,
    quadrimestre_planejado: int | None,
) -> list[dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}

    def obter(id_: str) -> dict[str, Any] | None:
        if id_ not in registro_curriculos:
            return None
        if id_ not in cache:
            cache[id_] = analisar_curriculo(
                base=base,
                registro=registro_curriculos[id_],
                registros_historico=registros_historico,
                convalidacoes_historico=convalidacoes_historico,
                resumo_historico=resumo_historico,
                modo_projecao=modo_projecao,
                codigos_personalizados=codigos_personalizados,
                estagio_status=estagios_status.get(id_, "nao_iniciado"),
                grade=grade,
                curriculo_origem=curriculo_origem,
                periodo_planejamento=periodo_planejamento,
                ritmo=ritmo,
                margem=margem,
                quadrimestre_planejado=quadrimestre_planejado,
            )
        return cache[id_]

    resultados: list[dict[str, Any]] = []
    for id_ in ids:
        analise = obter(id_)
        if analise is None:
            continue
        registro = registro_curriculos[id_]
        if registro.curso_base_id and registro.curso_base_id != id_:
            analise_base = obter(registro.curso_base_id)
            if analise_base is not None:
                analise = _ajustar_previsao_pelo_curso_base(
                    analise, analise_base, periodo_planejamento
                )
        resultados.append(analise)
    return resultados



def selecionar_melhor_sobreposicao(comparacoes_por_grade: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    """Seleciona a grade que gera maior avanço somado nos currículos comparados.

    O total é apenas um indicador de sobreposição: a mesma disciplina pode avançar mais
    de um currículo ao mesmo tempo e não representa créditos adicionais no histórico.
    """
    if not comparacoes_por_grade:
        return None
    chave_melhor, analises_melhor = max(
        comparacoes_por_grade.items(),
        key=lambda item: (
            sum(x.get("creditos_grade_aproveitados", 0) for x in item[1]),
            sum(x.get("estimativa_formatura", {}).get("percentual_conclusao", 0) for x in item[1]),
            item[0],
        ),
    )
    return {
        "assinatura": chave_melhor.split("|") if chave_melhor else [],
        "creditos_aproveitados_somados": sum(x.get("creditos_grade_aproveitados", 0) for x in analises_melhor),
        "cursos_impactados": sum(1 for x in analises_melhor if x.get("creditos_grade_aproveitados", 0) > 0),
        "analises": analises_melhor,
    }

def gerar_relatorio_multicurso_html(caminho: Path, comparacoes: list[dict[str, Any]], periodo: str) -> None:
    cards: list[str] = []
    linhas_resumo: list[str] = []
    for item in comparacoes:
        est = item["estimativa_formatura"]
        aud = item["auditoria"]["por_categoria"]
        meta = item.get("metadados", {})
        categorias = []
        for chave, rotulo in (("obrigatoria", "Obrigatórias"), ("opcao_limitada", "Opção limitada"), ("livre", "Livres")):
            d = aud.get(chave, {})
            categorias.append(
                f"<div class='linha'><span>{rotulo}</span><strong>{d.get('integralizado_estimado',0)} / {d.get('exigido',0)} cr</strong></div>"
            )
        gargalos = "".join(f"<li>{escape(str(g))}</li>" for g in est.get("gargalos", [])) or "<li>Nenhum gargalo adicional identificado.</li>"
        adicionais = []
        if meta.get("atividades_complementares_horas"):
            adicionais.append(
                f"Atividades complementares: {est.get('atividades_complementares_realizadas_horas',0):g} / "
                f"{meta.get('atividades_complementares_horas',0):g} h reconhecidas"
            )
        if meta.get("extensao_horas"):
            adicionais.append(
                f"Extensão: mínimo de {est.get('extensao_reconhecida_minima_horas',0):g} / "
                f"{meta.get('extensao_horas',0):g} h identificadas nas disciplinas"
            )
        if est.get("curso_base_rotulo"):
            adicionais.append(
                f"Curso-base considerado na data final: {est.get('curso_base_rotulo')}"
            )
        adicional_html = "".join(f"<li>{escape(x)}</li>" for x in adicionais) or "<li>Sem requisito adicional cadastrado.</li>"
        total_projecao = meta.get("creditos_disciplinas_e_integralizadores", meta.get("creditos_totais", 0))
        total_oficial = meta.get("creditos_totais_oficiais", meta.get("creditos_totais", 0))
        linhas_resumo.append(
            "<tr>"
            f"<td><strong>{escape(item['rotulo'])}</strong></td>"
            f"<td>{est['periodo_estimado_minimo']}</td>"
            f"<td>{est['periodo_estimado_prudente']}</td>"
            f"<td>{est['percentual_conclusao']}%</td>"
            f"<td>{item.get('creditos_grade_aproveitados',0)} cr</td>"
            "</tr>"
        )
        cards.append(f"""
        <article class='card'>
          <div class='top'><div><span class='grupo'>{escape(item['grupo'])}</span><h2>{escape(item['rotulo'])}</h2></div><div class='prazo'><b>{est['periodo_estimado_minimo']}</b><small>mínimo</small></div></div>
          <div class='progress'><i style='width:{min(100,est['percentual_conclusao'])}%'></i></div>
          <p class='percent'>{est['percentual_conclusao']}% dos créditos de disciplinas e integralizadores estimados após a grade analisada</p>
          <div class='categorias'>{''.join(categorias)}</div>
          <div class='datas'><div><span>Previsão mínima</span><b>{est['periodo_estimado_minimo']}</b></div><div><span>Faixa prudente</span><b>{est['periodo_estimado_prudente']}</b></div><div><span>Quadrimestres</span><b>{est['quadrimestres_estimados_incluindo_atual']}–{est['quadrimestres_estimados_prudente']}</b></div></div>
          <div class='mini'><span>Créditos usados na projeção</span><b>{total_projecao}</b><span>Total oficial do PPC</span><b>{total_oficial}</b><span>Créditos desta grade aproveitados</span><b>{item.get('creditos_grade_aproveitados',0)}</b></div>
          <details><summary>Atividades, extensão e componentes finais</summary><ul>{adicional_html}</ul><p>Estágio obrigatório: {meta.get('estagio_obrigatorio_creditos',0)} cr · Trabalho final: {meta.get('trabalho_final_creditos',0)} cr.</p></details>
          <details><summary>Gargalos e premissas da previsão</summary><ul>{gargalos}</ul><p>{escape(est['observacao'])}</p></details>
        </article>""")
    tabela = "".join(linhas_resumo) or "<tr><td colspan='5'>Nenhum currículo selecionado.</td></tr>"
    html = f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Comparação multicurso</title>
<style>
:root{{--green:#153f31;--green2:#276e55;--ink:#183027;--muted:#64766e;--line:#dbe6df;--bg:#f4f7f5}}
*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}}
header{{background:linear-gradient(135deg,var(--green),var(--green2));color:white;padding:40px max(5vw,24px)}}header h1{{margin:0 0 8px;font-size:2.1rem}}header p{{margin:0;color:#e4f1eb;max-width:850px;line-height:1.5}}
.wrapper{{max-width:1280px;margin:26px auto;padding:0 22px}}.notice{{background:#fff7dc;border-left:4px solid #c99b16;padding:14px 17px;border-radius:8px;margin-bottom:20px;line-height:1.45}}
.summary{{background:white;border:1px solid var(--line);border-radius:16px;padding:18px;overflow:auto;margin-bottom:22px}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{padding:12px;border-bottom:1px solid #edf2ef;text-align:left}}th{{color:#526860;font-size:.82rem;text-transform:uppercase}}
main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:20px}}.card{{background:white;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 10px 28px #163b2d12}}.top{{display:flex;justify-content:space-between;gap:15px}}h2{{margin:4px 0 16px;font-size:1.35rem}}.grupo{{font-size:.76rem;text-transform:uppercase;color:#527064;font-weight:750;letter-spacing:.06em}}.prazo{{background:#e8f3ed;border-radius:14px;padding:10px 14px;text-align:center;min-width:92px}}.prazo b{{display:block;font-size:1.08rem}}.prazo small{{color:#60736b}}.progress{{height:10px;background:#e6ece8;border-radius:99px;overflow:hidden}}.progress i{{display:block;height:100%;background:linear-gradient(90deg,#2d8b66,#71b992)}}.percent{{color:#617069;font-size:.9rem;min-height:38px}}.linha{{display:flex;justify-content:space-between;border-bottom:1px solid #edf2ef;padding:8px 0}}.datas{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0}}.datas div{{background:#f2f6f4;padding:10px;border-radius:10px}}.datas span,.datas b{{display:block}}.datas span{{font-size:.74rem;color:var(--muted)}}.mini{{display:grid;grid-template-columns:1fr auto;gap:7px 12px;background:#f8faf9;border:1px solid #edf2ef;padding:12px;border-radius:10px;font-size:.88rem}}.mini span{{color:var(--muted)}}details{{margin-top:13px;border-top:1px solid #edf2ef;padding-top:11px}}summary{{cursor:pointer;font-weight:700}}li,p{{line-height:1.46}}footer{{max-width:1280px;margin:24px auto 40px;padding:0 22px;color:var(--muted);font-size:.86rem}}
</style></head><body><header><h1>Comparação de trajetórias — UFABC</h1><p>Impacto da grade analisada e estimativa de conclusão a partir de {escape(periodo)}. As projeções consideram disciplinas, recomendações, trabalho final e estágio em paralelo; ofertas futuras e validações administrativas podem alterar o resultado.</p></header><div class='wrapper'><div class='notice'><strong>Como interpretar:</strong> o total oficial de currículos recentes pode incluir extensão e atividades complementares que não são somadas novamente aos créditos de disciplinas. A data é uma estimativa de planejamento, não uma previsão oficial da UFABC.</div><section class='summary'><table><thead><tr><th>Curso</th><th>Mínimo</th><th>Prudente</th><th>Conclusão estimada</th><th>Impacto da grade</th></tr></thead><tbody>{tabela}</tbody></table></section><main>{''.join(cards)}</main></div><footer>Relatório gerado localmente pelo Planejador de Matrícula. Confirme integralização, equivalências, extensão, estágio e trabalho final no SIGAA e com a coordenação do curso.</footer></body></html>"""
    caminho.write_text(html, encoding="utf-8")

