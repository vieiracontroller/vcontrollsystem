from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from db import fetch_rows
from fiscal.calculos_simples import calcular_das
from modules.fiscal_xml import render_importacao_xml


ANEXOS_DISPONIVEIS = ["I", "II", "III", "IV", "V"]


def _load_empresas() -> list[dict[str, Any]]:
    """Carrega empresas da base de clientes para selecao na apuracao."""
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,regime_tributario",
        order_by="razao_social",
        desc=False,
    )


def _render_apuracao_mensal() -> None:
    """Renderiza tela de apuracao mensal do Simples Nacional."""
    st.subheader("Apuracao Mensal - Simples Nacional")

    try:
        empresas = _load_empresas()
    except Exception as exc:
        st.error(f"Falha ao carregar empresas no Supabase: {exc}")
        return

    if not empresas:
        st.info("Nenhuma empresa cadastrada. Cadastre ao menos um cliente antes da apuracao.")
        return

    empresa_options = {
        f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in empresas
    }
    selected_label = st.selectbox("Empresa", list(empresa_options.keys()), index=0)
    empresa = empresa_options[selected_label]

    col1, col2 = st.columns(2)
    with col1:
        mes_referencia = st.selectbox(
            "Mes de referencia",
            list(range(1, 13)),
            index=max(0, date.today().month - 1),
            format_func=lambda m: f"{m:02d}",
        )
    with col2:
        ano_referencia = st.number_input(
            "Ano de referencia",
            min_value=2020,
            max_value=2100,
            value=date.today().year,
            step=1,
        )

    st.markdown("### Faturamento por anexo")

    faturamentos: dict[str, float] = {}
    for anexo in ANEXOS_DISPONIVEIS:
        faturamentos[anexo] = st.number_input(
            f"Receita do Anexo {anexo} (R$)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key=f"receita_anexo_{anexo}",
        )

    aliquota_custom = st.checkbox("Informar aliquota efetiva manual")

    aliquotas: dict[str, float | None] = {}
    deducoes: dict[str, float | None] = {}
    if aliquota_custom:
        st.caption("Preencha em % (ex.: 6 para 6%).")
        for anexo in ANEXOS_DISPONIVEIS:
            c1, c2 = st.columns(2)
            with c1:
                aliquotas[anexo] = st.number_input(
                    f"Aliquota efetiva Anexo {anexo} (%)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    key=f"aliquota_anexo_{anexo}",
                )
            with c2:
                deducoes[anexo] = st.number_input(
                    f"Deducao legal Anexo {anexo} (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=100.0,
                    key=f"deducao_anexo_{anexo}",
                )
    else:
        for anexo in ANEXOS_DISPONIVEIS:
            aliquotas[anexo] = None
            deducoes[anexo] = None

    if st.button("Calcular DAS", type="primary"):
        resultados: list[dict[str, float | str]] = []
        avisos: list[str] = []

        for anexo, receita in faturamentos.items():
            if receita < 0:
                avisos.append(f"Anexo {anexo}: receita negativa nao permitida.")
                continue
            if receita == 0:
                continue

            try:
                resultado = calcular_das(
                    receita_bruta=receita,
                    anexo=anexo,
                    aliquota_efetiva=aliquotas[anexo],
                    deducoes=deducoes[anexo],
                )
                resultados.append(resultado)
            except ValueError as exc:
                avisos.append(f"Anexo {anexo}: {exc}")
            except Exception as exc:
                avisos.append(f"Anexo {anexo}: erro inesperado ({exc}).")

        for aviso in avisos:
            st.warning(aviso)

        if not resultados:
            st.error("Nao foi possivel apurar o DAS com os dados informados.")
            return

        total_das = sum(float(item["valor_das"]) for item in resultados)

        st.success(
            f"Apuracao concluida para {mes_referencia:02d}/{int(ano_referencia)}. "
            f"DAS total: R$ {total_das:,.2f}"
        )

        st.dataframe(resultados, use_container_width=True, hide_index=True)

        st.caption(
            f"Empresa selecionada: {empresa.get('razao_social')} | Regime: {empresa.get('regime_tributario')}"
        )


def render_fiscal_module() -> None:
    """Tela principal fiscal desacoplando UI de calculo e importacao XML."""
    st.title("Modulo Fiscal")

    tab_apuracao, tab_xml = st.tabs(["Apuracao Mensal", "Importacao XML"])

    with tab_apuracao:
        _render_apuracao_mensal()

    with tab_xml:
        render_importacao_xml()
