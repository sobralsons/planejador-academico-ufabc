from __future__ import annotations

from pathlib import Path

import streamlit as st

from planejador.cobertura import PublicacaoBloqueadaError, exigir_liberacao_publica


BASE = Path(__file__).resolve().parent

try:
    exigir_liberacao_publica(BASE)
except PublicacaoBloqueadaError as exc:
    relatorio = exc.relatorio
    st.set_page_config(
        page_title="Planejador Acadêmico UFABC — validação pendente",
        page_icon="🎓",
        layout="centered",
    )
    st.title("Planejador Acadêmico UFABC")
    st.error(
        "A versão pública ainda não foi liberada porque a cobertura acadêmica "
        "não passou por todas as validações obrigatórias."
    )
    st.write(
        "O bloqueio é intencional: matrizes pendentes, incompletas ou sem revisão "
        "humana não podem ser apresentadas como suportadas."
    )
    if relatorio.impedimentos:
        st.markdown("**Pendências que impedem a publicação:**")
        for item in relatorio.impedimentos:
            st.write(f"- {item}")
    st.caption(
        "O protótipo interno continua disponível somente para desenvolvimento e "
        "validação. Esta entrada pública falha de forma segura por padrão."
    )
    st.stop()

# Só é alcançado quando o núcleo acadêmico autoriza explicitamente a publicação.
from app_interno import *  # noqa: E402,F401,F403
