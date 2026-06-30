import streamlit as st


def render_dp_module() -> None:
    """Tela inicial do modulo de Departamento Pessoal."""
    st.title("Modulo DP")
    st.write("Area para folhas, admissao, rescisao e eventos de eSocial.")

    st.subheader("Backlog sugerido")
    st.markdown("- Cadastro de colaboradores")
    st.markdown("- Processamento de folha")
    st.markdown("- Exportacao de eventos para eSocial")
