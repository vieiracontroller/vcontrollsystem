from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:
    import streamlit as st
except ModuleNotFoundError:
    st = None

try:
    from supabase import create_client
except ModuleNotFoundError:
    create_client = None


def _get_secret_value(section: str, key: str, fallback_key: str) -> str:
    """Le um segredo no formato TOML por secao ou por chave plana."""
    if st is not None:
        section_data = st.secrets.get(section, {})
        if isinstance(section_data, dict) and key in section_data:
            return str(section_data[key])
        if fallback_key in st.secrets:
            return str(st.secrets[fallback_key])
    env_value = os.getenv(fallback_key, "")
    if env_value:
        return env_value
    return ""


def _create_supabase_client() -> Any:
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


if st is not None:

    @st.cache_resource(show_spinner=False)
    def get_supabase_client() -> Any:
        return _create_supabase_client()

else:

    @lru_cache(maxsize=1)
    def get_supabase_client() -> Any:
        return _create_supabase_client()


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
    eq_filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Busca registros de uma tabela de forma reutilizavel."""
    client = get_supabase_client()
    query = client.table(table_name).select(columns)

    if eq_filters:
        for key, value in eq_filters.items():
            query = query.eq(key, value)

    if order_by:
        query = query.order(order_by, desc=desc)

    if limit is not None:
        query = query.limit(limit)

    response = query.execute()
    return list(response.data or [])


def upsert_rows(
    table_name: str,
    rows: list[dict[str, Any]],
    on_conflict: str,
) -> dict[str, Any]:
    """Executa upsert em lote para inserir ou atualizar registros."""
    if not rows:
        return {"status": "skipped", "detail": "Nenhum registro para upsert."}

    client = get_supabase_client()
    response = client.table(table_name).upsert(rows, on_conflict=on_conflict).execute()

    return {
        "status": "ok",
        "table": table_name,
        "processed": len(rows),
        "response": response.data,
    }
