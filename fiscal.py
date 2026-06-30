from __future__ import annotations

from datetime import datetime
from io import BytesIO
import xml.etree.ElementTree as ET

import streamlit as st

from db import insert_rows

NFE_NAMESPACE = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
DEFAULT_FISCAL_TABLE = "fiscal_nfe_imports"


def _find_text(node: ET.Element, path: str) -> str:
    """Busca texto em um caminho XML com namespace e retorna string limpa."""
    found = node.find(path, NFE_NAMESPACE)
    return (found.text or "").strip() if found is not None else ""


def _parse_nfe_xml(raw_file: BytesIO, original_name: str) -> dict[str, str | float]:
    """Extrai campos essenciais da NF-e para uso fiscal e persistencia."""
    tree = ET.parse(raw_file)
    root = tree.getroot()

    emitente = _find_text(root, ".//nfe:emit/nfe:xNome")
    cnpj = _find_text(root, ".//nfe:emit/nfe:CNPJ")
    valor_str = _find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF")

    valor = float(valor_str.replace(",", ".")) if valor_str else 0.0

    return {
        "arquivo": original_name,
        "emitente": emitente,
        "cnpj_emitente": cnpj,
        "valor_total": valor,
        "origem": "upload_streamlit",
        "criado_em": datetime.utcnow().isoformat(),
    }


def render_fiscal_module() -> None:
    """Renderiza o modulo fiscal com importacao de XML de NF-e."""
    st.title("Modulo Fiscal")
    st.caption("Importe XML de NF-e e prepare os dados para gravacao no Supabase.")

    st.subheader("1) Upload dos XMLs")
    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos XML de NF-e",
        type=["xml"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Aguardando upload dos XMLs.")
        return

    parsed_rows: list[dict[str, str | float]] = []
    errors: list[str] = []

    # Processa arquivo por arquivo para evitar falha total em lote misto.
    for file_obj in uploaded_files:
        try:
            parsed_rows.append(_parse_nfe_xml(file_obj, file_obj.name))
        except Exception as exc:
            errors.append(f"{file_obj.name}: {exc}")

    st.subheader("2) Resultado do processamento")
    st.dataframe(parsed_rows, use_container_width=True, hide_index=True)

    if errors:
        st.warning("Alguns arquivos nao puderam ser lidos:")
        for err in errors:
            st.write(f"- {err}")

    st.subheader("3) Persistencia no Supabase")
    table_name = st.text_input("Tabela destino", value=DEFAULT_FISCAL_TABLE)

    if st.button("Salvar no Supabase", type="primary"):
        try:
            result = insert_rows(table_name=table_name, rows=parsed_rows)
            st.success(
                f"Importacao concluida. Registros enviados: {result.get('inserted', 0)}"
            )
            st.json(result)
        except Exception as exc:
            st.error(f"Falha ao salvar no Supabase: {exc}")
