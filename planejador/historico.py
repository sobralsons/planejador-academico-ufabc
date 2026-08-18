from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

from .modelos import RegistroHistorico, ResumoHistorico, SituacaoAcademica
from .utils import garantir_arquivo, limpar_codigo, normalizar_texto

STATUS_CONCLUIDOS = {"APR", "APRN", "DISP", "TRANS", "INCORP", "CUMP"}
STATUS_EM_ANDAMENTO = {"MATR", "REC"}
STATUS_NAO_CONCLUIDOS = {
    "REP", "REPF", "REPMF", "REPN", "REPNF", "TRANC", "CANC"
}


def _inteiro(valor: object) -> int:
    try:
        return int(float(str(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _limpar_campo(valor: object) -> str:
    if valor is None:
        return ""
    return re.sub(r"\s+", " ", str(valor).replace("\n", " ")).strip()


def _extrair_resumo(texto_completo: str) -> ResumoHistorico:
    resumo = ResumoHistorico()

    padroes_texto = {
        "periodo_inicial": r"Ano\s*/\s*Período Letivo Inicial:\s*(\d{4}\.\d)",
        "periodo_atual": r"Período Letivo Atual:\s*(\d{4}\.\d)",
        "curriculo_bct": r"Currículo:\s*(.*?)\s+Modalidade:",
    }
    for campo, padrao in padroes_texto.items():
        achado = re.search(padrao, texto_completo, flags=re.IGNORECASE)
        if achado:
            setattr(resumo, campo, _limpar_campo(achado.group(1)))

    labels_coeficientes = {
        "CR": "Coeficiente de Rendimento (CR)",
        "CA": "Coeficiente de Aproveitamento (CA)",
        "CP": "Coeficiente de Progressão (CP)",
        "IK": "Coeficiente de Afinidade (IK)",
        "CAIK": "Coeficiente de Aproveitamento de Integralização (CAIK)",
    }
    for sigla, label in labels_coeficientes.items():
        achado = re.search(
            re.escape(label) + r"\s+([0-9]+(?:[\.,][0-9]+)?)",
            texto_completo,
            flags=re.IGNORECASE,
        )
        if achado:
            resumo.coeficientes[sigla] = float(achado.group(1).replace(",", "."))

    # A página de integralização do SIGAA usa horas para BCT. Mantemos esses
    # números separados da auditoria da Engenharia de Materiais, que é estimada
    # pela matriz específica do projeto.
    categorias = ["obrigatorias", "optativos", "livres", "complementares", "total"]
    for rotulo in ("Exigido", "Integralizado", "Pendente"):
        linha = re.search(
            rf"^{rotulo}\s+(.+)$",
            texto_completo,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if linha:
            numeros = [int(x) for x in re.findall(r"(\d+)\s*h", linha.group(1))]
            # A tabela contém colunas extensionistas entre Livres e Complementares.
            # Para o resumo do BC&T usamos as três primeiras colunas e as duas finais.
            if len(numeros) >= 5:
                valores = [numeros[0], numeros[1], numeros[2], numeros[-2], numeros[-1]]
                resumo.integralizacao_bct_horas[rotulo.lower()] = dict(zip(categorias, valores))

    achado_atc = re.search(
        r"ATIVIDADES COMPLEMENTARES.*?\d{2}/\d{2}/\d{4}\s+([0-9]+(?:[\.,][0-9]+)?)",
        texto_completo,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if achado_atc:
        resumo.atividades_complementares_horas = float(
            achado_atc.group(1).replace(",", ".")
        )

    return resumo


def ler_historico_sigaa(
    caminho: str | Path,
) -> tuple[list[RegistroHistorico], dict[str, str], ResumoHistorico]:
    path = garantir_arquivo(caminho, "Histórico escolar")
    registros: list[RegistroHistorico] = []
    convalidacoes: dict[str, str] = {}
    textos_paginas: list[str] = []

    with pdfplumber.open(path) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            textos_paginas.append(texto)

            # Ex.: "Cumpriu ESTM008-13 ... através de ESTM008-17 ..."
            for antigo, atual in re.findall(
                r"Cumpriu\s+([A-Z0-9]+-\d{2}).*?atrav[eé]s\s+de\s+([A-Z0-9]+-\d{2})",
                texto,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                convalidacoes[limpar_codigo(antigo)] = limpar_codigo(atual)

            for tabela in pagina.extract_tables() or []:
                if not tabela:
                    continue
                cabecalho = " ".join(_limpar_campo(c) for c in tabela[0])
                if "Ano/Período" not in cabecalho or "Situação" not in cabecalho:
                    continue

                for linha in tabela[1:]:
                    if len(linha) < 11:
                        continue
                    (
                        periodo,
                        categoria,
                        codigo,
                        nome,
                        creditos,
                        carga_horaria,
                        carga_extensao,
                        turma,
                        conceito,
                        situacao,
                        docentes,
                    ) = linha[:11]

                    codigo_limpo = limpar_codigo(codigo)
                    if not codigo_limpo or codigo_limpo == "ENADE":
                        continue

                    registros.append(
                        RegistroHistorico(
                            periodo=_limpar_campo(periodo),
                            categoria_original=_limpar_campo(categoria),
                            codigo=codigo_limpo,
                            nome=_limpar_campo(nome),
                            creditos=_inteiro(creditos),
                            carga_horaria=_inteiro(carga_horaria),
                            carga_extensao=_inteiro(carga_extensao),
                            turma=limpar_codigo(turma),
                            conceito=normalizar_texto(conceito),
                            situacao=normalizar_texto(situacao),
                            docentes=_limpar_campo(docentes),
                        )
                    )

    if not registros:
        raise ValueError(
            "Nenhum componente curricular foi extraído do histórico. "
            "Confira se o PDF é um histórico do SIGAA com texto selecionável."
        )
    resumo = _extrair_resumo("\n".join(textos_paginas))
    return registros, convalidacoes, resumo


def consolidar_historico(
    registros: list[RegistroHistorico],
    equivalencias_academicas: dict[str, str],
    equivalencias_compostas: list[tuple[set[str], str]] | None = None,
    convalidacoes_historico: dict[str, str] | None = None,
    resumo: ResumoHistorico | None = None,
) -> SituacaoAcademica:
    por_codigo: dict[str, list[RegistroHistorico]] = defaultdict(list)
    for registro in registros:
        por_codigo[registro.codigo].append(registro)

    situacao = SituacaoAcademica(
        tentativas=dict(por_codigo),
        convalidacoes_historico=dict(convalidacoes_historico or {}),
        resumo=resumo or ResumoHistorico(),
    )

    for codigo, tentativas in por_codigo.items():
        status = {tentativa.situacao for tentativa in tentativas}
        if status & STATUS_CONCLUIDOS:
            situacao.concluidas.add(codigo)
        elif status & STATUS_EM_ANDAMENTO:
            situacao.em_andamento.add(codigo)
        elif status & STATUS_NAO_CONCLUIDOS:
            situacao.nao_concluidas.add(codigo)

    # Convalidações oficiais do PPC: se o código antigo foi concluído, o novo é cumprido.
    for origem, destino in equivalencias_academicas.items():
        if origem in situacao.concluidas:
            situacao.concluidas.add(destino)
        if origem in situacao.em_andamento:
            situacao.em_andamento.add(destino)

    for origens, destino in equivalencias_compostas or []:
        if origens.issubset(situacao.concluidas):
            situacao.concluidas.add(destino)
        elif origens.issubset(situacao.concluidas | situacao.em_andamento):
            situacao.em_andamento.add(destino)

    # Convalidações impressas no próprio histórico.
    for destino_antigo, componente_realizado in situacao.convalidacoes_historico.items():
        if componente_realizado in situacao.concluidas:
            situacao.concluidas.add(destino_antigo)
        elif componente_realizado in situacao.em_andamento:
            situacao.em_andamento.add(destino_antigo)

    return situacao
