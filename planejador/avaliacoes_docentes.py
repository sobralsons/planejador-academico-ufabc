from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .modelos import DisciplinaCurricular, Oferta
from .utils import normalizar_texto


PESOS_IMPORTANCIA = {
    "nao_considerar": 0.0,
    "baixa": 0.5,
    "media": 1.0,
    "alta": 1.5,
}

PESOS_CONFIANCA = {
    "baixa": 0.55,
    "média": 0.80,
    "media": 0.80,
    "alta": 1.0,
}


def codigo_base(codigo: str) -> str:
    return re.sub(r"-\d{2}$", "", str(codigo or "").strip().upper())


@dataclass(frozen=True)
class AvaliacaoDocente:
    professor: str
    professor_normalizado: str
    aliases_normalizados: tuple[str, ...]
    codigo_disciplina: str
    nome_disciplina: str
    fonte: str
    classificacao: str
    qualidade_pedagogica: str
    risco_academico: str
    risco_score_0_100: float | None
    score_0_100: float | None
    efeito_ranking_original: float
    efeito_ranking_aplicado: float
    confianca: str
    conceitos: int
    comentarios: int
    taxa_f_ou_o: float | None
    cr_professor: float | None
    cr_medio_disciplina: float | None
    diferenca_cr: float | None
    gerado_em_utc: str = ""

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BaseAvaliacoesDocentes:
    por_professor_disciplina: dict[tuple[str, str], AvaliacaoDocente]
    geral_por_professor: dict[str, AvaliacaoDocente]
    avisos: list[str]
    gerado_em_utc: str = ""

    @property
    def quantidade(self) -> int:
        unicas = {
            (a.professor_normalizado, a.codigo_disciplina, a.fonte)
            for a in list(self.por_professor_disciplina.values()) + list(self.geral_por_professor.values())
        }
        return len(unicas)

    def localizar(self, professor: str, codigo_disciplina: str) -> AvaliacaoDocente | None:
        professor_norm = normalizar_texto(professor)
        codigo = codigo_base(codigo_disciplina)
        return (
            self.por_professor_disciplina.get((professor_norm, codigo))
            or self.geral_por_professor.get(professor_norm)
        )

    @classmethod
    def vazia(cls) -> "BaseAvaliacoesDocentes":
        return cls({}, {}, [])


def _num(valor: Any) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _int(valor: Any) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _efeito_aplicado(
    efeito: float,
    importancia: str,
    confianca: str,
    conceitos: int,
    comentarios: int,
    minimo_conceitos: int,
    minimo_comentarios: int,
) -> float:
    peso_importancia = PESOS_IMPORTANCIA.get(str(importancia).lower(), 1.0)
    peso_confianca = PESOS_CONFIANCA.get(str(confianca).lower(), 0.7)

    # Amostras pequenas não são ignoradas, mas seu impacto é reduzido.
    if conceitos < minimo_conceitos and comentarios < minimo_comentarios:
        peso_amostra = 0.35
    elif conceitos < minimo_conceitos or comentarios < minimo_comentarios:
        peso_amostra = 0.65
    else:
        peso_amostra = 1.0
    return round(float(efeito) * peso_importancia * peso_confianca * peso_amostra, 3)


def _avaliacao_de_bloco(
    item: dict[str, Any],
    bloco: dict[str, Any],
    fonte: str,
    codigo: str,
    nome_disciplina: str,
    gerado_em_utc: str,
    importancia: str,
    minimo_conceitos: int,
    minimo_comentarios: int,
) -> AvaliacaoDocente | None:
    resultado = bloco.get("resultado") or {}
    metricas = bloco.get("metricas") or {}
    comentarios_bloco = bloco.get("comentarios") or {}
    if not resultado:
        return None

    professor_info = item.get("professor") or {}
    professor = str(professor_info.get("nome") or item.get("consulta", {}).get("professor") or "").strip()
    if not professor:
        return None
    aliases = tuple(
        normalizar_texto(a)
        for a in professor_info.get("aliases", [])
        if str(a).strip()
    )
    professor_norm = normalizar_texto(professor)
    confianca = str(resultado.get("confianca") or "baixa")
    conceitos = _int(metricas.get("conceitos"))
    comentarios = _int(comentarios_bloco.get("quantidade"))
    efeito_original = float(resultado.get("efeito_ranking") or 0)
    efeito_aplicado = _efeito_aplicado(
        efeito_original,
        importancia,
        confianca,
        conceitos,
        comentarios,
        minimo_conceitos,
        minimo_comentarios,
    )
    risco = resultado.get("risco_academico") or {}
    return AvaliacaoDocente(
        professor=professor,
        professor_normalizado=professor_norm,
        aliases_normalizados=aliases,
        codigo_disciplina=codigo_base(codigo),
        nome_disciplina=str(nome_disciplina or "").strip(),
        fonte=fonte,
        classificacao=str(resultado.get("classificacao") or "sem classificação"),
        qualidade_pedagogica=str(resultado.get("qualidade_pedagogica") or "sem dados"),
        risco_academico=str(risco.get("classificacao") or "sem dados"),
        risco_score_0_100=_num(risco.get("score_0_100")),
        score_0_100=_num(resultado.get("score_0_100")),
        efeito_ranking_original=efeito_original,
        efeito_ranking_aplicado=efeito_aplicado,
        confianca=confianca,
        conceitos=conceitos,
        comentarios=comentarios,
        taxa_f_ou_o=_num(risco.get("taxa_f_ou_o")),
        cr_professor=_num(metricas.get("cr_professor")),
        cr_medio_disciplina=_num(metricas.get("cr_medio_disciplina")),
        diferenca_cr=_num(metricas.get("diferenca_cr")),
        gerado_em_utc=gerado_em_utc,
    )


def carregar_avaliacoes_docentes(
    caminho: str | Path | None,
    habilitado: bool = True,
    importancia: str = "media",
    minimo_conceitos: int = 10,
    minimo_comentarios: int = 3,
    usar_avaliacao_especifica: bool = True,
) -> BaseAvaliacoesDocentes:
    if not habilitado or not caminho:
        return BaseAvaliacoesDocentes.vazia()
    path = Path(caminho)
    if not path.exists():
        return BaseAvaliacoesDocentes({}, {}, [f"Arquivo de avaliações docentes não encontrado: {path}"])

    try:
        bruto = json.loads(path.read_text(encoding="utf-8"))
    except Exception as erro:
        return BaseAvaliacoesDocentes({}, {}, [f"Não foi possível ler avaliações docentes: {erro}"])

    por_especifica: dict[tuple[str, str], AvaliacaoDocente] = {}
    gerais: dict[str, AvaliacaoDocente] = {}
    avisos: list[str] = []
    gerado_em_utc = str(bruto.get("gerado_em_utc") or "")

    for item in bruto.get("resultados", []):
        if not item.get("encontrado"):
            consulta = item.get("consulta") or {}
            avisos.append(f"Avaliação não encontrada para {consulta.get('professor', 'docente desconhecido')}.")
            continue
        consulta = item.get("consulta") or {}
        geral = _avaliacao_de_bloco(
            item,
            item.get("avaliacao_geral") or {},
            "geral",
            "",
            "Avaliação geral",
            gerado_em_utc,
            importancia,
            minimo_conceitos,
            minimo_comentarios,
        )
        if geral:
            for nome_norm in {geral.professor_normalizado, *geral.aliases_normalizados}:
                gerais[nome_norm] = geral

        especifica = item.get("avaliacao_disciplina") or {}
        if usar_avaliacao_especifica and especifica.get("encontrada"):
            codigos = especifica.get("codigos") or [consulta.get("disciplina_codigo", "")]
            nome_disciplina = especifica.get("nome") or consulta.get("disciplina_nome", "")
            for codigo in codigos:
                avaliacao = _avaliacao_de_bloco(
                    item,
                    especifica,
                    "disciplina",
                    str(codigo),
                    str(nome_disciplina),
                    gerado_em_utc,
                    importancia,
                    minimo_conceitos,
                    minimo_comentarios,
                )
                if not avaliacao:
                    continue
                nomes = {avaliacao.professor_normalizado, *avaliacao.aliases_normalizados}
                for nome_norm in nomes:
                    por_especifica[(nome_norm, avaliacao.codigo_disciplina)] = avaliacao

            codigo_consulta = consulta.get("disciplina_codigo")
            if codigo_consulta:
                avaliacao = _avaliacao_de_bloco(
                    item,
                    especifica,
                    "disciplina",
                    str(codigo_consulta),
                    str(nome_disciplina),
                    gerado_em_utc,
                    importancia,
                    minimo_conceitos,
                    minimo_comentarios,
                )
                if avaliacao:
                    for nome_norm in {avaliacao.professor_normalizado, *avaliacao.aliases_normalizados}:
                        por_especifica[(nome_norm, avaliacao.codigo_disciplina)] = avaliacao

    if not por_especifica and not gerais:
        avisos.append("Nenhuma avaliação docente válida foi carregada.")
    return BaseAvaliacoesDocentes(por_especifica, gerais, avisos, gerado_em_utc)


def avaliacoes_para_oferta(
    oferta: Oferta,
    base: BaseAvaliacoesDocentes,
) -> tuple[AvaliacaoDocente, ...]:
    resultados: list[AvaliacaoDocente] = []
    vistos: set[tuple[str, str]] = set()
    for professor in oferta.docentes:
        avaliacao = base.localizar(professor, oferta.codigo_curriculo)
        if not avaliacao:
            continue
        chave = (avaliacao.professor_normalizado, avaliacao.codigo_disciplina or "GERAL")
        if chave not in vistos:
            vistos.add(chave)
            resultados.append(avaliacao)
    return tuple(resultados)


def gerar_consultas_csv(
    caminho: str | Path,
    ofertas: Iterable[Oferta],
    curriculo: dict[str, DisciplinaCurricular],
    codigos_permitidos: set[str] | None = None,
) -> int:
    pares: set[tuple[str, str, str]] = set()
    for oferta in ofertas:
        if codigos_permitidos is not None and oferta.codigo_curriculo not in codigos_permitidos:
            continue
        disciplina = curriculo.get(oferta.codigo_curriculo)
        nome = disciplina.nome if disciplina else oferta.nome_turma
        for professor in oferta.docentes:
            if professor.strip():
                pares.add((professor.strip(), oferta.codigo_curriculo, nome))
    path = Path(caminho)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=["professor", "disciplina_codigo", "disciplina_nome"],
        )
        escritor.writeheader()
        for professor, codigo, nome in sorted(pares):
            escritor.writerow({
                "professor": professor,
                "disciplina_codigo": codigo,
                "disciplina_nome": nome,
            })
    return len(pares)


def resumo_avaliacoes(base: BaseAvaliacoesDocentes) -> list[dict[str, Any]]:
    unicas: dict[tuple[str, str, str], AvaliacaoDocente] = {}
    for avaliacao in list(base.por_professor_disciplina.values()) + list(base.geral_por_professor.values()):
        chave = (avaliacao.professor_normalizado, avaliacao.codigo_disciplina, avaliacao.fonte)
        unicas[chave] = avaliacao
    return [a.para_dict() for a in sorted(unicas.values(), key=lambda x: (x.professor, x.codigo_disciplina, x.fonte))]
