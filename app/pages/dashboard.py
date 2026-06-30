import streamlit as st
from datetime import datetime

from db import fetch_rows
from utils.ui_theme import render_hero


def _month_label(value: str) -> str:
    """Converte timestamp ISO para label mensal curta (YYYY-MM)."""
    if not value:
        return "Sem data"
    safe = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(safe)
        return f"{dt.year:04d}-{dt.month:02d}"
    except Exception:
        return "Sem data"


def _count_by_month(rows: list[dict[str, str]], date_key: str) -> dict[str, int]:
    """Conta registros por mes para graficos simples de tendencia."""
    grouped: dict[str, int] = {}
    for row in rows:
        month = _month_label(str(row.get(date_key) or ""))
        grouped[month] = grouped.get(month, 0) + 1
    return dict(sorted(grouped.items()))


def _load_dashboard_data() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Carrega datasets essenciais para KPIs do painel."""
    clientes = fetch_rows("clientes", columns="id,created_at")
    produtos = fetch_rows("produtos", columns="id,created_at")
    notas = fetch_rows("fiscal_nfe_imports", columns="id,criado_em,valor_total")
    return clientes, produtos, notas


def render_dashboard() -> None:
    """Renderiza a visao principal com indicadores rapidos."""
    render_hero(
        "Painel Executivo",
        "Visao integrada dos modulos Contabil, Fiscal, SPED e Gestao de Clientes.",
    )

    try:
        clientes, produtos, notas = _load_dashboard_data()
    except Exception as exc:
        st.error(f"Falha ao carregar dados gerenciais: {exc}")
        clientes, produtos, notas = [], [], []

    total_empresas = len(clientes)
    total_produtos = len(produtos)
    total_notas = len(notas)
    faturamento_total = sum(float(item.get("valor_total") or 0.0) for item in notas)

    col1, col2, col3 = st.columns(3)
    col1.metric("Empresas Ativas", str(total_empresas))
    col2.metric("Produtos Cadastrados", str(total_produtos))
    col3.metric("Notas Processadas", str(total_notas))

    st.metric("Faturamento monitorado", f"R$ {faturamento_total:,.2f}")

    left, right = st.columns([1.35, 1])

    with left:
        produtos_mes = _count_by_month(produtos, "created_at")
        notas_mes = _count_by_month(notas, "criado_em")

        st.markdown(
            """
            <div class="vc-panel">
                <h3 style="margin-top:0;">Saude Operacional</h3>
                <div class="vc-kpi-grid">
                    <div class="vc-kpi-item">
                        <div class="label">XMLs processados (mes)</div>
                        <div class="value">Dinamico</div>
                    </div>
                    <div class="vc-kpi-item">
                        <div class="label">Produtos sincronizados</div>
                        <div class="value">Dinamico</div>
                    </div>
                    <div class="vc-kpi-item">
                        <div class="label">Apuracoes concluidas</div>
                        <div class="value">Em evolucao</div>
                    </div>
                </div>
                <p style="margin:0; color:#587189;">
                    Ambiente pronto para operar fluxo completo: XML -> produtos -> apuracao -> SPED.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("#### Produtos por mes")
            if produtos_mes:
                st.bar_chart(produtos_mes)
            else:
                st.info("Sem dados de produtos para o grafico.")

        with g2:
            st.markdown("#### XMLs por mes")
            if notas_mes:
                st.line_chart(notas_mes)
            else:
                st.info("Sem dados de XML para o grafico.")

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
