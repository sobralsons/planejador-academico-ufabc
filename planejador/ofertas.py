from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pdfplumber

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


def _horario_completo(valor: object) -> bool:
    """Cada campo preenchido deve ser interpretado integralmente."""
    texto = _normalizar_minusculo(valor)
    if not possui_valor(texto.upper()):
        return True
    matches = list(PADRAO_HORARIO.finditer(texto))
    if not matches:
        return False
    restante = PADRAO_HORARIO.sub(" ", texto)
    restante = re.sub(r"\be\b", " ", restante)
    if restante.strip(" \t\r\n;,./()-"):
        return False
    for match in matches:
        inicio, fim = match.group(2), match.group(3)
        for hora in (inicio, fim):
            h, m = map(int, hora.split(":"))
            if not (0 <= h <= 24 and 0 <= m < 60 and (h < 24 or m == 0)):
                return False
        if _hora_para_minutos(inicio) >= _hora_para_minutos(fim):
            return False
    return True


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
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto.upper() in {"NAN", "NONE", "-", "--"}:
        return None
    try:
        return int(float(texto.replace(",", ".")))
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


def _ler_ofertas_excel(
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
        codigo_curriculo = (
            codigo_ofertado
            if codigo_ofertado in codigos_curriculo
            else aliases_oferta.get(codigo_ofertado, codigo_ofertado)
        )
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

        if not (_horario_completo(linha.get("TEORIA")) and _horario_completo(linha.get("PRÁTICA"))):
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



def ler_ofertas_matricula_inicial_completa(
    caminho: str | Path,
    aliases_oferta: dict[str, str],
    campus: str,
    turno: str,
) -> ResultadoLeituraOfertas:
    """Lê todas as turmas do Excel inicial para reconstruir a matrícula real.

    Diferentemente de :func:`ler_ofertas`, esta leitura **não filtra pela matriz
    curricular principal**. Isso é necessário no ajuste, porque o estudante pode
    já estar matriculado em componentes de outra engenharia, de outra matriz,
    livres ou compartilhados que não pertencem ao currículo atualmente usado
    para ranquear novas sugestões.

    Campus e turno continuam sendo respeitados para manter a lista manejável.
    """
    path = garantir_arquivo(caminho, "Planilha de ofertas da matrícula inicial")
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
    ofertas: list[Oferta] = []
    avisos: list[str] = []

    for indice, linha in df.iterrows():
        if (
            normalizar_texto(linha.get("CAMPUS")) != campus_norm
            or normalizar_texto(linha.get("TURNO")) != turno_norm
        ):
            continue

        codigo_ofertado = limpar_codigo(linha.get("turma"))
        if not codigo_ofertado:
            codigo_turma_tmp = limpar_codigo(linha.get("CÓDIGO DE TURMA"))
            achado = re.search(r"([A-Z]{3,5}\d{3,4}-\d{2})", codigo_turma_tmp)
            codigo_ofertado = achado.group(1) if achado else ""
        if not codigo_ofertado:
            continue

        # Mantém aliases conhecidos (ex.: código antigo -> equivalente atual),
        # mas não exige que o destino exista na matriz principal.
        codigo_curriculo = aliases_oferta.get(codigo_ofertado, codigo_ofertado)

        teoria = extrair_horarios(linha.get("TEORIA"), "teoria")
        pratica = extrair_horarios(linha.get("PRÁTICA"), "pratica")
        horarios = teoria + pratica
        if not (_horario_completo(linha.get("TEORIA")) and _horario_completo(linha.get("PRÁTICA"))):
            avisos.append(
                f"Linha {indice + 2}: horário não reconhecido para "
                f"{linha.get('TURMA', codigo_ofertado)}; turma omitida da matrícula atual."
            )
            continue

        try:
            t, p, e, i, creditos = extrair_tpei(linha.get("TPEI"))
        except ValueError as erro:
            avisos.append(
                f"Linha {indice + 2}: {erro}; turma {linha.get('TURMA', codigo_ofertado)} omitida."
            )
            continue

        ofertas.append(
            Oferta(
                codigo_ofertado=codigo_ofertado,
                codigo_curriculo=codigo_curriculo,
                nome_turma=str(linha.get("TURMA", "")).strip(),
                codigo_turma=limpar_codigo(linha.get("CÓDIGO DE TURMA")),
                campus=normalizar_texto(linha.get("CAMPUS")),
                turno=normalizar_texto(linha.get("TURNO")),
                creditos=creditos,
                t=t, p=p, e=e, i=i,
                horarios=horarios,
                docentes=_docentes_da_linha(linha),
                tpei_original=str(linha.get("TPEI", "")).strip(),
                vagas_totais=_inteiro_opcional(linha.get("VAGAS TOTAIS")),
                vagas_ingressantes=_inteiro_opcional(linha.get("VAGAS INGRESSANTES")),
                vagas_veteranos=_inteiro_opcional(linha.get("VAGAS VETERANOS")),
                curso_oferta=normalizar_texto(linha.get("CURSO")),
                origem_oferta="matricula_inicial",
            )
        )

    # Há planilhas em que a mesma turma aparece repetida por vínculos de curso.
    # Para a matrícula real, o código da turma identifica univocamente a escolha.
    unicas: dict[str, Oferta] = {}
    for oferta in ofertas:
        unicas.setdefault(oferta.codigo_turma, oferta)
    return ResultadoLeituraOfertas(tuple(unicas.values()), tuple(avisos), {})

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


CODIGO_DISCIPLINA_EM_TURMA = re.compile(r"([A-Z]{3,5}\d{3,4}-\d{2})")


def extrair_codigo_disciplina_codigo_turma(valor: object) -> str:
    """Extrai o código da disciplina de códigos como ``NA1MCTA004-17SA``."""
    texto = limpar_codigo(valor)
    achado = CODIGO_DISCIPLINA_EM_TURMA.search(texto)
    return achado.group(1) if achado else ""


def _cabecalho_pdf(valor: object) -> str:
    cabecalho = normalizar_texto(str(valor or "").replace("\n", " "))
    # O PDF oficial pode quebrar palavras entre linhas/células na extração.
    aliases = {
        "VAGAS REMANESCENT ES": "VAGAS REMANESCENTES",
        "VAGAS REMANESCENT ES ": "VAGAS REMANESCENTES",
    }
    return aliases.get(cabecalho, cabecalho)


@lru_cache(maxsize=4)
def _extrair_linhas_pdf_cache(caminho_str: str, mtime_ns: int):
    """Extrai o PDF uma única vez por arquivo/versão durante a sessão."""
    caminho = Path(caminho_str)
    linhas = []
    with pdfplumber.open(caminho) as pdf:
        for pagina, page in enumerate(pdf.pages, start=1):
            tabela = page.extract_table()
            if not tabela or len(tabela) < 2:
                continue
            cabecalho = [_cabecalho_pdf(c) for c in tabela[0]]
            for indice, valores in enumerate(tabela[1:], start=2):
                if not valores or not any(possui_valor(v) for v in valores):
                    continue
                linha = {
                    cabecalho[i]: (valores[i] if i < len(valores) else "")
                    for i in range(len(cabecalho))
                }
                linhas.append((pagina, indice, linha))
    return tuple(linhas)


def _linhas_tabelas_pdf(caminho: Path):
    """Produz dicionários linha a linha a partir das tabelas do PDF de ajuste."""
    path = Path(caminho).resolve()
    mtime_ns = path.stat().st_mtime_ns
    yield from _extrair_linhas_pdf_cache(str(path), mtime_ns)


def ler_ofertas_ajuste_pdf(
    caminho: str | Path,
    codigos_curriculo: set[str],
    nomes_curriculo: dict[str, str],
    aliases_oferta: dict[str, str],
    campus: str,
    turno: str,
    professores_bloqueados: set[str],
) -> ResultadoLeituraOfertas:
    """Lê o PDF oficial de ajuste de matrículas da UFABC.

    Diferentemente da oferta inicial, o campo relevante é ``VAGAS
    REMANESCENTES``. Turmas sem vagas permanecem no resultado para que possam
    representar disciplinas nas quais o estudante já está matriculado; o
    planejador decide posteriormente quais podem ser usadas como novas adições.
    """
    path = garantir_arquivo(caminho, "PDF de ajuste de matrículas")
    campus_norm = normalizar_texto(campus)
    turno_norm = normalizar_texto(turno)
    professores_norm = {normalizar_texto(p) for p in professores_bloqueados}

    diagnosticos = {
        codigo: DiagnosticoDisciplina(codigo=codigo, nome=nomes_curriculo.get(codigo, codigo))
        for codigo in codigos_curriculo
    }
    ofertas: list[Oferta] = []
    avisos: list[str] = []

    for pagina, indice, linha in _linhas_tabelas_pdf(path):
        codigo_turma = limpar_codigo(linha.get("CODIGO DE TURMA"))
        codigo_ofertado = extrair_codigo_disciplina_codigo_turma(codigo_turma)
        if not codigo_ofertado:
            continue
        codigo_curriculo = (
            codigo_ofertado
            if codigo_ofertado in codigos_curriculo
            else aliases_oferta.get(codigo_ofertado, codigo_ofertado)
        )
        if codigo_curriculo not in codigos_curriculo:
            continue

        diag = diagnosticos[codigo_curriculo]
        diag = _diagnostico_atualizado(diag, encontrada_na_planilha=True)
        diagnosticos[codigo_curriculo] = diag

        if (
            normalizar_texto(linha.get("CAMPUS")) != campus_norm
            or normalizar_texto(linha.get("TURNO")) != turno_norm
        ):
            continue

        diag = _diagnostico_atualizado(diag, encontrada_campus_turno=True)
        diagnosticos[codigo_curriculo] = diag

        docentes: list[str] = []
        for nome_coluna, valor in linha.items():
            if not nome_coluna.startswith("DOCENTE") or not possui_valor(valor):
                continue
            nome = normalizar_texto(valor)
            if nome and "DEFINIR DOCENTE" not in nome and nome not in docentes:
                docentes.append(nome)
        docentes_tupla = tuple(docentes)
        if any(docente in professores_norm for docente in docentes_tupla):
            diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
                diag, bloqueadas_por_docente=diag.bloqueadas_por_docente + 1,
            )
            continue

        teoria = extrair_horarios(linha.get("TEORIA"), "teoria")
        pratica = extrair_horarios(linha.get("PRATICA"), "pratica")
        horarios = teoria + pratica
        if not (_horario_completo(linha.get("TEORIA")) and _horario_completo(linha.get("PRATICA"))):
            avisos.append(
                f"Página {pagina}, linha {indice}: horário não reconhecido para "
                f"{linha.get('TURMA', codigo_turma)}; oferta ignorada."
            )
            diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
                diag, rejeitadas_por_horario=diag.rejeitadas_por_horario + 1,
            )
            continue

        tpei = linha.get("T-P-E-I") or linha.get("TPEI")
        try:
            t, p, e, i, creditos = extrair_tpei(tpei)
        except ValueError as erro:
            avisos.append(
                f"Página {pagina}, linha {indice}: {erro}; oferta {linha.get('TURMA', codigo_turma)} ignorada."
            )
            diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
                diag, rejeitadas_por_horario=diag.rejeitadas_por_horario + 1,
            )
            continue

        remanescentes = _inteiro_opcional(linha.get("VAGAS REMANESCENTES"))
        alta_demanda = normalizar_texto(linha.get("TURMAS ALTA DEMANDA")) == "SIM"
        ofertas.append(
            Oferta(
                codigo_ofertado=codigo_ofertado,
                codigo_curriculo=codigo_curriculo,
                nome_turma=normalizar_texto(linha.get("TURMA")),
                codigo_turma=codigo_turma,
                campus=normalizar_texto(linha.get("CAMPUS")),
                turno=normalizar_texto(linha.get("TURNO")),
                creditos=creditos,
                t=t, p=p, e=e, i=i,
                horarios=horarios,
                docentes=docentes_tupla,
                tpei_original=str(tpei or "").strip(),
                vagas_totais=_inteiro_opcional(linha.get("VAGAS TOTAIS")),
                vagas_remanescentes=remanescentes,
                alta_demanda=alta_demanda,
                curso_oferta=normalizar_texto(linha.get("CURSO")),
                origem_oferta="ajuste",
            )
        )
        diagnosticos[codigo_curriculo] = _diagnostico_atualizado(
            diag, ofertas_validas=diag.ofertas_validas + 1,
        )

    finais: dict[str, DiagnosticoDisciplina] = {}
    for codigo, diag in diagnosticos.items():
        motivos: list[str] = []
        if not diag.encontrada_na_planilha:
            motivos.append("não consta no PDF oficial de ajuste")
        elif not diag.encontrada_campus_turno:
            motivos.append("sem turma no campus/turno selecionado no ajuste")
        elif diag.ofertas_validas == 0:
            if diag.bloqueadas_por_docente:
                motivos.append("todas as turmas foram removidas por docente bloqueado")
            if diag.rejeitadas_por_horario:
                motivos.append("horário ou TPEI não pôde ser lido com segurança")
        finais[codigo] = _diagnostico_atualizado(diag, motivos=tuple(motivos))

    return ResultadoLeituraOfertas(tuple(ofertas), tuple(avisos), finais)


def ler_ofertas(
    caminho: str | Path,
    codigos_curriculo: set[str],
    nomes_curriculo: dict[str, str],
    aliases_oferta: dict[str, str],
    campus: str,
    turno: str,
    professores_bloqueados: set[str],
) -> ResultadoLeituraOfertas:
    """Lê tanto a planilha de oferta inicial quanto o PDF oficial de ajuste."""
    path = Path(caminho)
    if path.suffix.lower() == ".pdf":
        return ler_ofertas_ajuste_pdf(
            path, codigos_curriculo, nomes_curriculo, aliases_oferta,
            campus, turno, professores_bloqueados,
        )
    return _ler_ofertas_excel(
        path, codigos_curriculo, nomes_curriculo, aliases_oferta,
        campus, turno, professores_bloqueados,
    )


def extrair_docentes_arquivo(caminho: str | Path) -> list[str]:
    """Extrai nomes docentes de Excel de oferta ou PDF de ajuste."""
    path = Path(caminho)
    if not path.exists():
        return []
    nomes: set[str] = set()
    if path.suffix.lower() == ".pdf":
        for _, _, linha in _linhas_tabelas_pdf(path):
            for coluna, valor in linha.items():
                if coluna.startswith("DOCENTE") and possui_valor(valor):
                    nome = normalizar_texto(valor)
                    if nome and "DEFINIR DOCENTE" not in nome:
                        nomes.add(nome)
        return sorted(nomes)
    try:
        df = pd.read_excel(path)
    except Exception:
        return []
    colunas = [c for c in df.columns if "DOCENTE" in normalizar_texto(c)]
    for coluna in colunas:
        for valor in df[coluna].dropna():
            if possui_valor(valor):
                nome = normalizar_texto(valor)
                if nome and "DEFINIR DOCENTE" not in nome:
                    nomes.add(nome)
    return sorted(nomes)
