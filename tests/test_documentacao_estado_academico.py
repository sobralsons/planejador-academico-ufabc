import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
MARCADOR_HISTORICO = (
    "> **DOCUMENTO HISTÓRICO — NÃO REPRESENTA O ESTADO ACADÊMICO ATUAL.**"
)


def test_estado_academico_documentado_reflete_fontes_estruturadas():
    inventario = json.loads(
        (BASE / "dados/inventario_cursos.json").read_text(encoding="utf-8")
    )
    vigencia = json.loads(
        (BASE / "dados/vigencia_ppcs_2026-09-16.json").read_text(encoding="utf-8")
    )
    registro = json.loads(
        (BASE / "dados/registro_curriculos.json").read_text(encoding="utf-8")
    )
    estado = (BASE / "docs/ESTADO_ACADEMICO_ATUAL.md").read_text(encoding="utf-8")

    cursos = inventario["cursos"]
    matrizes = [
        matriz
        for curso in cursos
        for matriz in curso["matrizes"]
    ]

    assert len(cursos) == inventario["total_cursos"] == 35
    assert len(matrizes) == vigencia["resumo"]["ppcs_total"] == 93
    assert vigencia["resumo"]["candidatas"] == 57
    assert vigencia["resumo"]["pendentes"] == 36
    assert len(registro["curriculos"]) == 7

    assert all(matriz["aplicabilidade"] == "a_confirmar" for matriz in matrizes)
    assert all(matriz["modelagem"] == "nao_iniciada" for matriz in matrizes)
    assert all(matriz["testes"] == "nao_iniciados" for matriz in matrizes)
    assert all(matriz["revisao_humana"] == "nao_iniciada" for matriz in matrizes)

    for trecho in (
        "**35 cursos**",
        "**93 PPCs**",
        "**57 matrizes candidatas**",
        "**36 pendentes**",
        "**7 pacotes curriculares legados estruturados**",
        "**não significa vigência definitivamente comprovada nem suporte acadêmico do produto**",
    ):
        assert trecho in estado


def test_readme_aponta_estado_atual_sem_declarar_suporte_dos_sete_pacotes():
    readme = (BASE / "README.md").read_text(encoding="utf-8")

    assert "docs/ESTADO_ACADEMICO_ATUAL.md" in readme
    assert "nenhuma matriz está declarada academicamente suportada para uso público" in readme
    assert "Currículos legados estruturados no protótipo" in readme
    assert "não é uma lista de matrizes validadas ou suportadas publicamente" in readme
    assert "Aplicação local para planejar **a trajetória completa**" not in readme


def test_documentos_antigos_estao_marcados_como_historicos():
    caminhos = (
        "RELATORIO_DE_VALIDACAO.md",
        "VALIDACAO_MULTICURSO.md",
        "VALIDACAO_TRAJETORIAS.md",
        "MELHORIAS_IMPLEMENTADAS.md",
    )

    for caminho in caminhos:
        texto = (BASE / caminho).read_text(encoding="utf-8")
        assert texto.startswith(MARCADOR_HISTORICO)
        assert "docs/ESTADO_ACADEMICO_ATUAL.md" in texto


def test_documento_historico_nao_autoriza_coleta_autenticada_ufabc_next():
    texto = (BASE / "MELHORIAS_IMPLEMENTADAS.md").read_text(encoding="utf-8")

    assert "coleta autenticada automática descrita abaixo pertence ao protótipo histórico" in texto
    assert "não faz parte do fluxo atual autorizado" in texto
    assert "não deve reativar login/coleta automática" in texto
