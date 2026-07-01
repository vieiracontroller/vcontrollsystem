from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
import xml.etree.ElementTree as ET

import streamlit as st

from db import insert_rows, fetch_rows

NFE_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _to_float(value: str) -> float:
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _find_text(node: ET.Element | None, path: str, ns: dict[str, str] | None = None) -> str:
    if node is None:
        return ""
    found = node.find(path, ns or NFE_NS)
    return (found.text or "").strip() if found is not None else ""


def _local_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _is_nfse(root: ET.Element) -> bool:
    names = {_local_name(item.tag).lower() for item in root.iter()}
    return any(name in names for name in {"nfse", "infnfse", "compnfse"})


def _is_nfe(root: ET.Element) -> bool:
    names = {_local_name(item.tag).lower() for item in root.iter()}
    return any(name in names for name in {"nfe", "nfeproc", "infnfe"})


def _load_empresas() -> list[dict[str, Any]]:
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,endereco",
        order_by="razao_social",
        desc=False,
    )


def _parse_nfe(content: bytes, file_name: str, cliente_id: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    root = ET.parse(BytesIO(content)).getroot()

    tp_nf = _find_text(root, ".//nfe:ide/nfe:tpNF")
    tipo_operacao = "entrada" if tp_nf == "0" else "saida"

    nota_row = {
        "cliente_id": cliente_id,
        "tipo_documento": "NFE",
        "tipo_operacao": tipo_operacao,
        "numero": _find_text(root, ".//nfe:ide/nfe:nNF"),
        "serie": _find_text(root, ".//nfe:ide/nfe:serie"),
        "chave_acesso": (_find_text(root, ".//nfe:infNFe", NFE_NS) or "").replace("NFe", ""),
        "data_emissao": (_find_text(root, ".//nfe:ide/nfe:dhEmi") or "")[:10],
        "cnpj_emitente": _find_text(root, ".//nfe:emit/nfe:CNPJ"),
        "cnpj_destinatario": _find_text(root, ".//nfe:dest/nfe:CNPJ") or _find_text(root, ".//nfe:dest/nfe:CPF"),
        "valor_total": _to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF")),
        "arquivo": file_name,
        "xml_base64": base64.b64encode(content).decode("ascii"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    cache_row = {
        "cliente_id": cliente_id,
        "arquivo": file_name,
        "data_emissao": nota_row["data_emissao"],
        "tipo_operacao": tipo_operacao,
        "cnpj_emitente": nota_row["cnpj_emitente"],
        "cnpj_destinatario": nota_row["cnpj_destinatario"],
        "valor_total": nota_row["valor_total"],
        "xml_base64": nota_row["xml_base64"],
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }

    return tipo_operacao, nota_row, cache_row


def _parse_nfse(content: bytes, file_name: str, cliente_id: str) -> dict[str, Any]:
    root = ET.parse(BytesIO(content)).getroot()

    numero = ""
    data_emissao = ""
    cnpj_prestador = ""
    cnpj_tomador = ""
    valor_servicos = 0.0

    for item in root.iter():
        name = _local_name(item.tag).lower()
        text = (item.text or "").strip()
        if not text:
            continue
        if name == "numero" and not numero:
            numero = text
        elif name in {"dataemissao", "dataemissao"} and not data_emissao:
            data_emissao = text[:10]
        elif name == "cnpj" and not cnpj_prestador:
            cnpj_prestador = text
        elif name == "cnpj" and cnpj_prestador and not cnpj_tomador:
            cnpj_tomador = text
        elif name in {"valorservicos", "valorliquidonfse"} and valor_servicos == 0.0:
            valor_servicos = _to_float(text)

    return {
        "cliente_id": cliente_id,
        "numero": numero,
        "data_emissao": data_emissao,
        "cnpj_prestador": cnpj_prestador,
        "cnpj_tomador": cnpj_tomador,
        "valor_servicos": valor_servicos,
        "arquivo": file_name,
        "xml_base64": base64.b64encode(content).decode("ascii"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def render_importacao_central() -> None:
    """Centro unico de importacao XML com classificacao automatica de documento fiscal."""
    st.subheader("Centro de Importacao Fiscal")
    st.caption("Arraste os XMLs e o sistema identifica automaticamente NF-e de entrada, saida ou NFS-e.")

    try:
        empresas = _load_empresas()
    except Exception as exc:
        st.error(f"Falha ao carregar clientes: {exc}")
        return

    if not empresas:
        st.info("Cadastre ao menos um cliente para iniciar a importacao fiscal.")
        return

    empresa_options = {f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in empresas}
    selected_label = st.selectbox("Cliente", list(empresa_options.keys()), index=0)
    empresa = empresa_options[selected_label]
    cliente_id = str(empresa.get("id") or "")

    uploaded_files = st.file_uploader(
        "Arraste e solte XMLs aqui",
        type=["xml"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Aguardando arquivos XML para processar.")
        return

    if st.button("Processar importacao", type="primary"):
        nf_saida_rows: list[dict[str, Any]] = []
        nf_entrada_rows: list[dict[str, Any]] = []
        cache_rows: list[dict[str, Any]] = []
        nfse_rows: list[dict[str, Any]] = []
        errors: list[str] = []

        for item in uploaded_files:
            content = item.getvalue()
            try:
                root = ET.parse(BytesIO(content)).getroot()
            except Exception:
                errors.append(f"{item.name}: arquivo XML invalido.")
                continue

            try:
                if _is_nfse(root):
                    nfse_rows.append(_parse_nfse(content, item.name, cliente_id))
                    continue

                if _is_nfe(root):
                    tipo_operacao, nota_row, cache_row = _parse_nfe(content, item.name, cliente_id)
                    if tipo_operacao == "saida":
                        nf_saida_rows.append(nota_row)
                    else:
                        nf_entrada_rows.append(nota_row)
                    cache_rows.append(cache_row)
                    continue

                errors.append(f"{item.name}: tipo de documento nao reconhecido.")
            except Exception as exc:
                errors.append(f"{item.name}: falha no processamento ({exc}).")

        try:
            all_nfe_rows = nf_saida_rows + nf_entrada_rows
            if all_nfe_rows:
                insert_rows(table_name="notas_fiscais", rows=all_nfe_rows)
                insert_rows(table_name="fiscal_nfe_xml_cache", rows=cache_rows)
            if nfse_rows:
                insert_rows(table_name="notas_servico", rows=nfse_rows)
        except Exception as exc:
            st.error(f"Falha ao salvar no banco: {exc}")
            return

        st.success("Importacao concluida com sucesso.")
        st.write(f"{len(nf_saida_rows)} notas de saida processadas")
        st.write(f"{len(nf_entrada_rows)} notas de entrada processadas")
        st.write(f"{len(nfse_rows)} notas de servico processadas")

        if errors:
            st.warning("Alguns arquivos apresentaram erro amigavel e nao travaram o processamento:")
            for err in errors:
                st.write(f"- {err}")
