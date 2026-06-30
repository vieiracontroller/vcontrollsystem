import streamlit as st


def render_contabil_module() -> None:
    """Tela inicial do modulo contabil."""
    st.title("Modulo Contabil")
    st.write("Area para balancetes, conciliacoes e demonstrativos contabeis.")

    st.subheader("Backlog sugerido")
    st.markdown("- Importacao de lancamentos contabeis")
    st.markdown("- Geracao de balancete mensal")
    st.markdown("- Analise de centros de custo")
