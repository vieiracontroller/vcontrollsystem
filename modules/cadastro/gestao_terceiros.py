from __future__ import annotations

from typing import Any

import streamlit as st

from db import fetch_rows, insert_rows, upsert_rows


def _load_clientes() -> list[dict[str, Any]]:
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,regime_tributario,observacoes",
        order_by="razao_social",
        desc=False,
        limit=2000,
    )


def _load_fornecedores() -> list[dict[str, Any]]:
    return fetch_rows(
        table_name="fornecedores",
        columns="id,razao_social,cnpj,observacoes",
        order_by="razao_social",
        desc=False,
        limit=2000,
    )


def _upsert_fornecedor(payload: dict[str, Any]) -> None:
    upsert_rows(
        table_name="fornecedores",
        rows=[payload],
        on_conflict="id",
    )


def _upsert_cliente(payload: dict[str, Any]) -> None:
    upsert_rows(
        table_name="clientes",
        rows=[payload],
        on_conflict="id",
    )


def _render_crud_clientes(clientes: list[dict[str, Any]]) -> None:
    st.markdown("### Clientes")
    st.dataframe(clientes, use_container_width=True, hide_index=True)

    if not clientes:
        st.info("Nenhum cliente encontrado.")
        return

    options = {f"{item.get('razao_social')} ({item.get('cnpj')})": item for item in clientes}
    selected_label = st.selectbox("Cliente para editar", list(options.keys()), index=0)
    cliente = options[selected_label]

    with st.form("editar_cliente"):
        razao = st.text_input("Razao social", value=str(cliente.get("razao_social") or ""))
        cnpj = st.text_input("CNPJ", value=str(cliente.get("cnpj") or ""))
        regime = st.selectbox(
            "Regime tributario",
            ["Simples Nacional", "Presumido", "Real"],
            index=["Simples Nacional", "Presumido", "Real"].index(str(cliente.get("regime_tributario") or "Simples Nacional")) if str(cliente.get("regime_tributario") or "Simples Nacional") in ["Simples Nacional", "Presumido", "Real"] else 0,
        )
        obs = st.text_area("Observacoes", value=str(cliente.get("observacoes") or ""))
        submitted = st.form_submit_button("Salvar cliente")

    if submitted:
        _upsert_cliente(
            {
                "id": cliente.get("id"),
                "razao_social": razao,
                "cnpj": cnpj,
                "regime_tributario": regime,
                "observacoes": obs,
            }
        )
        st.success("Cliente atualizado com sucesso.")


def _render_crud_fornecedores(fornecedores: list[dict[str, Any]]) -> None:
    st.markdown("### Fornecedores")
    st.dataframe(fornecedores, use_container_width=True, hide_index=True)

    with st.form("novo_fornecedor"):
        st.markdown("#### Novo fornecedor")
        razao_new = st.text_input("Razao social (novo)")
        cnpj_new = st.text_input("CNPJ (novo)")
        obs_new = st.text_area("Observacoes (novo)")
        create_submitted = st.form_submit_button("Criar fornecedor")

    if create_submitted:
        if not razao_new or not cnpj_new:
            st.error("Informe razao social e CNPJ para criar fornecedor.")
        else:
            insert_rows(
                table_name="fornecedores",
                rows=[
                    {
                        "razao_social": razao_new,
                        "cnpj": cnpj_new,
                        "observacoes": obs_new,
                    }
                ],
            )
            st.success("Fornecedor criado com sucesso.")

    if not fornecedores:
        st.info("Nenhum fornecedor encontrado.")
        return

    options = {f"{item.get('razao_social')} ({item.get('cnpj')})": item for item in fornecedores}
    selected_label = st.selectbox("Fornecedor para editar/excluir", list(options.keys()), index=0)
    fornecedor = options[selected_label]

    col_edit, col_delete = st.columns(2)

    with col_edit:
        with st.form("editar_fornecedor"):
            razao = st.text_input("Razao social", value=str(fornecedor.get("razao_social") or ""))
            cnpj = st.text_input("CNPJ", value=str(fornecedor.get("cnpj") or ""))
            obs = st.text_area("Observacoes", value=str(fornecedor.get("observacoes") or ""))
            submitted = st.form_submit_button("Salvar fornecedor")

        if submitted:
            _upsert_fornecedor(
                {
                    "id": fornecedor.get("id"),
                    "razao_social": razao,
                    "cnpj": cnpj,
                    "observacoes": obs,
                }
            )
            st.success("Fornecedor atualizado com sucesso.")

    with col_delete:
        st.warning("Exclusao logica simplificada: marca observacao como EXCLUIDO.")
        if st.button("Excluir fornecedor selecionado"):
            _upsert_fornecedor(
                {
                    "id": fornecedor.get("id"),
                    "razao_social": fornecedor.get("razao_social"),
                    "cnpj": fornecedor.get("cnpj"),
                    "observacoes": "EXCLUIDO_MANUAL",
                }
            )
            st.success("Fornecedor marcado como excluido.")


def render_gestao_terceiros() -> None:
    """Tela profissional para gestao de clientes e fornecedores com filtro por tipo."""
    st.title("Gestao de Terceiros")
    st.caption("Corrija manualmente qualquer divergencia da importacao automatica.")

    filtro = st.radio(
        "Filtrar contatos por tipo",
        ["Todos", "Cliente", "Fornecedor"],
        horizontal=True,
    )

    clientes = _load_clientes() if filtro in {"Todos", "Cliente"} else []
    fornecedores = _load_fornecedores() if filtro in {"Todos", "Fornecedor"} else []

    if filtro in {"Todos", "Cliente"}:
        _render_crud_clientes(clientes)

    if filtro in {"Todos", "Fornecedor"}:
        _render_crud_fornecedores(fornecedores)
