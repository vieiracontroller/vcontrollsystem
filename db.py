from __future__ import annotations

from typing import Any

import streamlit as st

try:
    from supabase import create_client
except ModuleNotFoundError:
    create_client = None


def _get_secret_value(section: str, key: str, fallback_key: str) -> str:
    """Le um segredo no formato TOML por secao ou por chave plana."""
    section_data = st.secrets.get(section, {})
    if isinstance(section_data, dict) and key in section_data:
        return str(section_data[key])
    if fallback_key in st.secrets:
        return str(st.secrets[fallback_key])
    return ""


@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Any:
    """Centraliza a criacao do cliente Supabase para reuso na aplicacao."""
    if create_client is None:
        raise RuntimeError(
            "Biblioteca Supabase indisponivel no ambiente. "
            "Adicione 'supabase' no requirements.txt e refaca o deploy."
        )

    url = _get_secret_value("supabase", "url", "SUPABASE_URL")
    key = _get_secret_value("supabase", "key", "SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Supabase nao configurado. Defina [supabase].url e [supabase].key "
            "ou SUPABASE_URL/SUPABASE_KEY em st.secrets."
        )

    return create_client(url, key)


def insert_rows(table_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Insere uma lista de registros em uma tabela do Supabase."""
    if not rows:
        return {"status": "skipped", "detail": "Nenhum registro para inserir."}

    client = get_supabase_client()
    response = client.table(table_name).insert(rows).execute()

    return {
        "status": "ok",
        "table": table_name,
        "inserted": len(rows),
        "response": response.data,
    }


def fetch_rows(
    table_name: str,
    columns: str = "*",
    order_by: str | None = None,
    desc: bool = False,
) -> list[dict[str, Any]]:
    """Busca registros de uma tabela de forma reutilizavel."""
    client = get_supabase_client()
    query = client.table(table_name).select(columns)

    if order_by:
        query = query.order(order_by, desc=desc)

    response = query.execute()
    return list(response.data or [])
