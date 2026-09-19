from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PACOTES = (
    "fastapi",
    "pydantic",
    "pytest",
    "pandas",
    "openpyxl",
    "pdfplumber",
    "streamlit",
)
CAMINHOS_QUE_DEVEM_SER_IGNORADOS = (
    ".env.local",
    "documentos-fonte/exemplo.pdf",
    "entradas/exemplo.pdf",
)


def _git_ignora(caminho: str) -> bool:
    resultado = subprocess.run(
        ["git", "check-ignore", "-q", caminho],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    return resultado.returncode == 0


def main() -> int:
    falhas: list[str] = []
    avisos: list[str] = []

    if sys.version_info[:2] != (3, 12):
        falhas.append(
            "Use Python 3.12. Versao atual: "
            f"{sys.version_info.major}.{sys.version_info.minor}."
        )

    if shutil.which("git") is None:
        falhas.append("Git nao foi encontrado no PATH.")
    else:
        git_repo = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if git_repo.returncode != 0:
            falhas.append("A pasta atual nao foi reconhecida como repositorio Git.")
        else:
            for caminho in CAMINHOS_QUE_DEVEM_SER_IGNORADOS:
                if not _git_ignora(caminho):
                    falhas.append(
                        f"Protecao Git ausente para caminho sensivel: {caminho}"
                    )

    ausentes = [
        pacote for pacote in PACOTES
        if importlib.util.find_spec(pacote) is None
    ]
    if ausentes:
        falhas.append(
            "Dependencias locais ausentes: " + ", ".join(sorted(ausentes))
        )

    obrigatorios = (
        ".env.example",
        "requirements-local.txt",
        "AGENTS.md",
        "api/app.py",
        "persistencia/contratos.py",
    )
    for relativo in obrigatorios:
        if not (ROOT / relativo).exists():
            falhas.append(f"Arquivo obrigatorio ausente: {relativo}")

    if not (ROOT / ".env.local").exists():
        avisos.append(
            ".env.local ainda nao existe. Isso e esperado antes de banco/autenticacao; "
            "copie .env.example quando precisar configurar servicos locais."
        )

    print("Planejador Academico UFABC - verificacao local")
    print(f"Raiz: {ROOT}")
    print(f"Python: {sys.version.split()[0]}")

    for aviso in avisos:
        print(f"AVISO: {aviso}")
    for falha in falhas:
        print(f"ERRO: {falha}")

    if falhas:
        print("RESULTADO: ambiente local incompleto.")
        return 1

    print("RESULTADO: ambiente local pronto para desenvolvimento.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
