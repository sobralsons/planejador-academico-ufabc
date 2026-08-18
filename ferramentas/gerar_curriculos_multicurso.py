from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
CATALOGO = BASE / "dados_fontes" / "catalogo_disciplinas_graduacao_2024_2025.xlsx"
SAIDA = BASE / "dados" / "curriculos"


def norm(valor: object) -> str:
    texto = str(valor or "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).upper().strip()


def tpei(valor: object) -> tuple[int, int, int, int, int]:
    partes = [int(x) for x in re.findall(r"\d+", str(valor or ""))]
    if len(partes) == 3:
        t, p, i = partes
        e = 0
    elif len(partes) >= 4:
        t, p, e, i = partes[:4]
    else:
        return 0, 0, 0, 0, 0
    return t, p, e, i, t + p


def carregar_catalogo() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    frames = [
        pd.read_excel(CATALOGO, sheet_name="Disciplinas"),
        pd.read_excel(CATALOGO, sheet_name="Componentes_Curriculares"),
    ]
    df = pd.concat(frames, ignore_index=True)
    por_codigo: dict[str, dict] = {}
    por_nome: dict[str, list[dict]] = {}
    for _, r in df.iterrows():
        if pd.isna(r.get("SIGLA")):
            continue
        item = r.to_dict()
        codigo = str(r["SIGLA"]).strip().upper()
        por_codigo[codigo] = item
        por_nome.setdefault(norm(r.get("DISCIPLINA")), []).append(item)
    return por_codigo, por_nome


def carregar_fallback_existente() -> dict[str, dict]:
    caminho = BASE / "dados" / "curriculo_engenharia_materiais_2017.json"
    if not caminho.exists():
        return {}
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    return {
        d["codigo"]: {
            "nome": d["nome"], "t": d.get("t", 0), "p": d.get("p", 0),
            "e": d.get("e", 0), "i": d.get("i", 0), "creditos": d.get("creditos", 0),
            "recomendacao_texto": d.get("recomendacao_texto", ""),
            "forcar": d.get("catalogo_codigo_consulta") != d["codigo"],
        }
        for d in bruto.get("disciplinas", [])
    }


def _parse_linhas_tabela(path: Path, modo: str) -> dict[str, dict]:
    """Extrai nome e T-P-E-I de linhas tabulares dos PPCs já convertidos em texto."""
    if not path.exists():
        return {}
    resultado: dict[str, dict] = {}
    for linha in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.search(r"\b([A-Z]{3,5}\d{3,4}-\d{2})\b", linha)
        if not m:
            continue
        codigo = m.group(1)
        depois = linha[m.end():].strip()
        # Formato do PPC BCC 2023: 4 (4-0-0-4) 48h
        par = re.search(r"^(.*?)\s+(\d+)\s*\((\d+)-(\d+)-(\d+)-(\d+)\)\s+\d+h?\s*$", depois)
        if par:
            nome = par.group(1).strip()
            t, p_, e, i = map(int, par.groups()[2:])
            resultado[codigo] = {"nome": nome, "t": t, "p": p_, "e": e, "i": i, "creditos": t + p_, "forcar": True}
            continue
        numeros = list(re.finditer(r"\b\d+\b", depois))
        necessario = 4 if modo == "antigo" else 5
        if len(numeros) < necessario:
            continue
        ultimos = numeros[-necessario:]
        nome = depois[:ultimos[0].start()].strip(" -–—")
        vals = [int(x.group()) for x in ultimos]
        if not nome:
            continue
        if modo == "antigo":
            t, p_, i, cr = vals
            e = 0
        elif modo == "bct":
            t, p_, e, i, _ext_horas = vals
            cr = t + p_
        else:  # atual: T P E I Créditos (horas, quando presente, já ficou fora dos cinco últimos)
            t, p_, e, i, cr = vals
            # Algumas linhas possuem uma sexta coluna de carga horária; nesse caso os cinco
            # últimos podem estar deslocados. Corrige usando o fato de crédito = T + P.
            if cr != t + p_ and len(numeros) >= 6:
                vals6 = [int(x.group()) for x in numeros[-6:]]
                t, p_, e, i, cr, _horas = vals6
        resultado.setdefault(codigo, {"nome": nome, "t": t, "p": p_, "e": e, "i": i, "creditos": cr, "forcar": True})
    return resultado


def carregar_fallback_fontes() -> dict[str, dict]:
    fontes = BASE / "dados_fontes"
    resultado = carregar_fallback_existente()
    for arquivo, modo in (
        ("bcc_2017.txt", "antigo"),
        ("engenharias_2017.txt", "antigo"),
        ("bcc_2023_opcao_limitada.txt", "atual"),
        ("bcd_2023_opcao_limitada.txt", "atual"),
        ("ei_2023_opcao_limitada.txt", "atual"),
        ("bct_opcao_limitada_2023.txt", "bct"),
    ):
        for codigo, dados in _parse_linhas_tabela(fontes / arquivo, modo).items():
            resultado.setdefault(codigo, dados)

    # Componentes ausentes do catálogo atual, com valores das tabelas oficiais.
    resultado.update({
        "MCBM006-23": {"nome": "Matemática Discreta", "t": 4, "p": 0, "e": 0, "i": 4, "creditos": 4},
        "MCCC014-23": {"nome": "Programação Estruturada", "t": 2, "p": 2, "e": 0, "i": 4, "creditos": 4},
        "MCZA050-15": {"nome": "Técnicas Avançadas de Programação", "t": 2, "p": 2, "e": 0, "i": 4, "creditos": 4},
        "MCBD008-23": {"nome": "Trabalho de Conclusão de Curso em Ciência de Dados", "t": 0, "p": 12, "e": 0, "i": 24, "creditos": 12},
        "MCTA022-13": {"nome": "Redes de Computadores", "t": 3, "p": 1, "e": 0, "i": 4, "creditos": 4},
        "ESTI019-17": {"nome": "Codificação de Sinais Multimídia", "t": 2, "p": 2, "e": 0, "i": 4, "creditos": 4},
        "BCC-TCC-23": {"nome": "Trabalho de Conclusão de Curso em Ciência da Computação", "t": 12, "p": 0, "e": 0, "i": 12, "creditos": 12},
    })
    for dados in resultado.values():
        dados.setdefault("forcar", False)
    for codigo in {"MCBM006-23", "MCCC014-23", "MCZA050-15", "MCBD008-23", "MCTA022-13", "ESTI019-17", "BCC-TCC-23"}:
        resultado[codigo]["forcar"] = True
    return resultado


BCT15 = [
    "BCS0001-15", "BIS0005-15", "BIS0003-15", "BIK0102-15", "BIL0304-15",
    "BIJ0207-15", "BCJ0204-15", "BCN0402-15", "BCN0404-15", "BCM0504-15",
    "BCL0306-15", "BCN0407-15", "BCJ0205-15", "BCM0505-15", "BCL0307-15",
    "BCM0506-15", "BIN0406-15", "BCN0405-15", "BCJ0203-15", "BIR0004-15",
    "BCL0308-15", "BIQ0602-15", "BCK0103-15", "BCK0104-15", "BIR0603-15",
    "BCS0002-15",
]
BCT22 = [c for c in BCT15 if c not in {"BIJ0207-15", "BCK0104-15"}]
BCT22 = ["BCM0505-22" if c == "BCM0505-15" else c for c in BCT22]

Q_BCT15 = {
    "BCS0001-15":1,"BIS0005-15":1,"BIS0003-15":1,"BIK0102-15":1,"BIL0304-15":1,"BIJ0207-15":1,
    "BCJ0204-15":2,"BCN0402-15":2,"BCN0404-15":2,"BCM0504-15":2,"BCL0306-15":2,
    "BCN0407-15":3,"BCJ0205-15":3,"BCM0505-15":3,"BCL0307-15":3,
    "BCM0506-15":4,"BIN0406-15":4,"BCN0405-15":4,"BCJ0203-15":4,"BIR0004-15":4,
    "BCL0308-15":5,"BIQ0602-15":5,"BCK0103-15":5,"BCK0104-15":6,"BIR0603-15":6,
    "BCS0002-15":9,
}
Q_BCT22 = {k.replace("BCM0505-15", "BCM0505-22"): v for k, v in Q_BCT15.items() if k in BCT22 or k == "BCM0505-15"}

BCC17_OBR = [
    "MCTB001-17","MCTA001-17","MCTA002-17","MCTA003-17","MCTA004-17","MCTA037-17",
    "MCTA006-17","MCTA007-17","MCTA008-17","MCTA009-13","MCTA033-15","MCTA014-15",
    "MCTA015-13","NHI2049-13","MCTB019-17","MCTA016-13","MCTA028-15","MCTA017-17",
    "MCTA018-13","MCTA029-17","MCTA030-17","MCTA031-17","MCTA022-17","MCTA023-17",
    "MCTA024-13","MCTA025-13","MCTA026-13","MCTA027-17",
]
Q_BCC17 = {
    **Q_BCT15,
    "NHI2049-13":5,"MCTA028-15":5,
    "MCTA006-17":6,"MCTA001-17":6,"MCTB019-17":6,
    "MCTA024-13":7,"MCTA003-17":7,"MCTA018-13":7,"MCTB001-17":7,"MCTA009-13":7,
    "MCTA004-17":8,"MCTA002-17":8,"MCTA027-17":8,"MCTA037-17":8,"MCTA014-15":8,
    "MCTA022-17":9,"MCTA026-13":9,"MCTA015-13":9,"MCTA033-15":9,
    "MCTA029-17":10,"MCTA025-13":10,"MCTA007-17":10,"MCTA016-13":10,
    "MCTA030-17":11,"MCTA008-17":11,"MCTA017-17":11,
    "MCTA031-17":12,"MCTA023-17":12,
}

BCC23_OBR = [
    "MCTB001-17","MCCC001-23","MCCC002-23","MCCC003-23","MCCC004-23","MCCC005-23",
    "MCTA004-17","MCTA006-17","MCCC006-23","MCCC007-23","MCTA009-13","MCTA033-15",
    "MCCC008-23","MCZA008-17","MCCC009-23","MCBM006-23","MCCC010-23","MCCC011-23",
    "MCCC012-23","MCTA028-15","MCCC015-23","MCTA018-13","MCTA022-17","MCTA023-17",
    "MCTA024-13","MCTA025-13","MCTA026-13",
]
Q_BCC23 = {
    **Q_BCT22,
    "MCBM006-23":4,"MCTA028-15":5,
    "MCTA006-17":6,"MCTB001-17":6,"MCCC001-23":6,
    "MCTA018-13":7,"MCTA024-13":7,"MCCC010-23":7,"MCCC002-23":7,
    "MCTA004-17":8,"MCCC008-23":8,"MCCC003-23":8,
    "MCTA022-17":9,"MCTA033-15":9,"MCCC004-23":9,
    "MCTA009-13":10,"MCCC015-23":10,"MCCC005-23":10,
    "MCCC012-23":11,"MCCC007-23":11,"MCZA008-17":11,
    "MCCC011-23":12,"MCTA026-13":12,"MCCC009-23":12,
    "MCCC006-23":13,"MCTA025-13":14,"MCTA023-17":15,
    "BCC-TCC-23":15,
}

BCD23_OBR = [
    "MCTB001-17","MCCC001-23","MCZB002-13","MCBM014-23","MCZA002-17","MCTC011-15",
    "MCTA009-13","MCTB008-17","MCTB009-17","MCBD002-23","MCBM016-23","MCTC014-13",
    "MCBM022-23","MCBM006-23","MCBD003-23","MCZA015-13","MCCC012-23","MCCC014-23",
    "MCCC013-23","MCBD004-23","MCBD008-23",
]
Q_BCD23 = {
    **Q_BCT22,
    "MCBM006-23":4,"MCTB008-17":5,"MCCC014-23":5,
    "MCTB001-17":6,"MCBD002-23":6,"MCCC001-23":6,
    "MCTC014-13":7,"MCTB009-17":7,"MCBD003-23":7,"MCTA009-13":7,
    "MCBM016-23":8,"MCBM014-23":8,"MCCC012-23":8,
    "MCTC011-15":9,"MCZB002-13":9,"MCZA002-17":9,
    "MCBD004-23":10,"MCZA015-13":10,
    "MCBM022-23":11,"MCCC013-23":11,"MCBD008-23":12,
}

EI17_OBR = [
    "MCTB001-17","MCTB009-17","ESTO013-17","ESTO011-17","ESTO005-17","ESTO006-17",
    "ESTO008-17","ESTO012-17","ESTO016-17","ESTO017-17","ESTO902-17","ESTO903-17",
    "MCTA028-15","ESTI016-17","ESTA002-17","ESTI017-17","ESTA004-17","ESTA001-17",
    "ESTA007-17","ESTI002-17","ESTI003-17","ESTI004-17","ESTA003-17","MCTA022-13",
    "ESTI005-17","ESTI006-17","ESTI007-17","ESTI008-17","ESTI018-17","ESTI010-17",
    "ESTI019-17","ESTI013-17","ESTI015-17","ESTI020-17","ESTI905-17","ESTI902-17",
    "ESTI903-17","ESTI904-17",
]
Q_EI17 = {
    **Q_BCT15,
    "ESTO005-17":4,"MCTA028-15":5,"MCTB009-17":5,"MCTB001-17":6,"ESTO006-17":6,"ESTO017-17":6,
    "ESTO011-17":7,"ESTO012-17":7,"ESTO008-17":7,"ESTO016-17":7,"ESTI016-17":7,
    "ESTO013-17":8,"ESTI003-17":8,"ESTA002-17":8,"ESTI005-17":8,
    "MCTA022-13":9,"ESTA004-17":9,"ESTA001-17":9,"ESTI004-17":9,
    "ESTI006-17":10,"ESTA003-17":10,"ESTA007-17":10,"ESTI002-17":10,
    "ESTI019-17":11,"ESTI007-17":11,"ESTI017-17":11,"ESTI013-17":11,"ESTO902-17":11,
    "ESTI010-17":12,"ESTI008-17":12,"ESTI018-17":12,"ESTO903-17":12,
    "ESTI020-17":13,"ESTI015-17":13,"ESTI902-17":13,
    "ESTI903-17":14,"ESTI905-17":15,"ESTI904-17":15,
}

EI23_OBR = [
    "MCTB001-17","MCTB009-17","ESTO013-17","ESTO016-17","ESTO011-17","ESTO005-17",
    "ESTO006-17","ESTO008-17","ESTO017-17","ESTO012-17","ESMA001-23","ESMA002-23",
    "ESTA002-17","ESTA004-17","ESIF001-23","ESTI007-17","ESTI015-17","ESTI010-17",
    "ESTA001-17","ESTA007-17","ESTI002-17","ESTI017-17","ESTI016-17","ESTI018-17",
    "ESTI004-17","ESTI006-17","MCTA028-15","MCTA022-17","ESTI005-17","ESTA003-17",
    "ESTI013-17","ESTI008-17","ESTI020-17","ESTI003-17","ESTI905-17","ESTI902-17",
    "ESTI903-17","ESTI904-17",
]
Q_EI23 = {
    **Q_BCT22,
    "ESTO005-17":4,"MCTA028-15":5,"MCTB009-17":5,"MCTB001-17":6,"ESTO006-17":6,"ESTO017-17":6,
    "ESTO011-17":7,"ESTO012-17":7,"ESTO008-17":7,"ESTO016-17":7,"ESTI016-17":7,
    "ESTO013-17":8,"ESTI003-17":8,"ESTA002-17":8,"ESTI005-17":8,
    "MCTA022-17":9,"ESTA004-17":9,"ESTA001-17":9,"ESTI004-17":9,
    "ESTI006-17":10,"ESTA003-17":10,"ESTA007-17":10,"ESTI002-17":10,
    "ESMA001-23":11,"ESTI007-17":11,"ESTI017-17":11,"ESTI013-17":11,"ESIF001-23":11,
    "ESMA002-23":12,"ESTI008-17":12,"ESTI018-17":12,"ESTI010-17":12,
    "ESTI020-17":13,"ESTI015-17":13,"ESTI902-17":13,
    "ESTI903-17":14,"ESTI905-17":15,"ESTI904-17":15,
}

# Códigos de opção limitada extraídos dos documentos oficiais e congelados no pacote.
BCC17_OL = []
BCC23_OL = []
BCD23_OL = []
EI17_OL = []
EI23_OL = []
BCT_OL = []


def ler_codigos_txt(path: Path, inicio: str | None = None, fim: str | None = None, ultima_ocorrencia: bool = False) -> list[str]:
    texto = path.read_text(encoding="utf-8", errors="ignore")
    if inicio:
        posicoes = [m.start() for m in re.finditer(re.escape(inicio), texto)]
        if posicoes:
            texto = texto[posicoes[-1] if ultima_ocorrencia else posicoes[0]:]
    if fim and fim in texto:
        texto = texto.split(fim, 1)[0]
    codigos: list[str] = []
    for codigo in re.findall(r"(?m)^\s*(?:\d+\s+)?([A-Z]{3,5}\d{3,4}-\d{2})\b", texto):
        if codigo not in codigos:
            codigos.append(codigo)
    return codigos


def preencher_listas_fontes() -> None:
    fontes = BASE / "dados_fontes"
    BCC17_OL.extend(ler_codigos_txt(
        fontes / "bcc_2017.txt", "17.3 DISCIPLINAS DE OPÇÃO LIMITADA", "18. OFERTA", True
    ))
    BCC23_OL.extend(ler_codigos_txt(fontes / "bcc_2023_opcao_limitada.txt"))
    BCD23_OL.extend(ler_codigos_txt(fontes / "bcd_2023_opcao_limitada.txt"))
    EI17_OL.extend(ler_codigos_txt(
        fontes / "engenharias_2017.txt",
        "Tabela INFO3. Disciplinas de Opção Limitada para a Engenharia de Informação",
        "Os 27 créditos restantes",
    ))
    EI23_OL.extend(ler_codigos_txt(fontes / "ei_2023_opcao_limitada.txt"))
    BCT_OL.extend(ler_codigos_txt(fontes / "bct_opcao_limitada_2023.txt"))


def item_disciplina(
    codigo: str,
    categoria: str,
    q: int | None,
    por_codigo: dict[str, dict],
    por_nome: dict[str, list[dict]],
    fallback: dict | None = None,
) -> dict:
    fallback = fallback or {}
    linha = None if fallback.get("forcar") else por_codigo.get(codigo)
    if linha is None and fallback.get("nome") and not fallback.get("forcar"):
        candidatos = por_nome.get(norm(fallback["nome"]), [])
        if len(candidatos) == 1:
            linha = candidatos[0]
    if linha:
        nome = str(linha.get("DISCIPLINA") or fallback.get("nome") or codigo).strip()
        t, p, e, i, cr = tpei(linha.get("TPEI"))
        rec_texto = str(linha.get("RECOMENDAÇÃO") or "").strip()
    else:
        nome = fallback.get("nome", codigo)
        t, p, e, i, cr = (
            int(fallback.get("t", 0)), int(fallback.get("p", 0)), int(fallback.get("e", 0)),
            int(fallback.get("i", 0)), int(fallback.get("creditos", 0)),
        )
        rec_texto = fallback.get("recomendacao_texto", "")
    observacoes = [] if linha else ["Componente estruturado a partir do PPC; não localizado no catálogo fornecido."]
    if codigo.startswith("BCC-"):
        observacoes = [
            "Código interno do planejador para representar o componente final do PPC; não deve ser pesquisado diretamente na oferta de turmas."
        ]
    return {
        "codigo": codigo,
        "nome": nome,
        "categoria": categoria,
        "creditos": cr,
        "t": t,"p": p,"e": e,"i": i,
        "quadrimestre_recomendado": q,
        "recomendacoes": [],
        "recomendacao_texto": rec_texto,
        "requisito_manual": rec_texto if norm(rec_texto).startswith("REQUISITO") else "",
        "catalogo_codigo_consulta": codigo if linha else None,
        "observacoes": observacoes,
    }


def aplicar_recomendacoes(disciplinas: list[dict]) -> None:
    codigo_por_nome = {norm(d["nome"]): d["codigo"] for d in disciplinas}
    for d in disciplinas:
        texto = d.get("recomendacao_texto", "")
        if not texto or norm(texto) in {"NAO HA", "NAN"} or norm(texto).startswith("REQUISITO"):
            continue
        encontrados: list[str] = []
        for trecho in re.split(r"[;\n]", texto):
            codigo = codigo_por_nome.get(norm(trecho))
            if codigo and codigo != d["codigo"]:
                encontrados.append(codigo)
        d["recomendacoes"] = sorted(set(encontrados))


def criar(
    id_: str,
    curso: str,
    versao: str,
    base_codes: list[str],
    obrigatorias: list[str],
    limitadas: list[str],
    qmap: dict[str, int],
    requisitos: dict,
    fontes: dict,
    extras: dict[str, dict] | None = None,
    equivalencias: dict[str, str] | None = None,
    equivalencias_compostas: list[dict] | None = None,
    duracoes_especiais: dict | None = None,
) -> None:
    por_codigo, por_nome = carregar_catalogo()
    fallback_fontes = carregar_fallback_fontes()
    extras = {**fallback_fontes, **(extras or {})}
    disciplinas: list[dict] = []
    vistos: set[str] = set()
    for codigo in base_codes + obrigatorias:
        if codigo in vistos:
            continue
        vistos.add(codigo)
        disciplinas.append(item_disciplina(codigo, "obrigatoria", qmap.get(codigo), por_codigo, por_nome, extras.get(codigo)))
    for codigo in limitadas:
        if codigo in vistos:
            continue
        vistos.add(codigo)
        disciplinas.append(item_disciplina(codigo, "opcao_limitada", None, por_codigo, por_nome, extras.get(codigo)))
    aplicar_recomendacoes(disciplinas)
    bruto = {
        "metadados": {
            "id": id_, "curso": curso, "versao": versao,
            **requisitos,
            "fontes": fontes,
            "duracoes_especiais": duracoes_especiais or {},
        },
        "disciplinas": disciplinas,
    }
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / f"{id_}.json").write_text(json.dumps(bruto, ensure_ascii=False, indent=2), encoding="utf-8")
    eq = {
        "equivalencias_academicas": equivalencias or {},
        "equivalencias_compostas": equivalencias_compostas or [],
    }
    (SAIDA / f"{id_}_equivalencias.json").write_text(json.dumps(eq, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    preencher_listas_fontes()
    extras = {
        "BCC-TCC-23": {"nome":"Trabalho de Conclusão de Curso em Ciência da Computação","t":12,"p":0,"e":0,"i":12,"creditos":12},
    }
    criar(
        "bct_2015", "Bacharelado em Ciência e Tecnologia — UFABC", "2015",
        [], BCT15, BCT_OL, Q_BCT15,
        {"creditos_totais":190,"creditos_totais_oficiais":190,"creditos_disciplinas_e_integralizadores":190,
         "creditos_obrigatorios":90,"creditos_obrigatorios_regulares":90,"creditos_opcao_limitada":57,"creditos_livres":43,
         "atividades_complementares_horas":120,"estagio_obrigatorio_creditos":0,"trabalho_final_creditos":0,"prazo_ideal_quadrimestres":9},
        {"matriz":"PPC BC&T 2015 consolidado","opcao_limitada":"Ato Decisório CG 29/2023, usado como compatibilidade atual"},
    )
    criar(
        "bcc_2017", "Bacharelado em Ciência da Computação — UFABC", "2017",
        BCT15, BCC17_OBR, BCC17_OL, Q_BCC17,
        {"creditos_totais":256,"creditos_totais_oficiais":256,"creditos_disciplinas_e_integralizadores":256,
         "creditos_obrigatorios":214,"creditos_obrigatorios_regulares":190,"creditos_opcao_limitada":30,"creditos_livres":12,
         "atividades_complementares_horas":120,"estagio_obrigatorio_creditos":0,"trabalho_final_creditos":24,"prazo_ideal_quadrimestres":12},
        {"matriz":"PPC BCC 2017","opcao_limitada":"Tabela 8 do PPC BCC 2017"},
        equivalencias={
            "MCCC001-23":"MCTA001-17","MCCC002-23":"MCTA002-17","MCCC003-23":"MCTA027-17",
            "MCCC004-23":"MCTA003-17","MCCC006-23":"MCTA007-17","MCCC007-23":"MCTA008-17",
            "MCCC008-23":"MCTA014-15","MCCC009-23":"MCTA015-13","MCCC010-23":"NHI2049-13",
            "MCCC012-23":"MCTA037-17","MCCC014-23":"MCTA028-15","MCCC015-23":"MCTA016-13",
        },
        equivalencias_compostas=[{"origens":["MCTA029-17","MCTA030-17","MCTA031-17"],"destino":"BCC-TCC-23"}],
        duracoes_especiais={"trabalho_final_quadrimestres":3},
    )
    criar(
        "bcc_2023", "Bacharelado em Ciência da Computação — UFABC", "2023",
        BCT22, BCC23_OBR + ["BCC-TCC-23"], BCC23_OL, Q_BCC23,
        {"creditos_totais":242,"creditos_totais_oficiais":242,"creditos_disciplinas_e_integralizadores":242,
         "creditos_obrigatorios":202,"creditos_obrigatorios_regulares":190,"creditos_opcao_limitada":24,"creditos_livres":16,
         "atividades_complementares_horas":48,"extensao_horas":328,"estagio_obrigatorio_creditos":0,"trabalho_final_creditos":12,"prazo_ideal_quadrimestres":15},
        {"matriz":"PPC BCC 2023","opcao_limitada":"Ato Decisório CG 44/2023","transicao":"Ato Decisório CG 44/2023 Anexo II"},
        extras=extras,
        equivalencias={
            "MCTA001-17":"MCCC001-23","MCTA002-17":"MCCC002-23","MCTA027-17":"MCCC003-23",
            "MCTA003-17":"MCCC004-23","MCTA007-17":"MCCC006-23","MCTA008-17":"MCCC007-23",
            "MCTA014-15":"MCCC008-23","MCTA015-13":"MCCC009-23","MCTA037-17":"MCCC012-23",
            "MCTA016-13":"MCCC015-23","BCM0505-15":"BCM0505-22",
        },
        equivalencias_compostas=[{"origens":["MCTA029-17","MCTA030-17","MCTA031-17"],"destino":"BCC-TCC-23"}],
        duracoes_especiais={"trabalho_final_quadrimestres":3,"trabalho_final_quadrimestre_inicio":13},
    )
    criar(
        "bcd_2023", "Bacharelado em Ciência de Dados — UFABC", "2023",
        BCT22, BCD23_OBR, BCD23_OL, Q_BCD23,
        {"creditos_totais":216,"creditos_totais_oficiais":216,"creditos_disciplinas_e_integralizadores":216,
         "creditos_obrigatorios":178,"creditos_obrigatorios_regulares":166,"creditos_opcao_limitada":24,"creditos_livres":14,
         "atividades_complementares_horas":48,"extensao_horas":294,"estagio_obrigatorio_creditos":0,"trabalho_final_creditos":12,"prazo_ideal_quadrimestres":12},
        {"matriz":"PPC Bacharelado em Ciência de Dados 2023","opcao_limitada":"Ato Decisório CG 57/2024"},
        equivalencias={"BCM0505-15":"BCM0505-22","MCTA001-17":"MCCC001-23","MCZB008-23":"MCBD008-23"},
        duracoes_especiais={"trabalho_final_quadrimestres":1},
    )
    criar(
        "ei_2017", "Engenharia de Informação — UFABC", "2017",
        BCT15, EI17_OBR, EI17_OL, Q_EI17,
        {"creditos_totais":300,"creditos_totais_oficiais":300,"creditos_disciplinas_e_integralizadores":300,
         "creditos_obrigatorios":245,"creditos_obrigatorios_regulares":225,"creditos_opcao_limitada":28,"creditos_livres":27,
         "atividades_complementares_horas":120,"estagio_obrigatorio_creditos":14,"trabalho_final_creditos":6,"prazo_ideal_quadrimestres":15},
        {"matriz":"PPC Engenharias 2017 — Engenharia de Informação"},
        equivalencias={"MCTA022-17":"MCTA022-13","ESIF001-23":"ESTI019-17","ESMA001-23":"ESTO902-17","ESMA002-23":"ESTO903-17"},
        duracoes_especiais={"trabalho_final_quadrimestres":3,"estagio_quadrimestres":1},
    )
    criar(
        "ei_2023", "Engenharia de Informação — UFABC", "2023",
        BCT22, EI23_OBR, EI23_OL, Q_EI23,
        {"creditos_totais":275,"creditos_totais_oficiais":310,"creditos_disciplinas_e_integralizadores":275,
         "creditos_obrigatorios":239,"creditos_obrigatorios_regulares":219,"creditos_opcao_limitada":20,"creditos_livres":16,
         "atividades_complementares_creditos":4,"atividades_complementares_horas":48,
         "extensao_creditos":31,"extensao_horas":372,"estagio_obrigatorio_creditos":14,"trabalho_final_creditos":6,"prazo_ideal_quadrimestres":15},
        {"matriz":"PPC Engenharias 2023 consolidado/retificado em 2025 — Engenharia de Informação","opcao_limitada":"Ato Decisório CG 68/2025","transicao":"Ato Decisório CG 68/2025 Anexo II"},
        equivalencias={"BCM0505-15":"BCM0505-22","MCTA022-13":"MCTA022-17","ESTI019-17":"ESIF001-23","ESTO902-17":"ESMA001-23","ESTO903-17":"ESMA002-23"},
        duracoes_especiais={"trabalho_final_quadrimestres":3,"estagio_quadrimestres":1},
    )

    # Materiais existente entra no registro junto aos novos pacotes.
    registro = {
        "curriculos": {
            "materiais_2017": {
                "rotulo":"Engenharia de Materiais 2017", "arquivo":"dados/curriculo_engenharia_materiais_2017.json",
                "equivalencias":"dados/equivalencias_engenharia_materiais_2013_2017.json", "grupo":"Engenharias", "estagio_codigo":"ESTM905-17", "curso_base_id":"bct_2015"
            },
            "bct_2015": {"rotulo":"BC&T 2015", "arquivo":"dados/curriculos/bct_2015.json", "equivalencias":"dados/curriculos/bct_2015_equivalencias.json", "grupo":"Curso de ingresso"},
            "bcc_2017": {"rotulo":"Ciência da Computação 2017", "arquivo":"dados/curriculos/bcc_2017.json", "equivalencias":"dados/curriculos/bcc_2017_equivalencias.json", "grupo":"Computação", "curso_base_id":"bct_2015"},
            "bcc_2023": {"rotulo":"Ciência da Computação 2023", "arquivo":"dados/curriculos/bcc_2023.json", "equivalencias":"dados/curriculos/bcc_2023_equivalencias.json", "grupo":"Computação", "curso_base_id":"bct_2015"},
            "bcd_2023": {"rotulo":"Ciência de Dados 2023", "arquivo":"dados/curriculos/bcd_2023.json", "equivalencias":"dados/curriculos/bcd_2023_equivalencias.json", "grupo":"Computação e Dados", "curso_base_id":"bct_2015"},
            "ei_2017": {"rotulo":"Engenharia de Informação 2017", "arquivo":"dados/curriculos/ei_2017.json", "equivalencias":"dados/curriculos/ei_2017_equivalencias.json", "grupo":"Engenharias", "estagio_codigo":"ESTI905-17", "curso_base_id":"bct_2015"},
            "ei_2023": {"rotulo":"Engenharia de Informação 2023", "arquivo":"dados/curriculos/ei_2023.json", "equivalencias":"dados/curriculos/ei_2023_equivalencias.json", "grupo":"Engenharias", "estagio_codigo":"ESTI905-17", "curso_base_id":"bct_2015"},
        }
    }
    (BASE / "dados" / "registro_curriculos.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Currículos multicurso gerados em", SAIDA)


if __name__ == "__main__":
    main()
