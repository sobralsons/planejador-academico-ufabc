import json
import subprocess
import sys

import pytest

from planejador.modelos import RegistroHistorico, ResumoHistorico
from scripts import comparar_bct_sombra


def test_runner_pode_ser_executado_diretamente():
    processo = subprocess.run(
        [sys.executable, "scripts/comparar_bct_sombra.py", "--help"],
        cwd=comparar_bct_sombra.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert processo.returncode == 0, processo.stderr
    assert "--confirmar-pacote-piloto" in processo.stdout


def test_runner_interno_executa_fluxo_real_sem_persistir_historico(
    monkeypatch, tmp_path, capsys
):
    historico = tmp_path / "historico-sintetico.pdf"
    historico.write_bytes(b"%PDF-sintetico")
    registro = RegistroHistorico(
        periodo="2026.1",
        categoria_original="Sintetica",
        codigo="BIS0005-15",
        nome="Disciplina sintetica",
        creditos=2,
        carga_horaria=24,
        carga_extensao=0,
        turma="A",
        conceito="A",
        situacao="APR",
        docentes="Docente sintetico",
    )
    monkeypatch.setattr(
        comparar_bct_sombra,
        "ler_historico_sigaa",
        lambda _: (
            [registro],
            {},
            ResumoHistorico(atividades_complementares_horas=120),
        ),
    )

    codigo = comparar_bct_sombra.main(
        [
            str(historico),
            "--confirmar-pacote-piloto",
            "--confirmar-aplicabilidade",
            "--confirmar-classificacoes",
            "--base",
            str(comparar_bct_sombra.ROOT),
        ]
    )

    assert codigo == 0
    saida = json.loads(capsys.readouterr().out)
    assert saida["modo"] == "sombra_controlada"
    assert saida["autoridade"] == "legado"
    assert saida["publicavel"] is False
    assert saida["proveniencia_regras_suficiente"] is False
    assert (
        saida["divergencias"]["atividades_complementares"]["classificacao"]
        == "concordante"
    )
    assert "Docente sintetico" not in json.dumps(saida)
    assert list(tmp_path.iterdir()) == [historico]


def test_runner_exige_confirmacao_explicita_do_pacote(monkeypatch, tmp_path):
    historico = tmp_path / "historico-sintetico.pdf"
    historico.write_bytes(b"%PDF-sintetico")
    monkeypatch.setattr(
        comparar_bct_sombra,
        "ler_historico_sigaa",
        lambda _: ([], {}, ResumoHistorico()),
    )

    with pytest.raises(SystemExit) as erro:
        comparar_bct_sombra.main([str(historico)])

    assert erro.value.code == 2
