from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def normalizar_texto(valor: object) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto.upper().strip()


def normalizar_nome(valor: object) -> str:
    texto = normalizar_texto(valor)
    texto = re.sub(r"[^A-Z0-9 ]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def limpar_codigo(valor: object) -> str:
    texto = normalizar_texto(valor)
    texto = re.sub(r"[^A-Z0-9-]", "", texto)
    return texto


def possui_valor(valor: object) -> bool:
    texto = str(valor).strip() if valor is not None else ""
    return texto not in {"", "0", "NAN", "NONE", "-", "--"}


def minutos_para_hora(minutos: int) -> str:
    hora, minuto = divmod(minutos, 60)
    return f"{hora:02d}:{minuto:02d}"


def garantir_arquivo(caminho: str | Path, descricao: str) -> Path:
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"{descricao} não encontrado: {path}")
    return path
