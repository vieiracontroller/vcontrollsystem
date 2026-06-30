from __future__ import annotations

from typing import Any

import streamlit as st

from db import fetch_rows, upsert_rows
from utils.tributario_validators import validar_produto_fiscal


def _load_clientes() -> list[dict[str, Any]]:
    """Carrega clientes para contexto de gestao de produtos."""
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj",
        order_by="razao_social",
    )


def _load_produtos(cliente_id: str) -> list[dict[str, Any]]:
    """Carrega produtos por cliente para exibicao e edicao fiscal."""
    return fetch_rows(
        table_name="produtos",
        columns=(
            "id,cliente_id,codigo_interno,descricao,ncm,cest,unidade_medida,"
            "cfop_padrao,cst_icms,aliquota_padrao_icms,aliquota_ibs,aliquota_cbs"
        ),
        eq_filters={"cliente_id": cliente_id},
        order_by="descricao",
    )


def render_produtos_module() -> None:
    """Tela de gestao de produtos com foco em campos fiscais."""
    st.title("Cadastro de Produtos")
    st.caption(
        "Edite dados fiscais de ICMS e reforma tributaria (IBS/CBS) "
        "dos produtos sincronizados por XML."
    )

    try:
        clientes = _load_clientes()
    except Exception as exc:
        st.error(f"Falha ao carregar clientes: {exc}")
        return

    if not clientes:
        st.info("Nenhum cliente cadastrado. Cadastre clientes antes de gerenciar produtos.")
        return

    cliente_options = {
        f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in clientes
    }
    cliente_label = st.selectbox("Cliente", list(cliente_options.keys()), index=0)
    cliente = cliente_options[cliente_label]

    try:
        produtos = _load_produtos(str(cliente.get("id") or ""))
    except Exception as exc:
        st.error(f"Falha ao carregar produtos: {exc}")
        return

    st.subheader("Produtos sincronizados")
    st.dataframe(produtos, use_container_width=True, hide_index=True)

    if not produtos:
        st.info("Nenhum produto encontrado para este cliente. Importe XMLs no modulo fiscal.")
        return

    mapa_produtos = {
        f"{p.get('codigo_interno')} - {p.get('descricao')}": p for p in produtos
    }
    produto_label = st.selectbox("Produto para editar", list(mapa_produtos.keys()), index=0)
    produto = mapa_produtos[produto_label]

    with st.form("editar_produto_fiscal"):
        descricao = st.text_input("Descricao", value=str(produto.get("descricao") or ""))
        ncm = st.text_input("NCM", value=str(produto.get("ncm") or ""), max_chars=8)
        cest = st.text_input("CEST", value=str(produto.get("cest") or ""), max_chars=7)
        cfop = st.text_input("CFOP padrao", value=str(produto.get("cfop_padrao") or ""), max_chars=4)
        cst_icms = st.text_input("CST/CSOSN ICMS", value=str(produto.get("cst_icms") or ""), max_chars=3)
        unidade = st.text_input(
            "Unidade de medida",
            value=str(produto.get("unidade_medida") or ""),
            max_chars=6,
        )
        aliquota_icms = st.number_input(
            "Aliquota padrao ICMS (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(produto.get("aliquota_padrao_icms") or 0.0),
            step=0.01,
        )
        c1, c2 = st.columns(2)
        with c1:
            aliquota_ibs = st.number_input(
                "Aliquota IBS (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(produto.get("aliquota_ibs") or 0.0),
                step=0.01,
            )
        with c2:
            aliquota_cbs = st.number_input(
                "Aliquota CBS (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(produto.get("aliquota_cbs") or 0.0),
                step=0.01,
            )

        submitted = st.form_submit_button("Salvar alteracoes", type="primary")

    if not submitted:
        return

    produto_editado = {
        "cliente_id": produto.get("cliente_id"),
        "codigo_interno": produto.get("codigo_interno"),
        "descricao": descricao.strip(),
        "ncm": ncm.strip(),
        "cest": cest.strip(),
        "cfop_padrao": cfop.strip(),
        "cst_icms": cst_icms.strip(),
        "unidade_medida": unidade.strip(),
        "aliquota_padrao_icms": float(aliquota_icms),
        "aliquota_ibs": float(aliquota_ibs),
        "aliquota_cbs": float(aliquota_cbs),
    }

    produto_normalizado, errors, warnings = validar_produto_fiscal(produto_editado)
    for warning in warnings:
        st.warning(warning)

    if errors:
        for error in errors:
            st.error(error)
        return

    payload = [produto_normalizado]

    try:
        result = upsert_rows(
            table_name="produtos",
            rows=payload,
            on_conflict="cliente_id,codigo_interno",
        )
        st.success("Produto atualizado com sucesso.")
        st.json(result)
    except Exception as exc:
        st.error(f"Falha ao atualizar produto: {exc}")
