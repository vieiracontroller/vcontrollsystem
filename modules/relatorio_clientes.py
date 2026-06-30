from __future__ import annotations

import csv
from io import StringIO
from typing import Any

import streamlit as st

from db import fetch_rows
from utils.validators import format_cnpj


def _flatten_cliente(row: dict[str, Any]) -> dict[str, str]:
    """Normaliza registro para exibicao tabular e exportacao CSV."""
    endereco = row.get("endereco") or {}
    socios = row.get("socios") or []

    return {
        "id": str(row.get("id") or ""),
        "razao_social": str(row.get("razao_social") or ""),
        "cnpj": format_cnpj(str(row.get("cnpj") or "")),
        "regime_tributario": str(row.get("regime_tributario") or ""),
        "cep": str(endereco.get("cep") or ""),
        "rua": str(endereco.get("rua") or ""),
        "numero": str(endereco.get("numero") or ""),
        "bairro": str(endereco.get("bairro") or ""),
        "cidade": str(endereco.get("cidade") or ""),
        "estado": str(endereco.get("estado") or ""),
        "qtd_socios": str(len(socios)),
        "observacoes": str(row.get("observacoes") or ""),
        "created_at": str(row.get("created_at") or ""),
    }


def _rows_to_csv(rows: list[dict[str, str]]) -> bytes:
    """Converte lista de dict para CSV em bytes para download."""
    if not rows:
        return b""

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _apply_filters(
    rows: list[dict[str, str]],
    regime_filter: str,
    estado_filter: str,
    cidade_filter: str,
    busca: str,
) -> list[dict[str, str]]:
    """Aplica filtros de relatorio sobre os registros normalizados."""
    filtered = rows

    if regime_filter != "Todos":
        filtered = [r for r in filtered if r["regime_tributario"] == regime_filter]

    if estado_filter != "Todos":
        filtered = [r for r in filtered if r["estado"].upper() == estado_filter.upper()]

    if cidade_filter:
        normalized = cidade_filter.strip().lower()
        filtered = [r for r in filtered if normalized in r["cidade"].lower()]

    if busca:
        normalized = busca.strip().lower()
        filtered = [
            r
            for r in filtered
            if normalized in r["razao_social"].lower() or normalized in r["cnpj"].lower()
        ]

    return filtered


def render_relatorio_clientes() -> None:
    """Renderiza relatorio da base de clientes cadastrada no Supabase."""
    st.title("Relatorio de Clientes")
    st.caption("Visao analitica da base cadastrada com filtros e exportacao.")

    if st.button("Atualizar base", type="secondary"):
        st.cache_data.clear()

    @st.cache_data(ttl=30, show_spinner=False)
    def _load_clientes() -> list[dict[str, Any]]:
        return fetch_rows(table_name="clientes", columns="*", order_by="created_at", desc=True)

    try:
        raw_rows = _load_clientes()
    except Exception as exc:
        st.error(f"Erro ao carregar clientes do Supabase: {exc}")
        return

    if not raw_rows:
        st.info("Nenhum cliente cadastrado ainda.")
        return

    flat_rows = [_flatten_cliente(row) for row in raw_rows]

    regimes = sorted({r["regime_tributario"] for r in flat_rows if r["regime_tributario"]})
    estados = sorted({r["estado"] for r in flat_rows if r["estado"]})

    f1, f2, f3, f4 = st.columns([1.2, 1, 1.2, 1.6])
    with f1:
        regime_filter = st.selectbox("Regime", ["Todos", *regimes], index=0)
    with f2:
        estado_filter = st.selectbox("Estado", ["Todos", *estados], index=0)
    with f3:
        cidade_filter = st.text_input("Cidade", placeholder="Ex: Sao Paulo")
    with f4:
        busca = st.text_input("Buscar", placeholder="Razao social ou CNPJ")

    filtered_rows = _apply_filters(
        rows=flat_rows,
        regime_filter=regime_filter,
        estado_filter=estado_filter,
        cidade_filter=cidade_filter,
        busca=busca,
    )

    total = len(filtered_rows)
    total_simples = sum(1 for r in filtered_rows if r["regime_tributario"] == "Simples Nacional")
    total_presumido = sum(1 for r in filtered_rows if r["regime_tributario"] == "Presumido")
    total_real = sum(1 for r in filtered_rows if r["regime_tributario"] == "Real")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de clientes", total)
    c2.metric("Simples Nacional", total_simples)
    c3.metric("Presumido", total_presumido)
    c4.metric("Real", total_real)

    st.dataframe(filtered_rows, use_container_width=True, hide_index=True)

    csv_bytes = _rows_to_csv(filtered_rows)
    st.download_button(
        label="Baixar relatorio CSV",
        data=csv_bytes,
        file_name="relatorio_clientes.csv",
        mime="text/csv",
        disabled=not filtered_rows,
    )
