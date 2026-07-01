from __future__ import annotations

import csv
from datetime import date
from io import StringIO
import json
from typing import Any

import streamlit as st

from db import fetch_rows
from fiscal.apuracoes import carregar_plugins_apuracao
from fiscal.apuracoes.base import (
    ApuracaoResultado,
    ApuracaoTributoBase,
    filtrar_documentos_periodo,
    parse_documentos_fiscais,
)
from fiscal.apuracoes.strategy import selecionar_motor_apuracao


def _load_empresas() -> list[dict[str, Any]]:
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,endereco,regime_tributario",
        order_by="razao_social",
        desc=False,
    )


def _build_contexto_ui(plugin: ApuracaoTributoBase) -> dict[str, Any]:
    contexto: dict[str, Any] = {}

    if plugin.codigo == "iss":
        contexto["aliquota_iss_percent"] = st.number_input(
            "Aliquota ISS (%)",
            min_value=0.0,
            max_value=20.0,
            value=5.0,
            step=0.1,
        )

    if plugin.codigo == "irpj_csll":
        col1, col2 = st.columns(2)
        with col1:
            contexto["percentual_presumido_ir"] = st.number_input(
                "Base presumida IRPJ (%)",
                min_value=0.0,
                max_value=100.0,
                value=8.0,
                step=0.5,
            )
        with col2:
            contexto["percentual_presumido_csll"] = st.number_input(
                "Base presumida CSLL (%)",
                min_value=0.0,
                max_value=100.0,
                value=12.0,
                step=0.5,
            )

    return contexto


def _resultado_para_csv(resultado: ApuracaoResultado) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["tributo", resultado.tributo])
    writer.writerow(["periodo_inicio", resultado.periodo_inicio.isoformat()])
    writer.writerow(["periodo_fim", resultado.periodo_fim.isoformat()])
    writer.writerow(["base_legal", resultado.base_legal])
    writer.writerow(["valor_apurado", f"{resultado.valor_apurado:.2f}"])
    writer.writerow([])
    writer.writerow(["resumo", "valor"])
    for key, value in resultado.resumo.items():
        writer.writerow([key, f"{float(value):.2f}"])
    writer.writerow([])
    writer.writerow(["etapa", "formula", "valor"])
    for step in resultado.memoria_calculo:
        writer.writerow([step.get("etapa", ""), step.get("formula", ""), step.get("valor", "")])

    return buffer.getvalue().encode("utf-8")


def _render_relatorio(resultado: ApuracaoResultado) -> None:
    st.markdown("### Relatorio de Conferencia")
    st.caption(f"Base legal: {resultado.base_legal}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Valor apurado", f"R$ {resultado.valor_apurado:,.2f}")
    with c2:
        st.metric("Inicio", resultado.periodo_inicio.strftime("%d/%m/%Y"))
    with c3:
        st.metric("Fim", resultado.periodo_fim.strftime("%d/%m/%Y"))

    resumo_rows = [{"item": key, "valor": float(value)} for key, value in resultado.resumo.items()]
    st.dataframe(resumo_rows, use_container_width=True, hide_index=True)

    st.markdown("### Memoria de Calculo")
    st.dataframe(resultado.memoria_calculo, use_container_width=True, hide_index=True)

    export_payload = {
        "tributo": resultado.tributo,
        "periodo_inicio": resultado.periodo_inicio.isoformat(),
        "periodo_fim": resultado.periodo_fim.isoformat(),
        "valor_apurado": resultado.valor_apurado,
        "base_legal": resultado.base_legal,
        "resumo": resultado.resumo,
        "memoria_calculo": resultado.memoria_calculo,
    }

    st.download_button(
        label="Exportar relatorio (JSON)",
        data=json.dumps(export_payload, ensure_ascii=True, indent=2).encode("utf-8"),
        file_name=f"apuracao_{resultado.tributo.lower().replace('/', '_')}.json",
        mime="application/json",
    )

    st.download_button(
        label="Exportar memoria (CSV)",
        data=_resultado_para_csv(resultado),
        file_name=f"memoria_calculo_{resultado.tributo.lower().replace('/', '_')}.csv",
        mime="text/csv",
    )


def render_apuracao_module() -> None:
    """Menu central de apuracao com plugins de tributos e memoria de calculo."""
    st.title("Menu de Apuracao")
    st.caption("Selecione o tributo, periodo e XMLs para calcular e conferir os valores.")

    try:
        empresas = _load_empresas()
    except Exception as exc:
        st.error(f"Falha ao carregar empresas no Supabase: {exc}")
        return

    if not empresas:
        st.info("Cadastre ao menos uma empresa antes de apurar tributos.")
        return

    plugins = carregar_plugins_apuracao()
    if not plugins:
        st.error("Nenhum plugin de apuracao encontrado em fiscal/apuracoes.")
        return

    empresa_options = {
        f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in empresas
    }
    selected_empresa_label = st.selectbox("Empresa", list(empresa_options.keys()), index=0)
    empresa = empresa_options[selected_empresa_label]

    try:
        strategy = selecionar_motor_apuracao(str(empresa.get("id") or ""))
    except Exception as exc:
        st.error(f"Falha ao selecionar motor de apuracao: {exc}")
        return

    plugins_habilitados = [plugin for plugin in plugins if strategy.permite(plugin)]
    if not plugins_habilitados:
        st.error("Nenhum tributo habilitado para o regime selecionado.")
        return

    st.caption(f"Motor selecionado: {strategy.nome}")

    plugin_options = {
        f"{plugin.nome} ({plugin.codigo})": plugin for plugin in plugins_habilitados
    }
    selected_plugin_label = st.selectbox("Tributo", list(plugin_options.keys()), index=0)
    plugin = plugin_options[selected_plugin_label]

    col1, col2 = st.columns(2)
    with col1:
        periodo_inicio = st.date_input("Periodo inicial", value=date(date.today().year, date.today().month, 1))
    with col2:
        periodo_fim = st.date_input("Periodo final", value=date.today())

    st.markdown("### XMLs processados (entradas/saidas)")
    uploaded_files = st.file_uploader(
        "Envie os XMLs NF-e para apuracao",
        type=["xml"],
        accept_multiple_files=True,
    )

    contexto = _build_contexto_ui(plugin)
    contexto["cliente_id"] = empresa.get("id")
    contexto["cnpj_empresa"] = empresa.get("cnpj")
    contexto["regime_tributario"] = empresa.get("regime_tributario")
    contexto = strategy.aplicar_contexto(contexto)

    if st.button("Calcular tributo", type="primary"):
        if not uploaded_files:
            st.error("Envie pelo menos um XML para calcular o tributo.")
            return

        try:
            xml_files = [(item.name, item.getvalue()) for item in uploaded_files]
            docs = parse_documentos_fiscais(xml_files)
            docs_filtrados = filtrar_documentos_periodo(docs, periodo_inicio, periodo_fim)

            if not docs_filtrados:
                st.warning("Nenhum documento no periodo informado.")
                return

            avisos_legais = plugin.validar_legislacao(periodo_inicio, periodo_fim)
            for aviso in avisos_legais:
                st.warning(aviso)

            resultado = plugin.calcular(
                documentos=docs_filtrados,
                periodo_inicio=periodo_inicio,
                periodo_fim=periodo_fim,
                contexto=contexto,
            )
            resultado = ApuracaoResultado(
                tributo=resultado.tributo,
                periodo_inicio=resultado.periodo_inicio,
                periodo_fim=resultado.periodo_fim,
                valor_apurado=resultado.valor_apurado,
                resumo=resultado.resumo,
                memoria_calculo=plugin.gerar_memoria_calculo(resultado),
                base_legal=resultado.base_legal,
            )
            _render_relatorio(resultado)
        except Exception as exc:
            st.error(f"Falha na apuracao: {exc}")
