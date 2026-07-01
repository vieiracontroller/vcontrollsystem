from __future__ import annotations

import streamlit as st

from modules.fiscal.importacao_central import render_importacao_central


def render_importacao_xml() -> None:
    """Compatibilidade: redireciona para o Centro de Importacao Fiscal centralizado."""
    st.info("Importacao de XML centralizada. Utilize o Centro de Importacao Fiscal no modulo fiscal.")
    render_importacao_central()
