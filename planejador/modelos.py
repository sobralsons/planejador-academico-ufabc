from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Recorrencia(str, Enum):
    SEMANAL = "semanal"
    QUINZENAL_I = "quinzenal_i"
    QUINZENAL_II = "quinzenal_ii"
    DESCONHECIDA = "desconhecida"


class Categoria(str, Enum):
    OBRIGATORIA = "obrigatoria"
    OPCAO_LIMITADA = "opcao_limitada"
    LIVRE = "livre"


class TipoComponente(str, Enum):
    DISCIPLINA_REGULAR = "disciplina_regular"
    ENGENHARIA_UNIFICADA = "engenharia_unificada"
    TRABALHO_GRADUACAO = "trabalho_graduacao"
    ESTAGIO = "estagio"
    ATIVIDADE_COMPLEMENTAR = "atividade_complementar"


class PerfilPlanejamento(str, Enum):
    PADRAO = "padrao"
    PROGRESSAO = "progressao"
    COMPACTA = "compacta"
    EQUILIBRADA = "equilibrada"
    MENOR_CARGA = "menor_carga"
    MAIOR_AVANCO = "maior_avanco"
    MENOR_RISCO = "menor_risco"


@dataclass(frozen=True)
class Horario:
    dia: int
    inicio: int
    fim: int
    recorrencia: Recorrencia
    tipo: str

    def __post_init__(self) -> None:
        if self.dia < 0 or self.dia > 6:
            raise ValueError(f"Dia da semana inválido: {self.dia}")
        if self.inicio >= self.fim:
            raise ValueError(
                f"Intervalo inválido: início={self.inicio}, fim={self.fim}"
            )

    @property
    def duracao_minutos(self) -> int:
        return self.fim - self.inicio


@dataclass(frozen=True)
class DisciplinaCurricular:
    codigo: str
    nome: str
    categoria: Categoria
    creditos: int
    t: int
    p: int
    e: int
    i: int
    quadrimestre_recomendado: int | None = None
    recomendacoes: tuple[str, ...] = ()
    recomendacao_texto: str = ""
    requisito_manual: str = ""
    catalogo_codigo_consulta: str | None = None
    observacoes: tuple[str, ...] = ()

    @property
    def carga_total_referencia(self) -> int:
        return self.t + self.p + self.e + self.i

    @property
    def tipo_componente(self) -> TipoComponente:
        codigo = self.codigo.upper()
        nome = self.nome.upper()
        if "ESTÁGIO" in nome or "ESTAGIO" in nome or codigo.endswith("905-17"):
            return TipoComponente.ESTAGIO
        if any(chave in nome for chave in (
            "TRABALHO DE GRADUAÇÃO", "TRABALHO DE GRADUACAO",
            "TRABALHO DE CONCLUSÃO", "TRABALHO DE CONCLUSAO",
            "PROJETO DE GRADUAÇÃO", "PROJETO DE GRADUACAO",
        )) or codigo == "BCC-TCC-23":
            return TipoComponente.TRABALHO_GRADUACAO
        if any(chave in nome for chave in (
            "ENGENHARIA UNIFICADA", "SOLUÇÕES PARA DESAFIOS EM ENGENHARIA",
            "SOLUCOES PARA DESAFIOS EM ENGENHARIA", "INOVAÇÕES PARA ENGENHARIA",
            "INOVACOES PARA ENGENHARIA",
        )):
            return TipoComponente.ENGENHARIA_UNIFICADA
        return TipoComponente.DISCIPLINA_REGULAR


@dataclass(frozen=True)
class Oferta:
    codigo_ofertado: str
    codigo_curriculo: str
    nome_turma: str
    codigo_turma: str
    campus: str
    turno: str
    creditos: int
    t: int
    p: int
    e: int
    i: int
    horarios: tuple[Horario, ...]
    docentes: tuple[str, ...]
    tpei_original: str
    vagas_totais: int | None = None
    vagas_ingressantes: int | None = None
    vagas_veteranos: int | None = None

    @property
    def carga_total_referencia(self) -> int:
        return self.t + self.p + self.e + self.i

    @property
    def possui_pratica(self) -> bool:
        return self.p > 0 or any(h.tipo == "pratica" for h in self.horarios)


@dataclass(frozen=True)
class RegistroHistorico:
    periodo: str
    categoria_original: str
    codigo: str
    nome: str
    creditos: int
    carga_horaria: int
    carga_extensao: int
    turma: str
    conceito: str
    situacao: str
    docentes: str


@dataclass
class ResumoHistorico:
    periodo_inicial: str = ""
    periodo_atual: str = ""
    curriculo_bct: str = ""
    coeficientes: dict[str, float] = field(default_factory=dict)
    integralizacao_bct_horas: dict[str, dict[str, int]] = field(default_factory=dict)
    atividades_complementares_horas: float | None = None


@dataclass
class SituacaoAcademica:
    concluidas: set[str] = field(default_factory=set)
    em_andamento: set[str] = field(default_factory=set)
    nao_concluidas: set[str] = field(default_factory=set)
    tentativas: dict[str, list[RegistroHistorico]] = field(default_factory=dict)
    convalidacoes_historico: dict[str, str] = field(default_factory=dict)
    resumo: ResumoHistorico = field(default_factory=ResumoHistorico)

    def codigos_projetados(
        self,
        modo: str = "todas",
        codigos_personalizados: Iterable[str] = (),
    ) -> set[str]:
        codigos = set(self.concluidas)
        modo_norm = modo.strip().lower()
        if modo_norm in {"todas", "otimista", "true"}:
            codigos.update(self.em_andamento)
        elif modo_norm in {"personalizada", "personalizado"}:
            permitidas = set(codigos_personalizados)
            codigos.update(self.em_andamento & permitidas)
        elif modo_norm not in {"nenhuma", "conservador", "false"}:
            raise ValueError(
                "Modo de projeção inválido. Use 'todas', 'nenhuma' ou 'personalizada'."
            )
        return codigos


@dataclass(frozen=True)
class MetricasGrade:
    creditos_totais: int
    creditos_obrigatorios: int
    creditos_opcao_limitada: int
    carga_teorica: int
    carga_pratica: int
    carga_extensao: int
    carga_individual: int
    carga_total_referencia: int
    disciplinas_praticas: int
    buracos_minutos: int
    permanencia_total_minutos: int
    tempo_em_aula_minutos: int
    tempo_livre_extremidades_minutos: int
    dias_com_jornada_parcial: int
    dias_com_aula: int
    recomendacoes_faltantes: int
    dependencias_em_andamento: int
    quadrimestres_prioridade: int
    atraso_curricular_total: int
    atraso_curricular_maximo: int
    disciplinas_futuras: int
    desbloqueios_diretos: int
    pendencias_futuras_impactadas: int
    disciplinas_totalmente_destravadas: int
    dias_preferidos_ocupados: int
    docentes_preferidos: int
    docentes_a_evitar: int
    ajuste_avaliacao_docente: float
    docentes_avaliados: int
    docentes_favoraveis: int
    docentes_alerta: int
    qualidade_docente_media: float | None
    risco_docente_medio: float | None
    interesse_formacao: int
    vagas_veteranos_minimas: int | None
    vagas_veteranos_media: float | None


@dataclass(frozen=True)
class Grade:
    ofertas: tuple[Oferta, ...]
    metricas: MetricasGrade
    recomendacoes_faltantes_por_disciplina: dict[str, tuple[str, ...]]
    dependencias_em_andamento_por_disciplina: dict[str, tuple[str, ...]]
    avaliacoes_docentes_por_disciplina: dict[str, tuple[dict, ...]] = field(default_factory=dict)
    perfil: PerfilPlanejamento = PerfilPlanejamento.PADRAO
    rotulo: str = ""

    @property
    def assinatura_disciplinas(self) -> tuple[str, ...]:
        return tuple(sorted(oferta.codigo_curriculo for oferta in self.ofertas))

    @property
    def assinatura_turmas(self) -> tuple[str, ...]:
        return tuple(sorted(oferta.codigo_turma for oferta in self.ofertas))




@dataclass(frozen=True)
class SugestaoAdicao:
    oferta: Oferta
    grade_resultante: Grade
    motivos: tuple[str, ...] = ()

@dataclass(frozen=True)
class DiagnosticoDisciplina:
    codigo: str
    nome: str
    encontrada_na_planilha: bool = False
    encontrada_campus_turno: bool = False
    ofertas_validas: int = 0
    bloqueadas_por_docente: int = 0
    rejeitadas_por_horario: int = 0
    rejeitadas_por_restricao: int = 0
    motivos: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanoQuadrimestre:
    indice: int
    rotulo: str
    codigos: tuple[str, ...]
    creditos: int
    observacao: str = ""


@dataclass(frozen=True)
class ResultadoCenario:
    nome: str
    cumpridas: frozenset[str]
    pendentes_obrigatorias: int
    melhor_grade: Grade | None


@dataclass
class ResultadoPlanejamento:
    grades_pool: list[Grade] = field(default_factory=list)
    grades_padrao: list[Grade] = field(default_factory=list)
    grades_por_perfil: dict[PerfilPlanejamento, Grade] = field(default_factory=dict)
    fronteira_pareto: list[Grade] = field(default_factory=list)
    grade_principal: Grade | None = None
    grades_reserva: list[tuple[str, Grade]] = field(default_factory=list)
    planos_futuros: list[PlanoQuadrimestre] = field(default_factory=list)
    diagnosticos: dict[str, DiagnosticoDisciplina] = field(default_factory=dict)
    cenarios: list[ResultadoCenario] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    validacao_busca: dict = field(default_factory=dict)


def nomes_docentes(ofertas: Iterable[Oferta]) -> set[str]:
    return {
        docente
        for oferta in ofertas
        for docente in oferta.docentes
        if docente
    }
