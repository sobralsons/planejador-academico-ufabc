import re

import pytest

import planejador.historico as historico


_CABECALHO = [
    "Ano/Período",
    "Categoria",
    "Código",
    "Nome",
    "Créditos",
    "Carga Horária",
    "Extensão",
    "Turma",
    "Conceito",
    "Situação",
    "Docentes",
]


class _PaginaFalsa:
    def __init__(self, linha):
        self._linha = linha

    def extract_text(self):
        return ""

    def extract_tables(self):
        return [[_CABECALHO, self._linha]]


class _PdfFalso:
    def __init__(self, linha):
        self.pages = [_PaginaFalsa(linha)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _linha_valida():
    return [
        "2026.1",
        "Obrigatória",
        "BIS0001-15",
        "Componente sintético",
        "4",
        "48",
        "0",
        "A",
        "A",
        "APR",
        "Docente sintético",
    ]


def _ler_linha(tmp_path, monkeypatch, linha):
    caminho = tmp_path / "historico.pdf"
    caminho.write_bytes(b"%PDF-sintetico")
    monkeypatch.setattr(
        historico.pdfplumber,
        "open",
        lambda _: _PdfFalso(linha),
    )
    return historico.ler_historico_sigaa(caminho)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (4, 4),
        ("4", 4),
        ("4,0", 4),
        ("48.0", 48),
        (" 12 ", 12),
        ("0", 0),
    ],
)
def test_inteiro_aceita_apenas_valores_inteiros_conhecidos(valor, esperado):
    assert historico._inteiro(valor) == esperado


@pytest.mark.parametrize("valor", [None, "", "   ", "ilegível", "4,5"])
def test_inteiro_rejeita_ausencia_texto_invalido_e_fracao(valor):
    with pytest.raises(ValueError):
        historico._inteiro(valor)


@pytest.mark.parametrize(
    ("indice", "rotulo"),
    [
        (4, "Créditos"),
        (5, "Carga horária"),
        (6, "Carga de extensão"),
    ],
)
def test_linha_com_quantidade_invalida_falha_com_contexto_auditavel(
    tmp_path,
    monkeypatch,
    indice,
    rotulo,
):
    linha = _linha_valida()
    linha[indice] = "valor-inválido"

    with pytest.raises(ValueError) as erro:
        _ler_linha(tmp_path, monkeypatch, linha)

    mensagem = str(erro.value)
    assert "página 1" in mensagem
    assert "linha 2" in mensagem
    assert f"campo {rotulo}" in mensagem
    assert "Revise o documento antes de planejar." in mensagem
    assert "valor-inválido" not in mensagem


def test_zero_real_permanece_distinguivel_de_falha_de_parsing(tmp_path, monkeypatch):
    linha = _linha_valida()
    linha[4] = "0"
    linha[5] = "0,0"
    linha[6] = 0

    registros, convalidacoes, resumo = _ler_linha(tmp_path, monkeypatch, linha)

    assert convalidacoes == {}
    assert resumo.coeficientes == {}
    assert len(registros) == 1
    registro = registros[0]
    assert registro.creditos == 0
    assert registro.carga_horaria == 0
    assert registro.carga_extensao == 0
