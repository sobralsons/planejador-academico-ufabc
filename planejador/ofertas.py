from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .modelos import DiagnosticoDisciplina, Horario, Oferta, Recorrencia
from .utils import garantir_arquivo, limpar_codigo, normalizar_texto, possui_valor

DIAS = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}

COLUNAS_DOCENTES = (
    "DOCENTE TEORIA",
    "DOCENTE TEORIA 2",
    "DOCENTE TEORIA 3",
    "DOCENTE PRÁTICA",
    "DOCENTE PRÁTICA 2",
    "DOCENTE PRÁTICA 3",
)

PADRAO_HORARIO = re.compile(
    r"(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\s+"
    r"das\s+(\d{1,2}:\d{2})\s+(?:as|a)\s+(\d{1,2}:\d{2})"
    r"(?:\s*,\s*(semanal|quinzenal\s+i{1,2}))?",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ResultadoLeituraOfertas:
    ofertas: tuple[Oferta, ...]
    avisos: tuple[str, ...]
    diagnosticos: dict[str, DiagnosticoDisciplina]


def _normalizar_minusculo(valor: object) -> str:
    return normalizar_texto(valor).lower()


def _hora_para_minutos(valor: str) -> int:
    hora, minuto = map(int, valor.split(":"))
    return hora * 60 + minuto


def _recorrencia(valor: str | None) -> Recorrencia:
    if not valor:
        return Recorrencia.DESCONHECIDA
    normalizado = _normalizar_minusculo(valor)
    if normalizado == "semanal":
        return Recorrencia.SEMANAL
    if normalizado == "quinzenal i":
        return Recorrencia.QUINZENAL_I
    if normalizado == "quinzenal ii":
        return Recorrencia.QUINZENAL_II
    return Recorrencia.DESCONHECIDA


def extrair_horarios(valor: object, tipo: str) -> tuple[Horario, ...]:
    if not possui_valor(valor):
        return ()

    texto = _normalizar_minusculo(valor)
    encontrados: list[Horario] = []
    for dia, inicio, fim, recorrencia in PADRAO_HORARIO.findall(texto):
        encontrados.append(
            Horario(
                dia=DIAS[dia],
                inicio=_hora_para_minutos(inicio),
                fim=_hora_para_minutos(fim),
                recorrencia=_recorrencia(recorrencia),
                tipo=tipo,
            )
        )
    return tuple(encontrados)


def extrair_tpei(valor: object) -> tuple[int, int, int, int, int]:
    """Retorna T, P, E, I e créditos presenciais/extensão.

    Formatos aceitos:
      - T-P-I: créditos = T + P
      - T-P-E-I: créditos = T + P + E
    """
    if not possui_valor(valor):
        raise ValueError("TPEI vazio")

    texto = str(valor).strip()
    try:
        partes = [int(p.strip()) for p in texto.split("-")]
    except ValueError as erro:
        raise ValueError(f"TPEI inválido: {valor}") from erro

    if len(partes) == 3:
        t, p, i = partes
        e = 0
    elif len(partes) == 4:
        t, p, e, i = partes
    else:
        raise ValueError(f"TPEI com formato inesperado: {valor}")

    return t, p, e, i, t + p + e


def recorrencias_conflitam(a: Recorrencia, b: Recorrencia) -> bool:
    if Recorrencia.DESCONHECIDA in {a, b}:
        return True
    if Recorrencia.SEMANAL in {a, b}:
        return True
    return a == b


def horarios_conflitam(a: Horario, b: Horario) -> bool:
    if a.dia != b.dia:
        return False
    sobrepoe = not (a.fim <= b.inicio or b.fim <= a.inicio)
    return sobrepoe and recorrencias_conflitam(a.recorrencia, b.recorrencia)


def ofertas_conflitam(a: Oferta, b: Oferta) -> bool:
    return any(
        horarios_conflitam(h1, h2)
        for h1 in a.horarios
        for h2 in b.horarios
    )


def _docentes_da_linha(linha: pd.Series) -> tuple[str, ...]:
    docentes: list[str] = []
    for coluna in COLUNAS_DOCENTES:
        valor = linha.get(coluna)
        if possui_valor(valor):
            nome = normalizar_texto(valor)
            if nome and "DEFINIR DOCENTE" not in nome and nome not in docentes:
                docentes.append(nome)
    return tuple(docentes)


def _inteiro_opcional(valor: object) -> int | None:
    if not possui_valor(valor):
        return None
    try:
        return int(float(str(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _diagnostico_atualizado(
    anterior: DiagnosticoDisciplina,
    **mudancas,
) -> DiagnosticoDisciplina:
    dados = {
        "codigo": anterior.codigo,
        "nome": anterior.nome,
        "encontrada_na_planilha": anterior.encontrada_na_planilha,
        "encontrada_campus_turno": anterior.encontrada_campus_turno,
        "ofertas_validas": anterior.ofertas_validas,
        "bloqueadas_por_docente": anterior.bloqueadas_por_docente,
        "rejeitadas_por_horario": anterior.rejeitadas_por_horario,
        "rejeitadas_por_restricao": anterior.rejeitadas_por_restricao,
        "motivos": anterior.motivos,
    }
    dados.update(mudancas)
    return DiagnosticoDisciplina(**dados)


def ler_ofertas(
    caminho: str | Path,
    codigos_curriculo: set[str],
    nomes_curriculo: dict[str, str],
    aliases_oferta: dict[str, str],
    campus: str,
    turno: str,
    professores_bloqueados: set[str],
) -> ResultadoLeituraOfertas:
    path = garantir_arquivo(caminho, "Planilha de ofertas")
    df = pd.read_excel(path)

    obrigatorias = {
        "CÓDIGO DE TURMA", "TURMA", "turma", "TEORIA", "PRÁTICA",
        "CAMPUS", "TURNO", "TPEI", *COLUNAS_DOCENTES,
    }
    faltantes = sorted(obrigatorias - set(df.columns))
    if faltantes:
        raise ValueError(
            "A planilha de ofertas não possui as colunas esperadas: "
            + ", ".join(faltantes)
        )

    campus_norm = normalizar_texto(campus)
    turno_norm = normalizar_texto(turno)
    professores_norm = {normalizar_texto(p) for p in professores_bloqueados}

    diagnosticos = {
        codigo: DiagnosticoDisciplina(codigo=codigo, nome=nomes_curriculo.get(codigo, codigo))
        for codigo in codigos_curriculo
    }
    ofertas: list[Oferta] = []
    avisos: list[str] = []

    for indice, linha in df.iterrows():
        codigo_ofertado = limpar_codigo(linha["turma"])
        codigo_curriculo = aliases_oferta.get(codigo_ofertado, codigo_ofertado)
        if codigo_curriculo not in codigos_curriculo:
            continue

        diag = diagnosticos[codigo_curriculo]
        diag = _diagnostico_atualizado(diag, encontrada_na_planilha=True)
        diagnosticos[codigo_curriculo] = diag

        if (
            normalizar_texto(linha["CAMPUS"]) != campus_norm
            or normalizar_texto(linha["TURNO"]) != turno_norm
        ):
            continue

        diag = _diagnostico_atualizado(diag, encontrada_campus_turno=True)
        diagnosticos[codigo_curriculo] = diag

        docentes = _docentes_da_linha(linha)
        if any(docente in professores_norm for docente in docentes):
            diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
                diag,
                bloqueadas_por_docente=diag.bloqueadas_por_docente + 1,
            )
            continue

        teoria = extrair_horarios(linha["TEORIA"], "teoria")
        pratica = extrair_horarios(linha["PRÁTICA"], "pratica")
        horarios = teoria + pratica

        campos_com_horario = possui_valor(linha["TEORIA"]) or possui_valor(linha["PRÁTICA"])
        if campos_com_horario and not horarios:
            avisos.append(
                f"Linha {indice + 2}: horário não reconhecido para "
                f"{linha['TURMA']} ({codigo_ofertado}); oferta ignorada."
            )
            diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
                diag,
                rejeitadas_por_horario=diag.rejeitadas_por_horario + 1,
            )
            continue

        try:
            t, p, e, i, creditos = extrair_tpei(linha["TPEI"])
        except ValueError as erro:
            avisos.append(
                f"Linha {indice + 2}: {erro}; oferta {linha['TURMA']} ignorada."
            )
            diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
                diag,
                rejeitadas_por_horario=diag.rejeitadas_por_horario + 1,
            )
            continue

        ofertas.append(
            Oferta(
                codigo_ofertado=codigo_ofertado,
                codigo_curriculo=codigo_curriculo,
                nome_turma=str(linha["TURMA"]).strip(),
                codigo_turma=limpar_codigo(linha["CÓDIGO DE TURMA"]),
                campus=normalizar_texto(linha["CAMPUS"]),
                turno=normalizar_texto(linha["TURNO"]),
                creditos=creditos,
                t=t,
                p=p,
                e=e,
                i=i,
                horarios=horarios,
                docentes=docentes,
                tpei_original=str(linha["TPEI"]).strip(),
                vagas_totais=_inteiro_opcional(linha.get("VAGAS TOTAIS")),
                vagas_ingressantes=_inteiro_opcional(linha.get("VAGAS INGRESSANTES")),
                vagas_veteranos=_inteiro_opcional(linha.get("VAGAS VETERANOS")),
            )
        )
        diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
            diag,
            ofertas_validas=diag.ofertas_validas + 1,
        )

    # Acrescenta motivos legíveis para o relatório.
    finais: dict[str, DiagnosticoDisciplina] = {}
    for codigo, diag in diagnosticos.items():
        motivos: list[str] = []
        if not diag.encontrada_na_planilha:
            motivos.append("não ofertada na planilha do quadrimestre")
        elif not diag.encontrada_campus_turno:
            motivos.append("sem turma no campus/turno selecionado")
        elif diag.ofertas_validas == 0:
            if diag.bloqueadas_por_docente:
                motivos.append("todas as turmas foram removidas por docente bloqueado")
            if diag.rejeitadas_por_horario:
                motivos.append("horário ou TPEI não pôde ser lido com segurança")
        finais[codigo] = _diagnostico_atualizado(diag, motivos=tuple(motivos))

    return ResultadoLeituraOfertas(tuple(ofertas), tuple(avisos), finais)


def ler_codigos_ofertados(
    caminho: str | Path,
    aliases_oferta: dict[str, str],
) -> set[str]:
    """Leitura leve para estimar frequência histórica de oferta."""
    path = garantir_arquivo(caminho, "Planilha histórica de ofertas")
    df = pd.read_excel(path, usecols=lambda coluna: coluna == "turma")
    if "turma" not in df.columns:
        raise ValueError(f"Planilha histórica sem coluna 'turma': {path}")
    resultado: set[str] = set()
    for valor in df["turma"]:
        codigo = limpar_codigo(valor)
        if codigo:
            resultado.add(aliases_oferta.get(codigo, codigo))
    return resultado
