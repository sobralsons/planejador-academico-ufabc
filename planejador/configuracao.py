from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .modelos import PerfilPlanejamento
from .utils import limpar_codigo, normalizar_texto


DIAS_CONFIG = {
    "SEGUNDA": 0,
    "TERCA": 1,
    "TERÇA": 1,
    "QUARTA": 2,
    "QUINTA": 3,
    "SEXTA": 4,
    "SABADO": 5,
    "SÁBADO": 5,
    "DOMINGO": 6,
}


def _hora_minutos(valor: str | None, padrao: int) -> int:
    if not valor:
        return padrao
    hora, minuto = map(int, str(valor).split(":"))
    return hora * 60 + minuto


def _dias(valores: list | tuple | None) -> tuple[int, ...]:
    resultado: list[int] = []
    for valor in valores or []:
        if isinstance(valor, int):
            dia = valor
        else:
            chave = normalizar_texto(valor)
            if chave not in DIAS_CONFIG:
                raise ValueError(f"Dia inválido na configuração: {valor}")
            dia = DIAS_CONFIG[chave]
        if dia not in resultado:
            resultado.append(dia)
    return tuple(resultado)


@dataclass(frozen=True)
class RestricoesConfig:
    dias_indisponiveis: tuple[int, ...] = ()
    horario_mais_cedo: int = 0
    horario_mais_tarde: int = 24 * 60
    disciplinas_obrigatorias_na_grade: tuple[str, ...] = ()
    disciplinas_proibidas: tuple[str, ...] = ()
    max_disciplinas_praticas: int | None = None
    incluir_componentes_especiais_na_grade: bool = False


@dataclass(frozen=True)
class PreferenciasConfig:
    horario_referencia_inicio: int = 0
    horario_referencia_fim: int = 24 * 60
    dias_preferidos_sem_aula: tuple[int, ...] = ()
    maximo_dias_preferido: int | None = None
    max_carga_individual_preferida: int | None = None
    max_disciplinas_praticas_preferida: int | None = None
    professores_preferidos: tuple[str, ...] = ()
    professores_a_evitar: tuple[str, ...] = ()
    interesses_formacao: tuple[str, ...] = ()
    considerar_aprovacoes_projetadas_como_cumpridas: bool = True


@dataclass(frozen=True)
class AvaliacoesDocentesConfig:
    habilitado: bool = False
    arquivo: str = "dados/avaliacoes_docentes.json"
    importancia: str = "media"
    usar_avaliacao_especifica: bool = True
    minimo_conceitos: int = 10
    minimo_comentarios: int = 3
    mostrar_no_relatorio: bool = True


@dataclass(frozen=True)
class ConfiguracaoAplicacao:
    arquivo_ofertas: str
    arquivo_historico: str
    arquivo_curriculo: str
    arquivo_equivalencias: str
    arquivo_aliases_oferta: str
    arquivos_ofertas_historicas: tuple[str, ...]
    arquivo_registro_curriculos: str
    curriculo_principal_id: str
    curriculos_comparacao: tuple[str, ...]
    modo_multicurso: str
    trajetoria_curso_atual_id: str
    trajetoria_ordem_ids: tuple[str, ...]
    trajetoria_estrategia: str
    gerar_relatorio_trajetoria: bool
    estagios_status: dict[str, str]
    campus: str
    turno: str
    professores_bloqueados: tuple[str, ...]
    min_creditos: int
    max_creditos: int
    creditos_alvo: int
    min_creditos_flexivel: int
    top_n: int
    min_opcoes_padrao: int
    max_solucoes_pool: int
    max_disciplinas_candidatas: int
    projecao_em_andamento: str
    disciplinas_em_andamento_assumidas_aprovadas: tuple[str, ...]
    incluir_opcao_limitada: bool
    periodo_planejamento: str
    quadrimestre_planejado: int | None
    perfis_gerados: tuple[PerfilPlanejamento, ...]
    gerar_fronteira_pareto: bool
    gerar_grades_reserva: bool
    gerar_cenarios_comparativos: bool
    gerar_planejamento_multiquadrimestral: bool
    horizonte_quadrimestres: int
    creditos_futuros_por_quadrimestre: int
    margem_formatura_quadrimestres: int
    estagio_status: str
    gerar_analise_desempenho: bool
    avaliacoes_docentes: AvaliacoesDocentesConfig
    restricoes: RestricoesConfig
    preferencias: PreferenciasConfig


def carregar_configuracao(caminho: str | Path) -> ConfiguracaoAplicacao:
    path = Path(caminho)
    with path.open("r", encoding="utf-8") as arquivo:
        bruto = json.load(arquivo)

    restricoes_bruto = bruto.get("restricoes", {})
    preferencias_bruto = bruto.get("preferencias", {})
    avaliacoes_bruto = bruto.get("avaliacoes_docentes", {})

    # Compatibilidade com a primeira versão do projeto.
    if "projecao_em_andamento" in bruto:
        projecao = str(bruto["projecao_em_andamento"]).lower()
    else:
        projecao = "todas" if bool(bruto.get("assumir_aprovacao_em_andamento", True)) else "nenhuma"

    top_n = max(3, int(bruto.get("top_n", 5)))
    min_opcoes = max(3, min(top_n, int(bruto.get("min_opcoes_padrao", 3))))

    estagio_status = str(bruto.get("estagio_status", "nao_iniciado")).strip().lower()
    aliases_estagio = {
        "nao": "nao_iniciado",
        "não": "nao_iniciado",
        "nao_iniciado": "nao_iniciado",
        "não_iniciado": "nao_iniciado",
        "em_andamento": "em_andamento",
        "andamento": "em_andamento",
        "concluido": "concluido",
        "concluído": "concluido",
        "validado": "concluido",
    }
    if estagio_status not in aliases_estagio:
        raise ValueError(
            "estagio_status inválido. Use 'nao_iniciado', 'em_andamento' ou 'concluido'."
        )
    estagio_status = aliases_estagio[estagio_status]

    estagios_status: dict[str, str] = {}
    for curso_id, valor in bruto.get("estagios_status", {}).items():
        chave = str(valor).strip().lower()
        if chave not in aliases_estagio:
            raise ValueError(f"Status de estágio inválido para {curso_id}: {valor}")
        estagios_status[str(curso_id)] = aliases_estagio[chave]
    curriculo_principal_id = str(bruto.get("curriculo_principal_id", "materiais_2017"))
    estagios_status.setdefault(curriculo_principal_id, estagio_status)
    modo_multicurso = str(bruto.get("modo_multicurso", "comparar")).strip().lower()
    if modo_multicurso not in {"principal", "comparar", "maximizar_sobreposicao"}:
        raise ValueError("modo_multicurso inválido.")

    trajetoria_bruto = bruto.get("trajetoria", {}) or {}
    trajetoria_curso_atual_id = str(trajetoria_bruto.get("curso_atual_id", curriculo_principal_id))
    trajetoria_ordem_ids_lista = []
    for item in trajetoria_bruto.get("ordem_ids", bruto.get("curriculos_comparacao", [curriculo_principal_id])):
        valor = str(item)
        if valor not in trajetoria_ordem_ids_lista:
            trajetoria_ordem_ids_lista.append(valor)
    if curriculo_principal_id not in trajetoria_ordem_ids_lista:
        trajetoria_ordem_ids_lista.insert(0, curriculo_principal_id)
    trajetoria_ordem_ids_lista = trajetoria_ordem_ids_lista[:3]
    trajetoria_estrategia = str(trajetoria_bruto.get("estrategia", "hibrida")).strip().lower()
    if trajetoria_estrategia not in {"simultanea", "hibrida", "sequencial"}:
        raise ValueError("Estratégia de trajetória inválida.")

    perfis: list[PerfilPlanejamento] = []
    for item in bruto.get(
        "perfis_gerados",
        ["progressao", "compacta", "equilibrada", "menor_carga", "maior_avanco", "menor_risco"],
    ):
        perfil = PerfilPlanejamento(str(item).lower())
        if perfil != PerfilPlanejamento.PADRAO and perfil not in perfis:
            perfis.append(perfil)

    restricoes = RestricoesConfig(
        dias_indisponiveis=_dias(restricoes_bruto.get("dias_indisponiveis", [])),
        horario_mais_cedo=_hora_minutos(restricoes_bruto.get("horario_mais_cedo"), 0),
        horario_mais_tarde=_hora_minutos(restricoes_bruto.get("horario_mais_tarde"), 24 * 60),
        disciplinas_obrigatorias_na_grade=tuple(
            limpar_codigo(c) for c in restricoes_bruto.get("disciplinas_obrigatorias_na_grade", [])
        ),
        disciplinas_proibidas=tuple(
            limpar_codigo(c) for c in restricoes_bruto.get("disciplinas_proibidas", [])
        ),
        max_disciplinas_praticas=(
            int(restricoes_bruto["max_disciplinas_praticas"])
            if restricoes_bruto.get("max_disciplinas_praticas") is not None
            else None
        ),
        incluir_componentes_especiais_na_grade=bool(
            restricoes_bruto.get("incluir_componentes_especiais_na_grade", False)
        ),
    )

    importancia_docentes = str(avaliacoes_bruto.get("importancia", "media")).strip().lower()
    if importancia_docentes not in {"nao_considerar", "baixa", "media", "alta"}:
        raise ValueError("Importância das avaliações docentes inválida.")
    avaliacoes_docentes = AvaliacoesDocentesConfig(
        habilitado=bool(avaliacoes_bruto.get("habilitado", False)),
        arquivo=str(avaliacoes_bruto.get("arquivo", "dados/avaliacoes_docentes.json")),
        importancia=importancia_docentes,
        usar_avaliacao_especifica=bool(avaliacoes_bruto.get("usar_avaliacao_especifica", True)),
        minimo_conceitos=max(0, int(avaliacoes_bruto.get("minimo_conceitos", 10))),
        minimo_comentarios=max(0, int(avaliacoes_bruto.get("minimo_comentarios", 3))),
        mostrar_no_relatorio=bool(avaliacoes_bruto.get("mostrar_no_relatorio", True)),
    )

    preferencias = PreferenciasConfig(
        horario_referencia_inicio=restricoes.horario_mais_cedo,
        horario_referencia_fim=restricoes.horario_mais_tarde,
        dias_preferidos_sem_aula=_dias(preferencias_bruto.get("dias_preferidos_sem_aula", [])),
        maximo_dias_preferido=(
            int(preferencias_bruto["maximo_dias_preferido"])
            if preferencias_bruto.get("maximo_dias_preferido") is not None
            else None
        ),
        max_carga_individual_preferida=(
            int(preferencias_bruto["max_carga_individual_preferida"])
            if preferencias_bruto.get("max_carga_individual_preferida") is not None
            else None
        ),
        max_disciplinas_praticas_preferida=(
            int(preferencias_bruto["max_disciplinas_praticas_preferida"])
            if preferencias_bruto.get("max_disciplinas_praticas_preferida") is not None
            else None
        ),
        professores_preferidos=tuple(
            normalizar_texto(p) for p in preferencias_bruto.get("professores_preferidos", [])
        ),
        professores_a_evitar=tuple(
            normalizar_texto(p) for p in preferencias_bruto.get("professores_a_evitar", [])
        ),
        interesses_formacao=tuple(
            normalizar_texto(a).lower() for a in preferencias_bruto.get("interesses_formacao", [])
        ),
        considerar_aprovacoes_projetadas_como_cumpridas=bool(
            preferencias_bruto.get("considerar_aprovacoes_projetadas_como_cumpridas", True)
        ),
    )

    return ConfiguracaoAplicacao(
        arquivo_ofertas=bruto["arquivo_ofertas"],
        arquivo_historico=bruto["arquivo_historico"],
        arquivo_curriculo=bruto["arquivo_curriculo"],
        arquivo_equivalencias=bruto["arquivo_equivalencias"],
        arquivo_aliases_oferta=bruto["arquivo_aliases_oferta"],
        arquivos_ofertas_historicas=tuple(bruto.get("arquivos_ofertas_historicas", [])),
        arquivo_registro_curriculos=str(bruto.get("arquivo_registro_curriculos", "dados/registro_curriculos.json")),
        curriculo_principal_id=curriculo_principal_id,
        curriculos_comparacao=tuple(str(x) for x in bruto.get("curriculos_comparacao", [curriculo_principal_id])),
        modo_multicurso=modo_multicurso,
        trajetoria_curso_atual_id=trajetoria_curso_atual_id,
        trajetoria_ordem_ids=tuple(trajetoria_ordem_ids_lista),
        trajetoria_estrategia=trajetoria_estrategia,
        gerar_relatorio_trajetoria=bool(trajetoria_bruto.get("gerar_relatorio", True)),
        estagios_status=estagios_status,
        campus=bruto.get("campus", "SA"),
        turno=bruto.get("turno", "Noturno"),
        professores_bloqueados=tuple(bruto.get("professores_bloqueados", [])),
        min_creditos=int(bruto.get("min_creditos", 14)),
        max_creditos=int(bruto.get("max_creditos", 20)),
        creditos_alvo=int(bruto.get("creditos_alvo", 16)),
        min_creditos_flexivel=int(bruto.get("min_creditos_flexivel", 12)),
        top_n=top_n,
        min_opcoes_padrao=min_opcoes,
        max_solucoes_pool=int(bruto.get("max_solucoes_pool", 5000)),
        max_disciplinas_candidatas=int(bruto.get("max_disciplinas_candidatas", 24)),
        projecao_em_andamento=projecao,
        disciplinas_em_andamento_assumidas_aprovadas=tuple(
            limpar_codigo(c)
            for c in bruto.get("disciplinas_em_andamento_assumidas_aprovadas", [])
        ),
        incluir_opcao_limitada=bool(bruto.get("incluir_opcao_limitada", True)),
        periodo_planejamento=str(bruto.get("periodo_planejamento", "")),
        quadrimestre_planejado=(
            int(bruto["quadrimestre_planejado"])
            if bruto.get("quadrimestre_planejado") is not None
            else None
        ),
        perfis_gerados=tuple(perfis),
        gerar_fronteira_pareto=bool(bruto.get("gerar_fronteira_pareto", True)),
        gerar_grades_reserva=bool(bruto.get("gerar_grades_reserva", True)),
        gerar_cenarios_comparativos=bool(bruto.get("gerar_cenarios_comparativos", True)),
        gerar_planejamento_multiquadrimestral=bool(
            bruto.get("gerar_planejamento_multiquadrimestral", True)
        ),
        horizonte_quadrimestres=max(1, int(bruto.get("horizonte_quadrimestres", 3))),
        creditos_futuros_por_quadrimestre=max(1, int(bruto.get("creditos_futuros_por_quadrimestre", bruto.get("creditos_alvo", 16)))),
        margem_formatura_quadrimestres=max(0, int(bruto.get("margem_formatura_quadrimestres", 1))),
        estagio_status=estagio_status,
        gerar_analise_desempenho=bool(bruto.get("gerar_analise_desempenho", True)),
        avaliacoes_docentes=avaliacoes_docentes,
        restricoes=restricoes,
        preferencias=preferencias,
    )
