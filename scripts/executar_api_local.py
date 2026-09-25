from __future__ import annotations

import os
from pathlib import Path
import re

import uvicorn


_CHAVE_ENV = re.compile(r"^[A-Z][A-Z0-9_]*$")
_HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1"}


def carregar_env_local(caminho: Path) -> None:
    if not caminho.exists():
        return

    for numero, linha in enumerate(
        caminho.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        texto = linha.strip()
        if not texto or texto.startswith("#"):
            continue
        if "=" not in texto:
            raise RuntimeError(
                f"Linha {numero} inválida em .env.local."
            )

        chave, valor = texto.split("=", 1)
        chave = chave.strip()
        if not _CHAVE_ENV.fullmatch(chave):
            raise RuntimeError(
                f"Nome de variável inválido na linha {numero} de .env.local."
            )

        os.environ.setdefault(chave, valor.strip())


def executar() -> None:
    raiz = Path(__file__).resolve().parents[1]
    carregar_env_local(raiz / ".env.local")

    host = os.getenv("API_HOST", "127.0.0.1").strip()
    if host not in _HOSTS_LOCAIS:
        raise RuntimeError(
            "API local só pode escutar em localhost/127.0.0.1/::1."
        )

    try:
        porta = int(os.getenv("API_PORT", "8000"))
    except ValueError as exc:
        raise RuntimeError("API_PORT deve ser um inteiro válido.") from exc
    if not 1 <= porta <= 65535:
        raise RuntimeError("API_PORT deve estar entre 1 e 65535.")

    uvicorn.run(
        "api.app:app",
        host=host,
        port=porta,
        reload=False,
    )


if __name__ == "__main__":
    executar()
