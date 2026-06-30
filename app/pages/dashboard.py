import streamlit as st


def render_dashboard() -> None:
    """Renderiza a visao principal com indicadores rapidos."""
    st.title("Dashboard")
    st.caption("Visao executiva dos modulos Contabil, Fiscal e DP")

    col1, col2, col3 = st.columns(3)
    col1.metric("Empresas Ativas", "24", "+2")
    col2.metric("Obrigacoes Proximas", "11", "-1")
    col3.metric("Pendencias Criticas", "3", "+1")

    st.subheader("Resumo Operacional")
    st.info(
        "Use o menu lateral para acessar os modulos e executar tarefas por area."
    )
