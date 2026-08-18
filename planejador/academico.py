from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .historico import STATUS_CONCLUIDOS
from .modelos import (
    Categoria,
    DisciplinaCurricular,
    Grade,
    PlanoQuadrimestre,
    RegistroHistorico,
    SituacaoAcademica,
    TipoComponente,
)
from .ofertas import ler_codigos_ofertados
from .utils import normalizar_texto


def _periodo_para_indice(periodo: str) -> int | None:
    achado = re.fullmatch(r"\s*(\d{4})\.(\d)\s*", periodo or "")
    if not achado:
        return None
    ano, quad = int(achado.group(1)), int(achado.group(2))
    if quad not in {1, 2, 3}:
        return None
    return ano * 3 + (quad - 1)


def estimar_quadrimestre_planejado(
    periodo_inicial: str,
    periodo_planejamento: str,
    valor_configurado: int | None = None,
) -> int | None:
    if valor_configurado is not None:
        return valor_configurado
    inicio = _periodo_para_indice(periodo_inicial)
    alvo = _periodo_para_indice(periodo_planejamento)
    if inicio is None or alvo is None or alvo < inicio:
        return None
    return alvo - inicio + 1


def proximo_periodo(periodo: str, passos: int = 1) -> str:
    indice = _periodo_para_indice(periodo)
    if indice is None:
        return f"quadrimestre +{passos}"
    indice += passos
    ano, resto = divmod(indice, 3)
    return f"{ano}.{resto + 1}"


def classificar_area_formacao(disciplina: DisciplinaCurricular) -> tuple[str, ...]:
    texto = normalizar_texto(disciplina.nome)
    areas: list[str] = []
    regras = {
        "metais": ("METAL", "METAIS", "METALURG", "SIDERURG", "ACO", "AÇOS"),
        "polimeros": ("POLIMER", "ELASTOM", "REOLOGIA", "BLENDAS"),
        "ceramicas": ("CERAMIC", "REFRAT"),
        "nanomateriais": ("NANO", "FILMES FINOS"),
        "energia_ambiente": ("ENERGIA", "AMBIENTE", "AMBIENT"),
        "biomateriais": ("BIOMATERIAL", "BIOMATERIAIS"),
        "computacional": ("COMPUT", "ELEMENTOS FINITOS", "DINAMICA MOLECULAR", "MONTE CARLO"),
        "caracterizacao": ("CARACTERIZ", "MICROSCOP", "DIFRAC", "ESPECTRO"),
        "eletronicos": ("ELETRIC", "MAGNET", "OPTIC", "DISPOSITIVOS", "ELETRONIC"),
        "software": ("SOFTWARE", "PROGRAMAC", "PARADIGMAS", "COMPILADOR"),
        "dados_ia": ("DADOS", "APRENDIZADO", "INTELIGENCIA ARTIFICIAL", "MINERAC", "ESTATIST"),
        "redes_comunicacao": ("REDES", "COMUNICAC", "INFORMACAO", "TELECOM", "SINAIS"),
        "sistemas_computacionais": ("SISTEMAS OPERACIONAIS", "ARQUITETURA", "DISTRIBUID", "EMBARCAD"),
        "teoria_computacao": ("ALGORIT", "COMPUTABIL", "COMPLEXIDADE", "GRAFOS", "MATEMATICA DISCRETA"),
        "seguranca": ("SEGURANCA", "CRIPTOGRAF"),
        "multimidia": ("MULTIMIDIA", "VIDEO", "AUDIO", "GRAFIC", "JOGOS"),
    }
    for area, palavras in regras.items():
        if any(palavra in texto for palavra in palavras):
            areas.append(area)
    return tuple(areas or ["generalista"])


def pontuacao_interesse(
    disciplina: DisciplinaCurricular,
    interesses: tuple[str, ...],
) -> int:
    if not interesses:
        return 0
    areas = set(classificar_area_formacao(disciplina))
    interesses_norm = {normalizar_texto(x).lower().replace(" ", "_") for x in interesses}
    return len(areas & interesses_norm)


def calcular_desbloqueios(
    curriculo: dict[str, DisciplinaCurricular],
    pendentes: set[str],
) -> dict[str, int]:
    resultado = defaultdict(int)
    for codigo_pendente in pendentes:
        disciplina = curriculo[codigo_pendente]
        for recomendacao in disciplina.recomendacoes:
            if recomendacao in curriculo:
                resultado[recomendacao] += 1
    return dict(resultado)


def auditoria_integralizacao(
    metadados: dict,
    curriculo: dict[str, DisciplinaCurricular],
    situacao: SituacaoAcademica,
    cumpridas_projetadas: set[str],
    cumpridas_confirmadas: set[str] | None = None,
    estagio_status: str = "nao_iniciado",
) -> dict:
    """Calcula duas leituras separadas da integralização.

    ``cumpridas_confirmadas`` representa apenas componentes efetivamente
    registrados no histórico (ou convalidados oficialmente). Já
    ``cumpridas_projetadas`` pode incluir disciplinas em andamento presumidas
    aprovadas e o estágio informado manualmente. Essa separação evita que uma
    projeção otimista apareça como conclusão oficial.
    """
    confirmadas = set(cumpridas_confirmadas if cumpridas_confirmadas is not None else situacao.concluidas)
    projetadas = set(cumpridas_projetadas)
    concluidas_curriculo_confirmadas = set(curriculo) & confirmadas
    concluidas_curriculo_projetadas = set(curriculo) & projetadas
    por_categoria: dict[str, dict[str, int]] = {}

    for categoria in Categoria:
        exigido_chave = {
            Categoria.OBRIGATORIA: "creditos_obrigatorios",
            Categoria.OPCAO_LIMITADA: "creditos_opcao_limitada",
            Categoria.LIVRE: "creditos_livres",
        }[categoria]
        exigido = int(metadados.get(exigido_chave, 0))
        confirmado = sum(
            curriculo[codigo].creditos
            for codigo in concluidas_curriculo_confirmadas
            if curriculo[codigo].categoria == categoria
        )
        projetado = sum(
            curriculo[codigo].creditos
            for codigo in concluidas_curriculo_projetadas
            if curriculo[codigo].categoria == categoria
        )
        por_categoria[categoria.value] = {
            "exigido": exigido,
            "integralizado_confirmado": min(confirmado, exigido) if exigido else confirmado,
            "integralizado_estimado": min(projetado, exigido) if exigido else projetado,
            "excedente_confirmado": max(0, confirmado - exigido),
            "excedente_estimado": max(0, projetado - exigido),
            "pendente_confirmado": max(0, exigido - confirmado),
            "pendente_estimado": max(0, exigido - projetado),
            # Compatibilidade com relatórios/integrações anteriores: o campo
            # legado reflete o cenário projetado selecionado pelo usuário.
            "integralizado": min(projetado, exigido) if exigido else projetado,
            "pendente": max(0, exigido - projetado),
        }

    # Componentes concluídos fora das listas explícitas da matriz podem preencher
    # os créditos livres. Mantemos a lista e o total para que a estimativa seja
    # transparente e conferível, sem afirmar uma integralização oficial.
    creditos_por_codigo: dict[str, int] = {}
    nomes_por_codigo: dict[str, str] = {}
    for codigo, tentativas in situacao.tentativas.items():
        if codigo in curriculo:
            continue
        concluidas = [r for r in tentativas if r.situacao in STATUS_CONCLUIDOS]
        if concluidas:
            melhor = max(concluidas, key=lambda r: r.creditos)
            if melhor.creditos > 0:
                creditos_por_codigo[codigo] = melhor.creditos
                nomes_por_codigo[codigo] = melhor.nome

    livres_potenciais = sum(creditos_por_codigo.values())
    dados_livres = por_categoria[Categoria.LIVRE.value]
    livres_estimados_adicionais = min(
        max(0, dados_livres["exigido"] - dados_livres["integralizado_estimado"]),
        livres_potenciais,
    )
    dados_livres["integralizado_estimado"] = min(
        dados_livres["exigido"],
        dados_livres["integralizado_estimado"] + livres_estimados_adicionais,
    )
    dados_livres["pendente_estimado"] = max(
        0, dados_livres["exigido"] - dados_livres["integralizado_estimado"]
    )
    dados_livres["integralizado"] = dados_livres["integralizado_estimado"]
    dados_livres["pendente"] = dados_livres["pendente_estimado"]

    # Quadro oficial do SIGAA para o vínculo atual, mantido separado porque as
    # categorias do BC&T não coincidem com as categorias da Engenharia.
    sigaa_vinculo_atual: dict[str, dict[str, int | float]] = {}
    quadro = situacao.resumo.integralizacao_bct_horas
    for categoria in ("obrigatorias", "optativos", "livres", "complementares", "total"):
        exigido_h = int(quadro.get("exigido", {}).get(categoria, 0))
        integralizado_h = int(quadro.get("integralizado", {}).get(categoria, 0))
        pendente_h = int(quadro.get("pendente", {}).get(categoria, max(0, exigido_h - integralizado_h)))
        sigaa_vinculo_atual[categoria] = {
            "exigido_horas": exigido_h,
            "integralizado_horas": integralizado_h,
            "pendente_horas": pendente_h,
            "exigido_creditos_referencia": exigido_h / 12 if exigido_h else 0,
            "integralizado_creditos_referencia": integralizado_h / 12 if integralizado_h else 0,
            "pendente_creditos_referencia": pendente_h / 12 if pendente_h else 0,
        }

    categorias_originais: defaultdict[str, int] = defaultdict(int)
    for codigo, tentativas in situacao.tentativas.items():
        concluidas = [r for r in tentativas if r.situacao in STATUS_CONCLUIDOS]
        if not concluidas:
            continue
        melhor = max(concluidas, key=lambda r: r.creditos)
        categorias_originais[melhor.categoria_original or "SEM_CATEGORIA"] += melhor.creditos

    especiais = {}
    for tipo in (
        TipoComponente.ENGENHARIA_UNIFICADA,
        TipoComponente.TRABALHO_GRADUACAO,
        TipoComponente.ESTAGIO,
    ):
        componentes = [d for d in curriculo.values() if d.tipo_componente == tipo]
        integralizado_confirmado = sum(d.creditos for d in componentes if d.codigo in confirmadas)
        integralizado_projetado = sum(d.creditos for d in componentes if d.codigo in projetadas)
        especiais[tipo.value] = {
            "exigido": sum(d.creditos for d in componentes),
            "integralizado_confirmado": integralizado_confirmado,
            "integralizado_projetado": integralizado_projetado,
            "integralizado": integralizado_projetado,
            "pendentes_confirmados": [d.codigo for d in componentes if d.codigo not in confirmadas],
            "pendentes_projetados": [d.codigo for d in componentes if d.codigo not in projetadas],
            "pendentes": [d.codigo for d in componentes if d.codigo not in projetadas],
        }
    especiais[TipoComponente.ESTAGIO.value]["status_informado"] = estagio_status

    return {
        "por_categoria": por_categoria,
        "componentes_curriculo_concluidos_confirmados": len(concluidas_curriculo_confirmadas),
        "componentes_curriculo_concluidos_projetados": len(concluidas_curriculo_projetadas),
        # Compatibilidade: reflete o cenário projetado.
        "componentes_curriculo_concluidos": len(concluidas_curriculo_projetadas),
        "componentes_historico_concluidos": len(situacao.concluidas),
        "livres_potenciais_fora_da_matriz": livres_potenciais,
        "livres_estimados_adicionais": livres_estimados_adicionais,
        "componentes_livres_potenciais": [
            {"codigo": codigo, "nome": nomes_por_codigo[codigo], "creditos": creditos}
            for codigo, creditos in sorted(creditos_por_codigo.items())
        ],
        "sigaa_vinculo_atual": sigaa_vinculo_atual,
        "categorias_originais_historico_creditos": dict(categorias_originais),
        "curriculo_vinculo_atual": situacao.resumo.curriculo_bct,
        "atividades_complementares_horas": situacao.resumo.atividades_complementares_horas,
        "especiais": especiais,
        "observacao_categorias": (
            "As categorias do histórico do vínculo atual e da matriz selecionada podem não ser equivalentes. "
            "Valores confirmados vêm do histórico; valores projetados também podem incluir aprovações "
            "presumidas e informações manuais."
        ),
    }


def analisar_frequencia_ofertas(
    caminhos: list[Path],
    aliases_oferta: dict[str, str],
) -> tuple[dict[str, dict[str, float | int]], list[str]]:
    if not caminhos:
        return {}, []
    contagem: defaultdict[str, int] = defaultdict(int)
    validos = 0
    avisos: list[str] = []
    for caminho in caminhos:
        try:
            codigos = ler_codigos_ofertados(caminho, aliases_oferta)
        except Exception as erro:  # relatório deve continuar com as demais bases
            avisos.append(f"Não foi possível ler oferta histórica {caminho}: {erro}")
            continue
        validos += 1
        for codigo in codigos:
            contagem[codigo] += 1
    if validos == 0:
        return {}, avisos
    return {
        codigo: {
            "quadrimestres_analisados": validos,
            "vezes_ofertada": vezes,
            "frequencia": vezes / validos,
        }
        for codigo, vezes in contagem.items()
    }, avisos


def rotulo_custo_adiamento(
    codigo: str,
    frequencias: dict[str, dict[str, float | int]],
    atraso: int,
    desbloqueios: int,
) -> str:
    dados = frequencias.get(codigo)
    if dados is None:
        if atraso >= 3 or desbloqueios >= 3:
            return "alto (estimado pela progressão; frequência sem dados)"
        return "não calculado — adicione ofertas históricas"
    freq = float(dados["frequencia"])
    pontos = (1.0 - freq) * 3 + min(atraso, 4) * 0.6 + min(desbloqueios, 5) * 0.4
    if pontos >= 3.5:
        return "muito alto"
    if pontos >= 2.2:
        return "alto"
    if pontos >= 1.1:
        return "médio"
    return "baixo"


def planejar_multiquadrimestres(
    curriculo: dict[str, DisciplinaCurricular],
    cumpridas_iniciais: set[str],
    grade_principal: Grade | None,
    periodo_planejamento: str,
    quadrimestre_planejado: int | None,
    horizonte: int,
    creditos_alvo: int,
    max_creditos: int,
    incluir_opcao_limitada: bool,
    interesses: tuple[str, ...],
) -> list[PlanoQuadrimestre]:
    if horizonte <= 0:
        return []

    cumpridas = set(cumpridas_iniciais)
    planos: list[PlanoQuadrimestre] = []

    if grade_principal is not None:
        codigos = tuple(o.codigo_curriculo for o in grade_principal.ofertas)
        planos.append(
            PlanoQuadrimestre(
                indice=quadrimestre_planejado or 0,
                rotulo=periodo_planejamento or "quadrimestre atual",
                codigos=codigos,
                creditos=grade_principal.metricas.creditos_totais,
                observacao="grade principal calculada com as ofertas e horários reais",
            )
        )
        cumpridas.update(codigos)

    inicio_passo = 1 if grade_principal is not None else 0
    for passo in range(inicio_passo, horizonte):
        indice_q = (quadrimestre_planejado + passo) if quadrimestre_planejado else passo + 1
        candidatos = [
            d
            for d in curriculo.values()
            if d.codigo not in cumpridas
            and d.tipo_componente == TipoComponente.DISCIPLINA_REGULAR
            and (
                d.categoria == Categoria.OBRIGATORIA
                or (incluir_opcao_limitada and d.categoria == Categoria.OPCAO_LIMITADA)
            )
        ]
        pendentes = {d.codigo for d in candidatos}
        desbloqueios = calcular_desbloqueios(curriculo, pendentes)

        def prioridade(d: DisciplinaCurricular) -> tuple:
            faltantes = len([r for r in d.recomendacoes if r not in cumpridas])
            atraso = max(0, indice_q - (d.quadrimestre_recomendado or indice_q))
            futura = max(0, (d.quadrimestre_recomendado or indice_q) - indice_q)
            interesse = pontuacao_interesse(d, interesses)
            return (
                faltantes,
                0 if d.categoria == Categoria.OBRIGATORIA else 1,
                -atraso,
                -desbloqueios.get(d.codigo, 0),
                -interesse,
                futura,
                d.quadrimestre_recomendado or 99,
                d.codigo,
            )

        escolhidas: list[DisciplinaCurricular] = []
        total = 0
        for disciplina in sorted(candidatos, key=prioridade):
            if total + disciplina.creditos > max_creditos:
                continue
            escolhidas.append(disciplina)
            total += disciplina.creditos
            if total >= creditos_alvo:
                break

        if not escolhidas:
            break
        codigos = tuple(d.codigo for d in escolhidas)
        planos.append(
            PlanoQuadrimestre(
                indice=indice_q,
                rotulo=proximo_periodo(periodo_planejamento, passo) if periodo_planejamento else f"Q{indice_q}",
                codigos=codigos,
                creditos=total,
                observacao=(
                    "projeção curricular aproximada; não garante que as disciplinas "
                    "serão ofertadas nem que os horários serão compatíveis"
                ),
            )
        )
        cumpridas.update(codigos)

    return planos
