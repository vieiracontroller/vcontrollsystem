import streamlit as st

from utils.ui_theme import render_hero


def render_dashboard() -> None:
    """Renderiza a visao principal com indicadores rapidos."""
    render_hero(
        "Painel Executivo",
        "Visao integrada dos modulos Contabil, Fiscal, SPED e Gestao de Clientes.",
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Empresas Ativas", "24", "+2")
    col2.metric("Obrigacoes Proximas", "11", "-1")
    col3.metric("Pendencias Criticas", "3", "+1")

    left, right = st.columns([1.35, 1])

    with left:
        st.markdown(
            """
            <div class="vc-panel">
                <h3 style="margin-top:0;">Saude Operacional</h3>
                <div class="vc-kpi-grid">
                    <div class="vc-kpi-item">
                        <div class="label">XMLs processados (mes)</div>
                        <div class="value">1.248</div>
                    </div>
                    <div class="vc-kpi-item">
                        <div class="label">Produtos sincronizados</div>
                        <div class="value">3.962</div>
                    </div>
                    <div class="vc-kpi-item">
                        <div class="label">Apuracoes concluidas</div>
                        <div class="value">87</div>
                    </div>
                </div>
                <p style="margin:0; color:#587189;">
                    Ambiente pronto para operar fluxo completo: XML -> produtos -> apuracao -> SPED.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <div class="vc-panel">
                <h3 style="margin-top:0;">Checklist Diario</h3>
                <p style="margin-bottom:0.35rem;"><strong style="color:#0f8d7a;">Concluido</strong> • Sincronizacao de produtos</p>
                <p style="margin-bottom:0.35rem;"><strong style="color:#e9a33b;">Em andamento</strong> • Conferencia de beneficios por NCM</p>
                <p style="margin-bottom:0.35rem;"><strong style="color:#ba3f4a;">Pendente</strong> • Revisao de notas com divergencia de CFOP</p>
                <hr style="border:none; border-top:1px solid #d7e3ec; margin:0.7rem 0;"/>
                <p style="margin:0; color:#587189; font-size:0.92rem;">
                    Dica: acesse o modulo SPED Fiscal para gerar o TXT do periodo apos validacoes.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.info(
        "Use o menu lateral para acessar os modulos e executar tarefas por area com trilha fiscal completa."
    )
