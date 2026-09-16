from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


APLICABILIDADES_RESOLVIDAS = frozenset({"aplicavel", "nao_aplicavel"})


@dataclass(frozen=True)
class RelatorioCoberturaPublica:
    liberacao_permitida: bool
    cursos_total: int
    cursos_com_levantamento_incompleto: tuple[str, ...]
    matrizes_total: int
    matrizes_com_aplicabilidade_pendente: tuple[str, ...]
    matrizes_aplicaveis: int
    matrizes_aplicaveis_nao_validadas: tuple[str, ...]
    inconsistencias: tuple[str, ...]

    @property
    def impedimentos(self) -> tuple[str, ...]:
        itens: list[str] = []
        if self.cursos_com_levantamento_incompleto:
            itens.append(
                f"{len(self.cursos_com_levantamento_incompleto)} curso(s) sem "
                "levantamento completo de matrizes"
            )
        if self.matrizes_com_aplicabilidade_pendente:
            itens.append(
                f"{len(self.matrizes_com_aplicabilidade_pendente)} matriz(es) "
                "com aplicabilidade pendente"
            )
        if self.matrizes_aplicaveis_nao_validadas:
            itens.append(
                f"{len(self.matrizes_aplicaveis_nao_validadas)} matriz(es) "
                "aplicável(is) sem validação completa"
            )
        itens.extend(self.inconsistencias)
        return tuple(itens)


def avaliar_cobertura_publica(
    inventario: Mapping[str, Any],
) -> RelatorioCoberturaPublica:
    """Calcula se o inventário acadêmico satisfaz o critério de publicação.

    A função não confia em um indicador pronto no JSON. A liberação é sempre
    recalculada a partir da completude do levantamento e do estado de cada
    matriz, evitando que um sinalizador fique desatualizado.
    """
    cursos = inventario.get("cursos", [])
    inconsistencias: list[str] = []

    if not isinstance(cursos, list) or not cursos:
        cursos = []
        inconsistencias.append("inventário sem cursos")

    total_declarado = inventario.get("total_cursos")
    if total_declarado != len(cursos):
        inconsistencias.append(
            "total de cursos declarado difere da quantidade inventariada"
        )

    cursos_incompletos: list[str] = []
    pendentes: list[str] = []
    aplicaveis_nao_validadas: list[str] = []
    matrizes_total = 0
    matrizes_aplicaveis = 0

    for curso in cursos:
        course_id = str(curso.get("id", "curso_sem_id"))
        matrizes = curso.get("matrizes", [])

        if curso.get("levantamento_matrizes") != "concluido":
            cursos_incompletos.append(course_id)
        if not isinstance(matrizes, list) or not matrizes:
            inconsistencias.append(f"curso {course_id} sem matrizes inventariadas")
            continue

        for matriz in matrizes:
            matrizes_total += 1
            matrix_id = str(matriz.get("id", f"{course_id}:matriz_sem_id"))
            aplicabilidade = matriz.get("aplicabilidade")

            if aplicabilidade not in APLICABILIDADES_RESOLVIDAS:
                pendentes.append(matrix_id)
                continue
            if aplicabilidade == "nao_aplicavel":
                continue

            matrizes_aplicaveis += 1
            validada = (
                matriz.get("modelagem") == "concluida"
                and matriz.get("testes") == "aprovados"
                and matriz.get("revisao_humana") == "aprovada"
                and bool(matriz.get("evidencias_aplicabilidade"))
            )
            if not validada:
                aplicaveis_nao_validadas.append(matrix_id)

    liberacao_permitida = not (
        cursos_incompletos
        or pendentes
        or aplicaveis_nao_validadas
        or inconsistencias
    )

    return RelatorioCoberturaPublica(
        liberacao_permitida=liberacao_permitida,
        cursos_total=len(cursos),
        cursos_com_levantamento_incompleto=tuple(cursos_incompletos),
        matrizes_total=matrizes_total,
        matrizes_com_aplicabilidade_pendente=tuple(pendentes),
        matrizes_aplicaveis=matrizes_aplicaveis,
        matrizes_aplicaveis_nao_validadas=tuple(aplicaveis_nao_validadas),
        inconsistencias=tuple(inconsistencias),
    )
