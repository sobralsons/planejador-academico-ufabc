from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

BASE = Path(__file__).resolve().parent
PROJETO = BASE.parent
SAIDAS = PROJETO / "saidas"
SESSAO = PROJETO / "dados" / "sessao_ufabc_next"
API_BASE = "https://api.v2.ufabcnext.com"

# A análise é local, determinística e auditável. Não usa serviços externos de IA.
POSITIVOS = {
    "bom professor": 2.0, "boa professora": 2.0, "otimo professor": 2.5,
    "otima professora": 2.5, "excelente": 2.5, "recomendo": 2.0,
    "explica bem": 2.2, "explica muito bem": 2.5, "boa didatica": 2.2,
    "didatica boa": 2.2, "didatica excelente": 2.5, "aula boa": 1.4,
    "aulas boas": 1.4, "prova justa": 1.8, "provas justas": 1.8,
    "coerente": 1.2, "organizado": 1.3, "organizada": 1.3,
    "atencioso": 1.5, "atenciosa": 1.5, "ajuda": 1.0,
    "disponivel": 1.0, "clareza": 1.0, "didatico": 1.8, "didatica": 1.2,
    "justo": 1.2, "justa": 1.2, "facil de entender": 1.5,
    "material bom": 1.2, "lista boa": 0.8, "vale a pena": 1.5,
    "gente boa": 1.2, "compreensivo": 1.3, "compreensiva": 1.3,
    "fofa": 1.4, "paciente": 1.4, "aulas didaticas": 2.0,
    "avalia de forma justa": 2.0, "provas faceis": 1.0,
    "provas factiveis": 1.3, "ajudou muito": 1.8,
}

NEGATIVOS = {
    "pessimo professor": -2.8, "pessima professora": -2.8,
    "horrivel": -2.5, "nao recomendo": -2.5, "nao explica": -2.2,
    "explica mal": -2.2, "didatica ruim": -2.2, "sem didatica": -2.3,
    "prova injusta": -2.2, "provas injustas": -2.2, "criterio confuso": -1.8,
    "criterios confusos": -1.8, "desorganizado": -1.7, "desorganizada": -1.7,
    "grosso": -1.7, "grossa": -1.7, "arrogante": -2.0,
    "humilha": -2.5, "nao ajuda": -1.5, "nao responde": -1.4,
    "impossivel": -1.5, "reprova muito": -1.6, "reprovou muita gente": -1.6,
    "cobra coisa que nao ensinou": -2.2, "nao disponibiliza": -1.0,
    "confuso": -1.2, "confusa": -1.2, "baguncado": -1.4, "baguncada": -1.4,
    "sem criterio": -1.8, "mal educado": -2.1, "mal educada": -2.1,
    "nao gostei": -1.5, "evite": -2.0, "foge": -1.8,
    "sem alma": -2.0, "peguei ranco": -1.8, "reprovou 90": -2.4,
    "reprovou quase todo mundo": -2.2, "cola que so tinha argumentos ruins": -2.5,
}

TEMAS = {
    "didatica": ["didatic", "explica", "ensina", "aula", "clareza", "entender"],
    "avaliacao_e_provas": ["prova", "p1", "p2", "rec", "nota", "criterio", "corrige"],
    "organizacao": ["organiza", "material", "cronograma", "moodle", "lista", "slide"],
    "apoio_e_duvidas": ["duvida", "ajuda", "atenc", "disponivel", "responde"],
    "postura_e_respeito": ["grosso", "grossa", "arrog", "respeito", "educad", "humilha"],
    "dificuldade_e_carga": ["dificil", "facil", "puxad", "trabalho", "carga", "exercicio"],
    "presenca": ["presenca", "chamada", "falta", "frequencia"],
}


@dataclass(frozen=True)
class Consulta:
    professor: str
    disciplina_codigo: str = ""
    disciplina_nome: str = ""


@dataclass
class AnaliseComentarios:
    quantidade: int
    positivos: int
    neutros: int
    negativos: int
    sentimento_medio: float
    score_0_100: float
    score_sentimento_geral_0_100: float
    classificacao_pedagogica: str
    temas: dict[str, dict[str, Any]]
    recentes_2_anos: int


def normalizar(texto: Any) -> str:
    if texto is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def codigo_base(codigo: str) -> str:
    codigo = str(codigo or "").strip().upper()
    return re.sub(r"-\d{2}$", "", codigo)


def clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def ler_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ler_consultas(path: Path) -> list[Consulta]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de consultas não encontrado: {path}")
    consultas: list[Consulta] = []
    with path.open("r", encoding="utf-8-sig", newline="") as arq:
        leitor = csv.DictReader(arq)
        for linha in leitor:
            professor = (linha.get("professor") or "").strip()
            if not professor or professor.startswith("#"):
                continue
            consultas.append(Consulta(
                professor=professor,
                disciplina_codigo=(linha.get("disciplina_codigo") or "").strip(),
                disciplina_nome=(linha.get("disciplina_nome") or "").strip(),
            ))
    return consultas


def localizar_busca(page: Page):
    busca = page.get_by_placeholder("Digite o nome do professor ou disciplina", exact=False)
    if busca.count() == 0:
        busca = page.locator("input[placeholder*='professor' i]")
    if busca.count() == 0:
        raise RuntimeError("Campo de pesquisa não encontrado")
    return busca.first


def esperar_login(page: Page, url_reviews: str, timeout_s: int) -> None:
    page.goto(url_reviews, wait_until="domcontentloaded", timeout=60_000)
    print("\nFaça login no Google institucional na janela do Edge.")
    print("Depois do login, deixe a página Reviews aberta. O restante será automático.\n")
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        try:
            if "/app/reviews" in page.url and localizar_busca(page).is_visible():
                return
        except Exception:
            pass
        page.wait_for_timeout(1000)
    raise TimeoutError("Tempo esgotado aguardando login")


class CapturadorAutorizacao:
    """Mantém o cabeçalho somente em memória; nunca o grava em arquivo."""

    def __init__(self) -> None:
        self.authorization: str | None = None

    def observar(self, request: Any) -> None:
        try:
            if "api.v2.ufabcnext.com" not in request.url:
                return
            valor = request.headers.get("authorization")
            if valor:
                self.authorization = valor
        except Exception:
            pass


def procurar_token_em_objeto(obj: Any) -> str | None:
    if isinstance(obj, str):
        s = obj.strip()
        if s.lower().startswith("bearer "):
            return s
        if s.count(".") == 2 and len(s) > 50:
            return f"Bearer {s}"
        try:
            return procurar_token_em_objeto(json.loads(s))
        except Exception:
            return None
    if isinstance(obj, dict):
        for chave in ("authorization", "token", "accessToken", "access_token", "jwt"):
            if chave in obj:
                achado = procurar_token_em_objeto(obj[chave])
                if achado:
                    return achado
        for valor in obj.values():
            achado = procurar_token_em_objeto(valor)
            if achado:
                return achado
    if isinstance(obj, list):
        for valor in obj:
            achado = procurar_token_em_objeto(valor)
            if achado:
                return achado
    return None


def obter_authorization(page: Page, capturador: CapturadorAutorizacao, timeout_s: int = 30) -> str:
    # O carregamento normal da página costuma chamar /entities/enrollments e revelar
    # o header em memória. Se não ocorrer, tenta ler a chave localStorage 'auth'.
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        if capturador.authorization:
            return capturador.authorization
        page.wait_for_timeout(300)
    auth_bruto = page.evaluate("() => window.localStorage.getItem('auth')")
    encontrado = procurar_token_em_objeto(auth_bruto)
    if encontrado:
        return encontrado
    raise RuntimeError("Não foi possível obter a autorização da sessão. Recarregue a página e tente novamente.")


def sanitizar_erro(erro: Exception | str) -> str:
    """Remove credenciais e dados pessoais de mensagens antes de gravá-las."""
    texto = str(erro)
    texto = re.sub(r"Bearer\s+[A-Za-z0-9._~+\-/=]+", "Bearer [REMOVIDO]", texto, flags=re.I)
    texto = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[EMAIL REMOVIDO]", texto, flags=re.I)
    texto = re.sub(r"https://accounts\.google\.[^\s]+", "[URL DE LOGIN REMOVIDA]", texto, flags=re.I)
    texto = re.sub(r"https://acesso\.ufabc\.edu\.br/[^\s]+", "[URL DE LOGIN REMOVIDA]", texto, flags=re.I)
    # Evita arquivos gigantes em caso de stack trace ou resposta inesperada.
    return texto[:1200]


def api_get(page: Page, authorization: str, caminho: str, timeout_ms: int = 30_000) -> Any:
    """Executa a chamada dentro do navegador autenticado.

    O APIRequestContext do Playwright usa a cadeia de certificados do Node e, em
    algumas redes Windows, rejeita o certificado intermediário da API como
    'self-signed certificate in certificate chain'. O navegador Edge já acessa
    a mesma API normalmente; por isso usamos fetch no contexto da página.
    """
    url = f"{API_BASE}{caminho}"
    resultado = page.evaluate(
        """
        async ({url, authorization, timeoutMs}) => {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), timeoutMs);
          try {
            const resposta = await fetch(url, {
              method: 'GET',
              headers: {
                'Authorization': authorization,
                'Accept': 'application/json'
              },
              signal: controller.signal
            });
            const texto = await resposta.text();
            let dados = null;
            try { dados = JSON.parse(texto); } catch (_) {}
            return {
              ok: resposta.ok,
              status: resposta.status,
              statusText: resposta.statusText,
              dados,
              preview: texto.slice(0, 300)
            };
          } catch (erro) {
            return {
              ok: false,
              status: 0,
              statusText: erro && erro.name ? erro.name : 'FetchError',
              dados: null,
              preview: erro && erro.message ? erro.message : String(erro)
            };
          } finally {
            clearTimeout(timer);
          }
        }
        """,
        {"url": url, "authorization": authorization, "timeoutMs": timeout_ms},
    )
    if not resultado.get("ok"):
        status = resultado.get("status")
        detalhe = sanitizar_erro(resultado.get("preview") or resultado.get("statusText") or "erro desconhecido")
        raise RuntimeError(f"API retornou HTTP {status} em {caminho}: {detalhe}")
    if resultado.get("dados") is None:
        raise RuntimeError(f"A API não retornou JSON válido em {caminho}")
    return resultado["dados"]


def escolher_professor(payload: dict[str, Any], nome: str) -> dict[str, Any] | None:
    dados = payload.get("data") or []
    if not dados:
        return None
    alvo = normalizar(nome)

    def pontuacao(item: dict[str, Any]) -> tuple[int, int]:
        principal = normalizar(item.get("name"))
        aliases = [normalizar(a) for a in (item.get("alias") or [])]
        if principal == alvo:
            return (4, len(principal))
        if alvo in aliases:
            return (3, len(principal))
        if alvo in principal or principal in alvo:
            return (2, len(principal))
        tokens_alvo = set(alvo.split())
        tokens_item = set(principal.split())
        return (1 if tokens_alvo and len(tokens_alvo & tokens_item) >= max(2, len(tokens_alvo) - 1) else 0, len(tokens_item))

    escolhido = max(dados, key=pontuacao)
    return escolhido if pontuacao(escolhido)[0] > 0 else None


def localizar_especifica(specific: list[dict[str, Any]], consulta: Consulta) -> dict[str, Any] | None:
    codigo_alvo = codigo_base(consulta.disciplina_codigo)
    nome_alvo = normalizar(consulta.disciplina_nome)
    candidatos: list[tuple[int, dict[str, Any]]] = []
    for item in specific or []:
        materia = item.get("_id") or {}
        codigos = {codigo_base(c) for c in (materia.get("uf_subject_code") or [])}
        nome = normalizar(materia.get("name"))
        score = 0
        if codigo_alvo and codigo_alvo in codigos:
            score += 10
        if nome_alvo and nome == nome_alvo:
            score += 8
        elif nome_alvo and (nome_alvo in nome or nome in nome_alvo):
            score += 5
        if score:
            candidatos.append((score, item))
    return max(candidatos, key=lambda x: x[0])[1] if candidatos else None


def carregar_comentarios(
    page: Page,
    authorization: str,
    teacher_id: str,
    limite_total: int,
    tamanho_pagina: int,
) -> list[dict[str, Any]]:
    comentarios: list[dict[str, Any]] = []
    pagina = 0
    while len(comentarios) < limite_total:
        limite = min(tamanho_pagina, limite_total - len(comentarios))
        payload = api_get(
            page,
            authorization,
            f"/comments/{teacher_id}/?page={pagina}&limit={limite}",
        )
        lote = payload.get("data") or []
        comentarios.extend(lote)
        total = int(payload.get("total") or len(comentarios))
        if not lote or len(comentarios) >= total:
            break
        pagina += 1
        time.sleep(0.15)
    return comentarios[:limite_total]


def comentario_da_disciplina(comentario: dict[str, Any], consulta: Consulta, especifica: dict[str, Any] | None) -> bool:
    if not consulta.disciplina_codigo and not consulta.disciplina_nome:
        return True
    subject = comentario.get("subject") or {}
    enrollment = comentario.get("enrollment") or {}
    id_especifica = ((especifica or {}).get("_id") or {}).get("_id")
    if id_especifica and (subject.get("_id") == id_especifica or enrollment.get("subject") == id_especifica):
        return True
    codigo_alvo = codigo_base(consulta.disciplina_codigo)
    codigos = {codigo_base(c) for c in (subject.get("uf_subject_code") or [])}
    if codigo_alvo and codigo_alvo in codigos:
        return True
    nome_alvo = normalizar(consulta.disciplina_nome)
    nomes = [normalizar(subject.get("name")), normalizar(enrollment.get("disciplina"))]
    return bool(nome_alvo and any(nome_alvo == n or nome_alvo in n or n in nome_alvo for n in nomes if n))


def peso_recencia(comentario: dict[str, Any], ano_atual: int) -> float:
    enrollment = comentario.get("enrollment") or {}
    ano = enrollment.get("year")
    try:
        idade = max(0, ano_atual - int(ano))
    except Exception:
        idade = 2
    if idade <= 1:
        return 1.0
    if idade <= 3:
        return 0.8
    if idade <= 5:
        return 0.65
    return 0.5


def dividir_clausulas(texto: str) -> list[str]:
    """Separa trechos para não atribuir um elogio de didática a uma crítica de prova."""
    t = normalizar(texto)
    if not t:
        return []
    partes = re.split(r"\b(?:mas|porem|contudo|entretanto|so que|apesar disso)\b|[.!?;]+", t)
    return [re.sub(r"\s+", " ", p).strip() for p in partes if p.strip()]


def pontuar_texto(texto: str) -> float:
    """Pontua qualidade docente; dificuldade da matéria não é crítica ao professor por si só."""
    t = normalizar(texto)
    if not t:
        return 0.0
    score = 0.0
    for frase, peso in POSITIVOS.items():
        if normalizar(frase) in t:
            score += peso
    for frase, peso in NEGATIVOS.items():
        if normalizar(frase) in t:
            score += peso

    autorresponsabilidade = any(frase in t for frase in (
        "porque faltei", "por faltar", "faltei muitas aulas", "nao estudei",
        "nao fiz as listas", "culpa minha", "nao me dediquei",
    ))
    if autorresponsabilidade:
        score += 0.8

    if "reprov" in t and any(x in t for x in ("por 0 1", "sem motivo", "injust", "quase todo mundo", "90 da turma")):
        score -= 1.5

    palavras_pos = ["bom", "boa", "otimo", "otima", "excelente", "justa", "justo", "ajudou", "paciente", "fofa"]
    palavras_neg = ["ruim", "pessimo", "pessima", "grosso", "grossa", "confuso", "confusa", "arrogante"]
    if abs(score) < 0.5:
        score += 0.35 * sum(1 for p in palavras_pos if re.search(rf"\b{re.escape(p)}\b", t))
        score -= 0.35 * sum(1 for p in palavras_neg if re.search(rf"\b{re.escape(p)}\b", t))
    return clamp(score, -3.0, 3.0) / 3.0


def classificar_qualidade_pedagogica(score: float, positivos: int, negativos: int, quantidade: int) -> str:
    forte_maioria_positiva = positivos >= 5 and positivos >= 3 * max(1, negativos)
    maioria_positiva = positivos >= 3 and positivos >= 2 * max(1, negativos)
    if score >= 68 or (score >= 60 and forte_maioria_positiva):
        return "favorável"
    if score >= 54 and maioria_positiva:
        return "razoável"
    if score >= 46:
        return "mista / inconclusiva"
    if score >= 36:
        return "desfavorável"
    return "muito desfavorável"


def analisar_comentarios(comentarios: Iterable[dict[str, Any]]) -> AnaliseComentarios:
    ano_atual = datetime.now().year
    soma = 0.0
    soma_pesos = 0.0
    positivos = neutros = negativos = recentes = 0
    temas_brutos: dict[str, dict[str, float]] = {
        t: {"mencoes": 0, "positivas": 0, "negativas": 0, "soma": 0.0, "peso": 0.0}
        for t in TEMAS
    }
    quantidade = 0
    for item in comentarios:
        if item.get("active") is False:
            continue
        texto = str(item.get("comment") or "").strip()
        if not texto:
            continue
        quantidade += 1
        clausulas = dividir_clausulas(texto) or [normalizar(texto)]
        scores = [pontuar_texto(c) for c in clausulas]
        scores_relevantes = [x for x in scores if abs(x) >= 0.05]
        sentimento = sum(scores_relevantes) / len(scores_relevantes) if scores_relevantes else 0.0
        recencia = peso_recencia(item, ano_atual)
        reacoes = item.get("reactionsCount") or {}
        bonus_reacao = 1.0 + 0.04 * min(5, sum(int(reacoes.get(k) or 0) for k in ("like", "recommendation", "star")))
        peso = recencia * bonus_reacao
        soma += sentimento * peso
        soma_pesos += peso
        if recencia >= 0.8:
            recentes += 1
        if sentimento >= 0.18:
            positivos += 1
        elif sentimento <= -0.18:
            negativos += 1
        else:
            neutros += 1

        for clausula, score_clause in zip(clausulas, scores):
            for tema, gatilhos in TEMAS.items():
                if any(g in clausula for g in gatilhos):
                    d = temas_brutos[tema]
                    d["mencoes"] += 1
                    d["soma"] += score_clause * peso
                    d["peso"] += peso
                    if score_clause >= 0.18:
                        d["positivas"] += 1
                    elif score_clause <= -0.18:
                        d["negativas"] += 1

    media = soma / soma_pesos if soma_pesos else 0.0
    confianca_geral = quantidade / (quantidade + 8.0)
    media_ajustada = media * confianca_geral
    score_sentimento = 50 + 50 * media_ajustada

    temas: dict[str, dict[str, Any]] = {}
    for tema, d in temas_brutos.items():
        if not d["mencoes"]:
            continue
        media_tema = d["soma"] / d["peso"] if d["peso"] else 0.0
        media_tema *= d["mencoes"] / (d["mencoes"] + 3.0)
        temas[tema] = {
            "mencoes": int(d["mencoes"]),
            "positivas": int(d["positivas"]),
            "negativas": int(d["negativas"]),
            "score_0_100": round(50 + 50 * media_tema, 1),
        }

    pesos_temas = {
        "didatica": 0.30,
        "avaliacao_e_provas": 0.25,
        "organizacao": 0.15,
        "apoio_e_duvidas": 0.15,
        "postura_e_respeito": 0.15,
    }
    soma_ped = 0.0
    peso_ped = 0.0
    for tema, peso_tema in pesos_temas.items():
        if tema in temas:
            soma_ped += temas[tema]["score_0_100"] * peso_tema
            peso_ped += peso_tema
    score_ped = soma_ped / peso_ped if peso_ped else score_sentimento
    score_ped = 0.85 * score_ped + 0.15 * score_sentimento
    classificacao = classificar_qualidade_pedagogica(score_ped, positivos, negativos, quantidade)

    return AnaliseComentarios(
        quantidade=quantidade,
        positivos=positivos,
        neutros=neutros,
        negativos=negativos,
        sentimento_medio=round(media_ajustada, 4),
        score_0_100=round(score_ped, 1),
        score_sentimento_geral_0_100=round(score_sentimento, 1),
        classificacao_pedagogica=classificacao,
        temas=temas,
        recentes_2_anos=recentes,
    )


def distribuir_conceitos(bloco: dict[str, Any] | None) -> dict[str, int]:
    saida = {c: 0 for c in "ABCDFO"}
    for item in ((bloco or {}).get("distribution") or []):
        c = str(item.get("conceito") or "").upper()
        if c in saida:
            saida[c] += int(item.get("count") or 0)
    return saida


def metrica_bloco(bloco: dict[str, Any] | None) -> dict[str, Any]:
    if not bloco:
        return {
            "disponivel": False,
            "conceitos": 0,
            "cr_professor": None,
            "cr_medio_disciplina": None,
            "diferenca_cr": None,
            "distribuicao": {c: 0 for c in "ABCDFO"},
        }
    cr_prof = bloco.get("cr_professor")
    cr_medio = bloco.get("cr_medio")
    return {
        "disponivel": True,
        "conceitos": int(bloco.get("count") or 0),
        "conceitos_nao_ead": int(bloco.get("amount") or 0),
        "ead_count": int(bloco.get("eadCount") or 0),
        "cr_professor": round(float(cr_prof), 4) if cr_prof is not None else None,
        "cr_medio_disciplina": round(float(cr_medio), 4) if cr_medio is not None else None,
        "diferenca_cr": round(float(cr_prof) - float(cr_medio), 4) if cr_prof is not None and cr_medio is not None else None,
        "distribuicao": distribuir_conceitos(bloco),
    }


def calcular_risco_academico(metrica: dict[str, Any]) -> dict[str, Any]:
    if not metrica.get("disponivel"):
        return {"score_0_100": 50.0, "classificacao": "sem dados", "taxa_f_ou_o": None}
    dist = metrica.get("distribuicao") or {}
    total = max(1, int(metrica.get("conceitos") or 0))
    taxa_fo = 100.0 * (int(dist.get("F") or 0) + int(dist.get("O") or 0)) / total
    delta = float(metrica.get("diferenca_cr") or 0.0)
    risco_delta = clamp(((-delta) - 0.05) / 0.55 * 100, 0, 100)
    risco_fo = clamp((taxa_fo - 8.0) / 24.0 * 100, 0, 100)
    risco = 0.65 * risco_delta + 0.35 * risco_fo
    if risco >= 75:
        classe = "muito alto"
    elif risco >= 55:
        classe = "alto"
    elif risco >= 32:
        classe = "moderado"
    else:
        classe = "baixo"
    return {
        "score_0_100": round(risco, 1),
        "classificacao": classe,
        "taxa_f_ou_o": round(taxa_fo, 1),
        "diferenca_cr": metrica.get("diferenca_cr"),
    }


def recomendar_docente(qualidade: str, risco: dict[str, Any]) -> tuple[str, int]:
    nivel_risco = risco.get("classificacao")
    if qualidade == "favorável":
        if nivel_risco in {"muito alto", "alto"}:
            return "favorável, mas disciplina/turma exigente", 2
        if nivel_risco == "moderado":
            return "favorável", 5
        return "preferir", 8
    if qualidade == "razoável":
        if nivel_risco in {"muito alto", "alto"}:
            return "evitar se houver alternativa", -5
        if nivel_risco == "moderado":
            return "neutro / avaliar", 0
        return "razoável / boa opção", 2
    if qualidade == "mista / inconclusiva":
        if nivel_risco in {"muito alto", "alto"}:
            return "evitar se houver alternativa", -6
        return "neutro / avaliar", 0
    if qualidade == "desfavorável":
        return "evitar se houver alternativa", -8
    if qualidade == "muito desfavorável":
        return "forte alerta", -12
    return "sem dados", 0


def score_docente(metrica: dict[str, Any], comentarios: AnaliseComentarios, geral_score: float | None = None) -> dict[str, Any]:
    if not metrica.get("disponivel"):
        return {
            "score_0_100": 50.0,
            "classificacao": "sem dados",
            "confianca": "sem dados",
            "qualidade_pedagogica": "sem dados",
            "risco_academico": calcular_risco_academico(metrica),
            "efeito_ranking": 0,
        }
    n_conceitos = int(metrica.get("conceitos") or 0)
    score_ped = float(comentarios.score_0_100)
    risco = calcular_risco_academico(metrica)

    confianca_n = n_conceitos / (n_conceitos + 25.0)
    confianca_c = comentarios.quantidade / (comentarios.quantidade + 6.0)
    confianca_total = clamp(0.65 * confianca_n + 0.35 * confianca_c, 0, 1)
    if geral_score is not None:
        score_ped = confianca_total * score_ped + (1 - confianca_total) * float(geral_score)
    qualidade = classificar_qualidade_pedagogica(
        score_ped, comentarios.positivos, comentarios.negativos, comentarios.quantidade
    )
    recomendacao, efeito = recomendar_docente(qualidade, risco)

    if n_conceitos >= 100 or (n_conceitos >= 40 and comentarios.quantidade >= 6):
        confianca = "alta"
    elif n_conceitos >= 25 or comentarios.quantidade >= 4:
        confianca = "média"
    elif n_conceitos > 0 or comentarios.quantidade > 0:
        confianca = "baixa"
    else:
        confianca = "sem dados"

    return {
        "score_0_100": round(score_ped, 1),
        "classificacao": recomendacao,
        "confianca": confianca,
        "qualidade_pedagogica": qualidade,
        "risco_academico": risco,
        "efeito_ranking": efeito,
        "componentes_score": {
            "comentarios_pedagogicos": round(float(comentarios.score_0_100), 1),
            "sentimento_geral": round(float(comentarios.score_sentimento_geral_0_100), 1),
            "confianca_numerica": round(confianca_total, 3),
        },
    }


def compactar_comentario(item: dict[str, Any]) -> dict[str, Any]:
    enrollment = item.get("enrollment") or {}
    subject = item.get("subject") or {}
    return {
        "texto": str(item.get("comment") or ""),
        "disciplina": subject.get("name") or enrollment.get("disciplina"),
        "codigos": subject.get("uf_subject_code") or [],
        "ano": enrollment.get("year"),
        "quadrimestre": enrollment.get("quad"),
        "conceito": enrollment.get("conceito"),
        "campus": enrollment.get("campus"),
        "turno": enrollment.get("turno"),
        "reacoes": item.get("reactionsCount") or {},
        "criado_em": item.get("createdAt"),
    }


def analisar_consulta(
    page: Page,
    authorization: str,
    consulta: Consulta,
    config: dict[str, Any],
    cache_professores: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    chave_cache = normalizar(consulta.professor)
    cache_professores = cache_professores if cache_professores is not None else {}
    dados_cache = cache_professores.get(chave_cache)
    if dados_cache:
        professor = dados_cache["professor"]
        reviews = dados_cache["reviews"]
        todos_comentarios = dados_cache["comentarios"]
    else:
        busca = api_get(page, authorization, f"/entities/teachers/search?q={quote_plus(consulta.professor)}")
        professor = escolher_professor(busca, consulta.professor)
    if professor is None:
        resultado = {
            "consulta": asdict(consulta),
            "encontrado": False,
            "erro": "Professor não localizado",
        }
        return resultado, resultado

    teacher_id = professor["_id"]
    if not dados_cache:
        reviews = api_get(page, authorization, f"/entities/teachers/reviews/{teacher_id}")
        todos_comentarios = carregar_comentarios(
            page,
            authorization,
            teacher_id,
            int(config.get("max_comentarios_por_professor", 250)),
            int(config.get("comentarios_por_pagina", 50)),
        )
        cache_professores[chave_cache] = {
            "professor": professor,
            "reviews": reviews,
            "comentarios": todos_comentarios,
        }
    especifica = localizar_especifica(reviews.get("specific") or [], consulta)
    comentarios_gerais = [c for c in todos_comentarios if c.get("active") is not False]
    comentarios_especificos = [c for c in comentarios_gerais if comentario_da_disciplina(c, consulta, especifica)]

    metrica_geral = metrica_bloco(reviews.get("general"))
    analise_com_geral = analisar_comentarios(comentarios_gerais)
    score_geral = score_docente(metrica_geral, analise_com_geral)

    metrica_esp = metrica_bloco(especifica)
    analise_com_esp = analisar_comentarios(comentarios_especificos)
    score_esp = score_docente(metrica_esp, analise_com_esp, score_geral.get("score_0_100"))

    materia = (especifica or {}).get("_id") or {}
    compartilhavel = {
        "consulta": asdict(consulta),
        "encontrado": True,
        "professor": {
            "nome": reviews.get("teacher", {}).get("name") or professor.get("name"),
            "teacher_id": teacher_id,
            "aliases": professor.get("alias") or [],
        },
        "avaliacao_geral": {
            "metricas": metrica_geral,
            "comentarios": asdict(analise_com_geral),
            "resultado": score_geral,
        },
        "avaliacao_disciplina": {
            "encontrada": bool(especifica),
            "nome": materia.get("name"),
            "codigos": materia.get("uf_subject_code") or [],
            "metricas": metrica_esp,
            "comentarios": asdict(analise_com_esp),
            "resultado": score_esp,
        },
        "regra_ranking_sugerida": {
            "usar": "avaliacao_disciplina" if especifica else "avaliacao_geral",
            "efeito": score_esp.get("classificacao") if especifica else score_geral.get("classificacao"),
            "ajuste_numerico_sugerido": score_esp.get("efeito_ranking") if especifica else score_geral.get("efeito_ranking"),
            "observacao": "Preferência flexível; qualidade pedagógica e risco acadêmico são exibidos separadamente.",
        },
    }
    local = {
        **compartilhavel,
        "comentarios_gerais_com_texto": [compactar_comentario(c) for c in comentarios_gerais],
        "comentarios_disciplina_com_texto": [compactar_comentario(c) for c in comentarios_especificos],
        "reviews_api": reviews,
    }
    return compartilhavel, local


def cor_score(score: float) -> str:
    if score >= 68:
        return "#15803d"
    if score >= 54:
        return "#4d7c0f"
    if score >= 46:
        return "#a16207"
    if score >= 36:
        return "#c2410c"
    return "#b91c1c"


def render_temas(temas: dict[str, dict[str, int]]) -> str:
    if not temas:
        return "<p class='muted'>Sem temas suficientes nos comentários.</p>"
    linhas = []
    for tema, dados in sorted(temas.items(), key=lambda kv: kv[1]["mencoes"], reverse=True):
        nome = tema.replace("_", " ").title()
        linhas.append(
            f"<tr><td>{html.escape(nome)}</td><td>{dados['mencoes']}</td>"
            f"<td>{dados['positivas']}</td><td>{dados['negativas']}</td><td>{dados.get('score_0_100', 50)}</td></tr>"
        )
    return "<table><thead><tr><th>Tema</th><th>Menções</th><th>Positivas</th><th>Negativas</th><th>Índice</th></tr></thead><tbody>" + "".join(linhas) + "</tbody></table>"


def gerar_html(resultados: list[dict[str, Any]], caminho: Path) -> None:
    cards = []
    for r in resultados:
        if not r.get("encontrado"):
            cards.append(f"<section class='card'><h2>{html.escape(r['consulta']['professor'])}</h2><p>Não encontrado.</p></section>")
            continue
        geral = r["avaliacao_geral"]
        esp = r["avaliacao_disciplina"]
        escolhido = esp if esp.get("encontrada") else geral
        resultado = escolhido["resultado"]
        score = resultado["score_0_100"]
        risco = resultado.get("risco_academico") or {}
        disciplina_titulo = esp.get("nome") or r["consulta"].get("disciplina_nome") or "Avaliação geral"
        cards.append(f"""
        <section class='card'>
          <div class='head'><div><h2>{html.escape(r['professor']['nome'])}</h2><p>{html.escape(str(disciplina_titulo).title())}</p></div>
          <div class='score' style='background:{cor_score(score)}'>{score:.1f}</div></div>
          <div class='badges'>
            <span class='pill'><b>Recomendação:</b> {html.escape(resultado['classificacao'])}</span>
            <span class='pill'><b>Qualidade pedagógica:</b> {html.escape(resultado.get('qualidade_pedagogica', 'sem dados'))}</span>
            <span class='pill'><b>Risco acadêmico:</b> {html.escape(str(risco.get('classificacao', 'sem dados')))}</span>
            <span class='pill'><b>Confiança:</b> {html.escape(resultado['confianca'])}</span>
          </div>
          <div class='grid'>
            <article><span>Conceitos na disciplina</span><strong>{esp['metricas'].get('conceitos', 0)}</strong></article>
            <article><span>CR do professor</span><strong>{esp['metricas'].get('cr_professor') if esp.get('encontrada') else geral['metricas'].get('cr_professor')}</strong></article>
            <article><span>Média da disciplina</span><strong>{esp['metricas'].get('cr_medio_disciplina') if esp.get('encontrada') else geral['metricas'].get('cr_medio_disciplina')}</strong></article>
            <article><span>F/O na disciplina</span><strong>{risco.get('taxa_f_ou_o', '—')}%</strong></article>
            <article><span>Comentários analisados</span><strong>{esp['comentarios']['quantidade'] if esp.get('encontrada') else geral['comentarios']['quantidade']}</strong></article>
            <article><span>Impacto sugerido no ranking</span><strong>{resultado.get('efeito_ranking', 0):+d}</strong></article>
          </div>
          <div class='explain'><b>Como ler:</b> a qualidade pedagógica vem principalmente dos comentários sobre didática, justiça das avaliações, organização, apoio e respeito. O risco acadêmico usa resultados históricos e comparação com a média da própria disciplina. Uma professora pode ser bem avaliada e, ao mesmo tempo, ministrar uma turma exigente.</div>
          <h3>Análise pedagógica dos comentários da disciplina</h3>
          <p>Positivos: <b>{esp['comentarios']['positivos']}</b> · Neutros: <b>{esp['comentarios']['neutros']}</b> · Negativos: <b>{esp['comentarios']['negativos']}</b></p>
          {render_temas(esp['comentarios']['temas'])}
          <details><summary>Avaliação geral do professor</summary>
            <p>Qualidade geral: <b>{geral['resultado']['score_0_100']}</b> — {html.escape(geral['resultado'].get('qualidade_pedagogica',''))}; risco {html.escape(str((geral['resultado'].get('risco_academico') or {}).get('classificacao','')))}; {geral['metricas'].get('conceitos', 0)} conceitos e {geral['comentarios']['quantidade']} comentários.</p>
          </details>
          <p class='muted'>Indicadores auxiliares e colaborativos, não oficiais. A classificação não bloqueia turmas automaticamente.</p>
        </section>
        """)
    documento = f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Avaliações docentes — UFABC Next</title><style>
    body{{margin:0;background:#f4f7f8;color:#17212b;font:15px/1.5 Arial,sans-serif}}header{{background:#173f5f;color:white;padding:28px max(24px,calc((100% - 1100px)/2))}}main{{max-width:1100px;margin:28px auto;padding:0 20px}}.card{{background:white;border-radius:16px;padding:24px;margin:18px 0;box-shadow:0 8px 24px #173f5f18}}.head{{display:flex;justify-content:space-between;gap:18px;align-items:center}}h1,h2,h3{{margin:.2em 0}}.score{{width:74px;height:74px;border-radius:50%;display:grid;place-items:center;color:white;font-size:24px;font-weight:700}}.badges{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 18px}}.pill{{display:inline-block;background:#eef4f6;border-radius:999px;padding:7px 12px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}article{{background:#f6f9fa;border:1px solid #e1eaed;border-radius:12px;padding:14px}}article span{{display:block;color:#52616b;font-size:13px}}article strong{{font-size:20px}}.explain{{background:#f0f7ff;border-left:4px solid #2f80ed;padding:12px 14px;margin:16px 0;border-radius:6px}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #e5ecef}}.muted{{color:#667781;font-size:13px}}details{{margin-top:16px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}
    </style></head><body><header><h1>Avaliações docentes — diagnóstico v5</h1><p>Qualidade pedagógica e risco acadêmico avaliados separadamente.</p></header><main>{''.join(cards)}</main></body></html>"""
    caminho.write_text(documento, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta automática e análise local das avaliações do UFABC Next")
    parser.add_argument("--config", type=Path, default=PROJETO / "config" / "ufabc_next.json")
    parser.add_argument("--consultas", type=Path, default=PROJETO / "dados" / "consultas_ufabc_next.csv")
    parser.add_argument("--saida-json", type=Path, default=PROJETO / "dados" / "avaliacoes_docentes.json")
    parser.add_argument("--saida-html", type=Path, default=PROJETO / "saidas" / "relatorio_avaliacoes_docentes.html")
    parser.add_argument("--saida-local", type=Path, default=PROJETO / "saidas" / "avaliacoes_docentes_local_com_comentarios_NAO_COMPARTILHAR.json")
    parser.add_argument("--sessao", type=Path, default=PROJETO / "dados" / "sessao_ufabc_next")
    args = parser.parse_args()

    config = ler_json(args.config)
    consultas = ler_consultas(args.consultas)
    if not consultas:
        print("Nenhuma consulta informada.")
        return 2

    args.saida_json.parent.mkdir(parents=True, exist_ok=True)
    args.saida_html.parent.mkdir(parents=True, exist_ok=True)
    args.saida_local.parent.mkdir(parents=True, exist_ok=True)
    args.sessao.mkdir(parents=True, exist_ok=True)
    compartilhavel: list[dict[str, Any]] = []
    local: list[dict[str, Any]] = []
    capturador = CapturadorAutorizacao()
    cache_professores: dict[str, dict[str, Any]] = {}

    with sync_playwright() as pw:
        kwargs: dict[str, Any] = {
            "user_data_dir": str(args.sessao),
            "headless": False,
            "ignore_https_errors": True,
            "viewport": {"width": 1500, "height": 900},
            "locale": "pt-BR",
        }
        if str(config.get("navegador", "msedge")).lower() in {"edge", "msedge"}:
            kwargs["channel"] = "msedge"
        contexto = pw.chromium.launch_persistent_context(**kwargs)
        try:
            page = contexto.pages[0] if contexto.pages else contexto.new_page()
            page.on("request", capturador.observar)
            esperar_login(page, str(config.get("url_reviews")), int(config.get("timeout_login_segundos", 600)))
            authorization = obter_authorization(page, capturador)
            print("Login detectado. A coleta agora usa diretamente a API; não é preciso clicar nos cards.\n")
            for indice, consulta in enumerate(consultas, 1):
                alvo = consulta.disciplina_nome or consulta.disciplina_codigo or "avaliação geral"
                print(f"[{indice}/{len(consultas)}] {consulta.professor} — {alvo}")
                try:
                    part, completo = analisar_consulta(
                        page, authorization, consulta, config, cache_professores
                    )
                    compartilhavel.append(part)
                    local.append(completo)
                    print("  OK")
                except Exception as erro:
                    item = {"consulta": asdict(consulta), "encontrado": False, "erro": sanitizar_erro(f"{type(erro).__name__}: {erro}")}
                    compartilhavel.append(item)
                    local.append(item)
                    print(f"  ERRO: {sanitizar_erro(erro)}")
                time.sleep(float(config.get("pausa_entre_professores_segundos", 0.8)))
        finally:
            contexto.close()

    agora = datetime.now(timezone.utc).isoformat()
    arquivo_comp = {
        "gerado_em_utc": agora,
        "origem": "UFABC Next — sessão autenticada local",
        "aviso": "Sem cookies, tokens, e-mail, URLs de login ou texto integral dos comentários.",
        "metodologia": {
            "avaliacao_especifica": "Qualidade pedagógica calculada principalmente pelos comentários temáticos; risco acadêmico calculado separadamente pela comparação de resultados com a própria disciplina.",
            "comentarios": "Análise lexical local em português por cláusulas e temas; dificuldade/carga e presença não são confundidas automaticamente com qualidade docente.",
            "uso_recomendado": "Preferência flexível; mostra separadamente qualidade pedagógica e risco acadêmico, nunca bloqueio automático.",
        },
        "resultados": compartilhavel,
    }
    arquivo_local = {
        **arquivo_comp,
        "aviso": "ARQUIVO LOCAL: contém texto de comentários. Não compartilhe sem revisar.",
        "resultados": local,
    }
    caminho_comp = args.saida_json
    caminho_local = args.saida_local
    caminho_html = args.saida_html
    caminho_comp.write_text(json.dumps(arquivo_comp, ensure_ascii=False, indent=2), encoding="utf-8")
    caminho_local.write_text(json.dumps(arquivo_local, ensure_ascii=False, indent=2), encoding="utf-8")
    gerar_html(compartilhavel, caminho_html)

    print("\nConcluído.")
    print(f"Compartilhável: {caminho_comp}")
    print(f"Relatório visual: {caminho_html}")
    print(f"Local com textos: {caminho_local}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
