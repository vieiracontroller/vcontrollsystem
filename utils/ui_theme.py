from __future__ import annotations

import streamlit as st


def apply_global_theme() -> None:
    """Aplica identidade visual global para todas as telas do sistema."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

        :root {
            --vc-bg: #f3f7f9;
            --vc-surface: #ffffff;
            --vc-ink: #0f2233;
            --vc-muted: #587189;
            --vc-primary: #0d5a84;
            --vc-primary-soft: #d7eefa;
            --vc-secondary: #0f8d7a;
            --vc-accent: #e9a33b;
            --vc-border: #d7e3ec;
            --vc-danger: #ba3f4a;
        }

        html, body, [class*="css"] {
            font-family: 'Manrope', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 0% 0%, #ffffff 0%, var(--vc-bg) 55%),
                linear-gradient(140deg, #edf4f8 0%, #f7fafc 100%);
            color: var(--vc-ink);
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, #0f2233 0%, #16334b 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        [data-testid="stSidebar"] * {
            color: #eaf3fb;
        }

        .vc-sidebar-brand {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 14px;
            padding: 0.85rem 0.95rem;
            margin-bottom: 0.8rem;
        }

        .vc-shell-header {
            background: linear-gradient(120deg, #0d5a84 0%, #0f8d7a 95%);
            border-radius: 16px;
            padding: 1rem 1.15rem;
            color: #ffffff;
            margin-bottom: 0.95rem;
            box-shadow: 0 14px 26px rgba(13, 90, 132, 0.20);
        }

        .vc-shell-header h2 {
            margin: 0;
            font-weight: 800;
            font-size: 1.25rem;
        }

        .vc-shell-header p {
            margin: 0.3rem 0 0;
            opacity: 0.93;
            font-size: 0.93rem;
        }

        .vc-hero {
            background: var(--vc-surface);
            border: 1px solid var(--vc-border);
            border-left: 8px solid var(--vc-primary);
            border-radius: 16px;
            padding: 1rem 1.15rem;
            margin-bottom: 0.9rem;
            box-shadow: 0 10px 24px rgba(15, 34, 51, 0.07);
        }

        .vc-hero h1 {
            color: var(--vc-ink);
            font-size: 1.85rem;
            margin: 0;
            font-weight: 800;
        }

        .vc-hero p {
            margin: 0.4rem 0 0;
            color: var(--vc-muted);
            font-size: 0.98rem;
        }

        [data-testid="metric-container"] {
            background: var(--vc-surface);
            border: 1px solid var(--vc-border);
            border-radius: 14px;
            padding: 0.5rem 0.8rem;
            box-shadow: 0 10px 20px rgba(15, 34, 51, 0.06);
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            background: var(--vc-surface);
            border: 1px solid var(--vc-border);
            border-radius: 14px;
            padding: 0.25rem;
        }

        .stTextInput>div>div>input,
        .stTextArea textarea,
        .stSelectbox>div>div,
        .stNumberInput>div>div>input {
            border-radius: 10px !important;
            border: 1px solid var(--vc-border) !important;
            background: #fbfdff !important;
        }

        .stButton>button,
        .stDownloadButton>button,
        .stFormSubmitButton>button {
            border-radius: 10px !important;
            border: none !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            background: linear-gradient(120deg, #0d5a84 0%, #0f8d7a 100%) !important;
        }

        .vc-panel {
            background: var(--vc-surface);
            border: 1px solid var(--vc-border);
            border-radius: 14px;
            padding: 0.95rem;
            box-shadow: 0 10px 24px rgba(15, 34, 51, 0.06);
        }

        .vc-kpi-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(180px, 1fr));
            gap: 0.75rem;
            margin-bottom: 0.9rem;
        }

        .vc-kpi-item {
            border: 1px solid var(--vc-border);
            border-radius: 12px;
            padding: 0.8rem;
            background: #fafdff;
        }

        .vc-kpi-item .label {
            color: var(--vc-muted);
            font-size: 0.83rem;
            margin-bottom: 0.25rem;
        }

        .vc-kpi-item .value {
            color: var(--vc-ink);
            font-size: 1.25rem;
            font-weight: 800;
        }

        @media (max-width: 900px) {
            .vc-kpi-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_shell_header(section_name: str) -> None:
    """Renderiza faixa de cabecalho padrão no topo do workspace."""
    st.markdown(
        f"""
        <div class="vc-shell-header">
            <h2>V-Controll System</h2>
            <p>Modulo ativo: {section_name}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str) -> None:
    """Renderiza bloco hero para paginas principais."""
    st.markdown(
        f"""
        <div class="vc-hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
