from __future__ import annotations

from datetime import datetime
from io import BytesIO
import xml.etree.ElementTree as ET

import streamlit as st

from db import insert_rows
from fiscal.importador_xml import XMLProdutoPayload, sincronizar_produtos_por_xml

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


def render_importacao_xml() -> None:
    """Renderiza interface de importacao de XML de NF-e."""
    st.subheader("Importacao XML NF-e")
    st.caption("Importe XML de NF-e e prepare os dados para gravacao no Supabase.")

    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos XML de NF-e",
        type=["xml"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Aguardando upload dos XMLs.")
        return

    parsed_rows: list[dict[str, str | float]] = []
    xml_payloads: list[XMLProdutoPayload] = []
    errors: list[str] = []

    # Processa arquivo por arquivo para evitar falha total em lote misto.
    for file_obj in uploaded_files:
        try:
            content = file_obj.getvalue()
            parsed_rows.append(_parse_nfe_xml(BytesIO(content), file_obj.name))
            xml_payloads.append(XMLProdutoPayload(file_name=file_obj.name, content=content))
        except Exception as exc:
            errors.append(f"{file_obj.name}: {exc}")

    st.dataframe(parsed_rows, use_container_width=True, hide_index=True)

    if errors:
        st.warning("Alguns arquivos nao puderam ser lidos:")
        for err in errors:
            st.write(f"- {err}")

    table_name = st.text_input("Tabela destino", value=DEFAULT_FISCAL_TABLE)

    if st.button("Salvar XMLs no Supabase", type="primary"):
        try:
            result = insert_rows(table_name=table_name, rows=parsed_rows)
            st.success(
                f"Importacao concluida. Registros enviados: {result.get('inserted', 0)}"
            )
            st.json(result)

            sync_result = sincronizar_produtos_por_xml(xml_payloads)
            if sync_result.get("status") == "ok":
                st.success(
                    "Cadastro inteligente de produtos sincronizado. "
                    f"Registros processados: {sync_result.get('processed', 0)}"
                )
            else:
                st.warning(str(sync_result.get("detail", "Sem atualizacao de produtos.")))

            warnings = sync_result.get("warnings", [])
            if isinstance(warnings, list):
                for warning in warnings:
                    st.warning(str(warning))

            invalids = sync_result.get("invalid", [])
            if isinstance(invalids, list):
                for invalid in invalids:
                    st.error(str(invalid))
        except Exception as exc:
            st.error(f"Falha ao salvar no Supabase: {exc}")
