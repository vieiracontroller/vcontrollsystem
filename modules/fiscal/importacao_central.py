from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
import xml.etree.ElementTree as ET

import streamlit as st

from db import fetch_rows, insert_rows, upsert_rows

NFE_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

CATEGORIAS_DOC = [
    "NFE_SAIDA",
    "NFE_ENTRADA",
    "NFSE_SAIDA",
    "NFSE_ENTRADA",
    "NAO_IDENTIFICADO",
]

MODO_CLASSIFICACAO = [
    "AUTOMATICA",
    "NFE_SAIDA",
    "NFE_ENTRADA",
    "NFSE_SAIDA",
    "NFSE_ENTRADA",
    "NAO_IDENTIFICADO",
]


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


def _extract_doc_emit_dest(root: ET.Element) -> tuple[str, str]:
    emit = _find_text(root, ".//nfe:emit/nfe:CNPJ") or _find_text(root, ".//nfe:emit/nfe:CPF")
    dest = _find_text(root, ".//nfe:dest/nfe:CNPJ") or _find_text(root, ".//nfe:dest/nfe:CPF")
    return emit, dest


def _classificar_nfe(root: ET.Element) -> str:
    tp_nf = _find_text(root, ".//nfe:ide/nfe:tpNF")
    if tp_nf == "1":
        return "NFE_SAIDA"
    if tp_nf == "0":
        return "NFE_ENTRADA"
    return "NAO_IDENTIFICADO"


def _parse_nfse_generico(root: ET.Element) -> dict[str, str]:
    data = {
        "numero": "",
        "data_emissao": "",
        "cnpj_prestador": "",
        "cnpj_tomador": "",
        "valor_servicos": "0",
    }

    cnpj_values: list[str] = []
    for item in root.iter():
        name = _local_name(item.tag).lower()
        text = (item.text or "").strip()
        if not text:
            continue

        if name == "numero" and not data["numero"]:
            data["numero"] = text
        elif name in {"dataemissao", "competencia"} and not data["data_emissao"]:
            data["data_emissao"] = text[:10]
        elif name == "cnpj":
            cnpj_values.append(text)
        elif name in {"valorservicos", "valorliquidonfse", "valornfse"} and data["valor_servicos"] == "0":
            data["valor_servicos"] = text

    if cnpj_values:
        data["cnpj_prestador"] = cnpj_values[0]
    if len(cnpj_values) > 1:
        data["cnpj_tomador"] = cnpj_values[1]

    return data


def _classificar_nfse(root: ET.Element) -> str:
    info = _parse_nfse_generico(root)
    if info["cnpj_prestador"] and info["cnpj_tomador"]:
        return "NFSE_SAIDA"
    return "NAO_IDENTIFICADO"


def _load_empresas() -> list[dict[str, Any]]:
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,endereco,regime_tributario",
        order_by="razao_social",
        desc=False,
    )


def _get_cliente_by_cnpj(cnpj: str) -> dict[str, Any] | None:
    if not cnpj:
        return None
    rows = fetch_rows(
        table_name="clientes",
        columns="*",
        eq_filters={"cnpj": cnpj},
        limit=1,
    )
    return rows[0] if rows else None


def _get_fornecedor_by_cnpj(cnpj: str) -> dict[str, Any] | None:
    if not cnpj:
        return None
    rows = fetch_rows(
        table_name="fornecedores",
        columns="*",
        eq_filters={"cnpj": cnpj},
        limit=1,
    )
    return rows[0] if rows else None


def _ensure_cliente(cnpj: str, razao_social: str) -> str | None:
    if not cnpj:
        return None

    existing = _get_cliente_by_cnpj(cnpj)
    if existing:
        return str(existing.get("id") or "")

    row = {
        "razao_social": razao_social or f"Cliente {cnpj}",
        "cnpj": cnpj,
        "endereco": {},
        "regime_tributario": "Simples Nacional",
        "socios": [],
        "observacoes": "Cadastro automatico via Centro de Importacao Fiscal",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = insert_rows(table_name="clientes", rows=[row])
    response = result.get("response", [])
    if response:
        return str(response[0].get("id") or "")
    return None


def _ensure_fornecedor(cnpj: str, razao_social: str) -> str | None:
    if not cnpj:
        return None

    existing = _get_fornecedor_by_cnpj(cnpj)
    if existing:
        return str(existing.get("id") or "")

    row = {
        "razao_social": razao_social or f"Fornecedor {cnpj}",
        "cnpj": cnpj,
        "observacoes": "Cadastro automatico via Centro de Importacao Fiscal",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = insert_rows(table_name="fornecedores", rows=[row])
    response = result.get("response", [])
    if response:
        return str(response[0].get("id") or "")
    return None


def _ensure_produtos(cliente_id: str, root: ET.Element) -> int:
    produtos_rows: list[dict[str, Any]] = []

    for det in root.findall(".//nfe:det", NFE_NS):
        prod = det.find("nfe:prod", NFE_NS)
        if prod is None:
            continue

        codigo = _find_text(prod, "nfe:cProd") or _find_text(prod, "nfe:cEAN")
        if not codigo:
            continue

        descricao = _find_text(prod, "nfe:xProd") or "Produto importado"
        produtos_rows.append(
            {
                "cliente_id": cliente_id,
                "codigo_interno": codigo,
                "descricao": descricao,
                "ncm": _find_text(prod, "nfe:NCM"),
                "cest": _find_text(prod, "nfe:CEST"),
                "unidade_medida": _find_text(prod, "nfe:uCom"),
                "aliquota_padrao_icms": 0.0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    if not produtos_rows:
        return 0

    upsert_rows(
        table_name="produtos",
        rows=produtos_rows,
        on_conflict="cliente_id,codigo_interno",
    )
    return len(produtos_rows)


def _save_nfe(
    cliente_empresa_id: str,
    fornecedor_id: str | None,
    cliente_terceiro_id: str | None,
    categoria: str,
    root: ET.Element,
    file_name: str,
    content: bytes,
) -> None:
    emit_cnpj, dest_cnpj = _extract_doc_emit_dest(root)
    tipo_operacao = "Saida" if categoria == "NFE_SAIDA" else "Entrada"

    row = {
        "cliente_id": cliente_empresa_id,
        "fornecedor_id": fornecedor_id,
        "cliente_terceiro_id": cliente_terceiro_id,
        "tipo_documento": "NFE",
        "tipo_operacao": tipo_operacao,
        "classificacao_importacao": categoria,
        "numero": _find_text(root, ".//nfe:ide/nfe:nNF"),
        "serie": _find_text(root, ".//nfe:ide/nfe:serie"),
        "chave_acesso": (_find_text(root, ".//nfe:infNFe", NFE_NS) or "").replace("NFe", ""),
        "data_emissao": (_find_text(root, ".//nfe:ide/nfe:dhEmi") or "")[:10],
        "cnpj_emitente": emit_cnpj,
        "cnpj_destinatario": dest_cnpj,
        "valor_total": _to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF")),
        "arquivo": file_name,
        "xml_base64": base64.b64encode(content).decode("ascii"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    insert_rows(table_name="notas_fiscais", rows=[row])

    cache_row = {
        "cliente_id": cliente_empresa_id,
        "arquivo": file_name,
        "data_emissao": row["data_emissao"],
        "tipo_operacao": tipo_operacao.lower(),
        "cnpj_emitente": emit_cnpj,
        "cnpj_destinatario": dest_cnpj,
        "valor_total": row["valor_total"],
        "xml_base64": row["xml_base64"],
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }
    insert_rows(table_name="fiscal_nfe_xml_cache", rows=[cache_row])


def _save_nfse(
    cliente_empresa_id: str,
    fornecedor_id: str | None,
    cliente_terceiro_id: str | None,
    categoria: str,
    root: ET.Element,
    file_name: str,
    content: bytes,
) -> None:
    info = _parse_nfse_generico(root)

    tipo_operacao = "Saida" if categoria == "NFSE_SAIDA" else "Entrada"
    row = {
        "cliente_id": cliente_empresa_id,
        "fornecedor_id": fornecedor_id,
        "cliente_terceiro_id": cliente_terceiro_id,
        "tipo_operacao": tipo_operacao,
        "classificacao_importacao": categoria,
        "numero": info["numero"],
        "data_emissao": info["data_emissao"],
        "cnpj_prestador": info["cnpj_prestador"],
        "cnpj_tomador": info["cnpj_tomador"],
        "valor_servicos": _to_float(info["valor_servicos"]),
        "arquivo": file_name,
        "xml_base64": base64.b64encode(content).decode("ascii"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    insert_rows(table_name="notas_servico", rows=[row])


def _build_drafts(
    uploaded_files: list[Any],
    classificacao_lote: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    drafts: list[dict[str, Any]] = []
    errors: list[str] = []

    for item in uploaded_files:
        content = item.getvalue()
        try:
            root = ET.parse(BytesIO(content)).getroot()
        except Exception:
            errors.append(f"{item.name}: arquivo XML invalido.")
            continue

        categoria = "NAO_IDENTIFICADO"
        tipo_documento = "NAO_IDENTIFICADO"
        cnpj_emitente = ""
        cnpj_destinatario = ""

        if _is_nfse(root):
            tipo_documento = "NFSE"
            categoria = _classificar_nfse(root)
            info = _parse_nfse_generico(root)
            cnpj_emitente = info["cnpj_prestador"]
            cnpj_destinatario = info["cnpj_tomador"]
        elif _is_nfe(root):
            tipo_documento = "NFE"
            categoria = _classificar_nfe(root)
            cnpj_emitente, cnpj_destinatario = _extract_doc_emit_dest(root)

        if classificacao_lote != "AUTOMATICA":
            categoria = classificacao_lote
            if categoria.startswith("NFE"):
                tipo_documento = "NFE"
            elif categoria.startswith("NFSE"):
                tipo_documento = "NFSE"

        drafts.append(
            {
                "arquivo": item.name,
                "categoria": categoria,
                "tipo_documento": tipo_documento,
                "cnpj_emitente": cnpj_emitente,
                "cnpj_destinatario": cnpj_destinatario,
                "xml_base64": base64.b64encode(content).decode("ascii"),
            }
        )

    return drafts, errors


def _render_badges(counters: dict[str, int]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("NF-e de Saida", counters.get("NFE_SAIDA", 0))
    with c2:
        st.metric("NF-e de Entrada", counters.get("NFE_ENTRADA", 0))
    with c3:
        st.metric("NFS-e de Saida", counters.get("NFSE_SAIDA", 0))
    with c4:
        st.metric("NFS-e de Entrada", counters.get("NFSE_ENTRADA", 0))


def _sync_terceiros_produtos(cliente_empresa_id: str, drafts: list[dict[str, Any]]) -> dict[str, int]:
    clientes_criados = 0
    fornecedores_criados = 0
    produtos_sincronizados = 0

    for draft in drafts:
        content = base64.b64decode(str(draft["xml_base64"]))
        root = ET.parse(BytesIO(content)).getroot()
        categoria = str(draft["categoria"])

        cnpj_emitente = str(draft.get("cnpj_emitente") or "")
        cnpj_dest = str(draft.get("cnpj_destinatario") or "")

        if categoria in {"NFE_ENTRADA", "NFSE_ENTRADA"}:
            if cnpj_emitente and not _get_fornecedor_by_cnpj(cnpj_emitente):
                if _ensure_fornecedor(cnpj_emitente, f"Fornecedor {cnpj_emitente}"):
                    fornecedores_criados += 1

        if categoria in {"NFE_SAIDA", "NFSE_SAIDA"}:
            if cnpj_dest and not _get_cliente_by_cnpj(cnpj_dest):
                if _ensure_cliente(cnpj_dest, f"Cliente {cnpj_dest}"):
                    clientes_criados += 1

        if draft.get("tipo_documento") == "NFE":
            produtos_sincronizados += _ensure_produtos(cliente_empresa_id, root)

    return {
        "clientes_criados": clientes_criados,
        "fornecedores_criados": fornecedores_criados,
        "produtos_sincronizados": produtos_sincronizados,
    }


def _finalizar_importacao(cliente_empresa_id: str, drafts: list[dict[str, Any]]) -> dict[str, int]:
    counters = {key: 0 for key in CATEGORIAS_DOC}

    for draft in drafts:
        categoria = str(draft.get("categoria") or "NAO_IDENTIFICADO")
        if categoria not in counters:
            categoria = "NAO_IDENTIFICADO"

        content = base64.b64decode(str(draft["xml_base64"]))
        root = ET.parse(BytesIO(content)).getroot()

        fornecedor_id: str | None = None
        cliente_terceiro_id: str | None = None

        cnpj_emitente = str(draft.get("cnpj_emitente") or "")
        cnpj_dest = str(draft.get("cnpj_destinatario") or "")

        if categoria in {"NFE_ENTRADA", "NFSE_ENTRADA"}:
            fornecedor_id = _ensure_fornecedor(cnpj_emitente, f"Fornecedor {cnpj_emitente}")
        if categoria in {"NFE_SAIDA", "NFSE_SAIDA"}:
            cliente_terceiro_id = _ensure_cliente(cnpj_dest, f"Cliente {cnpj_dest}")

        try:
            if draft.get("tipo_documento") == "NFE":
                _save_nfe(
                    cliente_empresa_id=cliente_empresa_id,
                    fornecedor_id=fornecedor_id,
                    cliente_terceiro_id=cliente_terceiro_id,
                    categoria=categoria,
                    root=root,
                    file_name=str(draft["arquivo"]),
                    content=content,
                )
                _ensure_produtos(cliente_empresa_id, root)
            elif draft.get("tipo_documento") == "NFSE":
                _save_nfse(
                    cliente_empresa_id=cliente_empresa_id,
                    fornecedor_id=fornecedor_id,
                    cliente_terceiro_id=cliente_terceiro_id,
                    categoria=categoria,
                    root=root,
                    file_name=str(draft["arquivo"]),
                    content=content,
                )
            else:
                categoria = "NAO_IDENTIFICADO"
        except Exception:
            categoria = "NAO_IDENTIFICADO"

        counters[categoria] = counters.get(categoria, 0) + 1

    return counters


def render_importacao_central() -> None:
    """Centro unico de importacao XML com classificacao inteligente e automacao de cadastros."""
    st.subheader("Centro de Importacao Fiscal")
    st.caption("Arraste XMLs para classificar automaticamente em NF-e/NFS-e de entrada e saida.")

    try:
        empresas = _load_empresas()
    except Exception as exc:
        st.error(f"Falha ao carregar clientes: {exc}")
        return

    if not empresas:
        st.info("Cadastre ao menos um cliente para iniciar a importacao fiscal.")
        return

    empresa_options = {f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in empresas}
    selected_label = st.selectbox("Cliente da Contabilidade", list(empresa_options.keys()), index=0)
    empresa = empresa_options[selected_label]
    cliente_empresa_id = str(empresa.get("id") or "")

    if "importacao_drafts" not in st.session_state:
        st.session_state["importacao_drafts"] = []
    if "importacao_counters" not in st.session_state:
        st.session_state["importacao_counters"] = {key: 0 for key in CATEGORIAS_DOC}

    uploaded_files = st.file_uploader(
        "Arraste e solte XMLs aqui",
        type=["xml"],
        accept_multiple_files=True,
    )

    classificacao_lote = st.radio(
        "Tipo de XML do lote",
        MODO_CLASSIFICACAO,
        index=0,
        horizontal=True,
        help="Use AUTOMATICA para detectar pelo XML ou force o tipo para todo o lote.",
    )

    if uploaded_files and st.button("Analisar lote", type="primary"):
        drafts, errors = _build_drafts(uploaded_files, classificacao_lote)
        st.session_state["importacao_drafts"] = drafts

        if errors:
            st.warning("Alguns arquivos apresentaram erro amigavel e nao travaram o processamento:")
            for err in errors:
                st.write(f"- {err}")

        if not drafts:
            st.error("Nenhum XML valido para importacao.")
            return

    drafts = st.session_state.get("importacao_drafts", [])
    if not drafts:
        st.info("Aguardando lote de XMLs para classificar.")
        return

    st.markdown("### Classificacao do Lote")

    for idx, draft in enumerate(drafts):
        if draft.get("categoria") != "NAO_IDENTIFICADO":
            continue
        selected = st.selectbox(
            f"Categoria manual para {draft.get('arquivo')}",
            CATEGORIAS_DOC,
            index=CATEGORIAS_DOC.index("NAO_IDENTIFICADO"),
            key=f"classificacao_manual_{idx}",
        )
        draft["categoria"] = selected

    st.dataframe(
        [
            {
                "arquivo": d.get("arquivo"),
                "tipo_documento": d.get("tipo_documento"),
                "categoria": d.get("categoria"),
                "cnpj_emitente": d.get("cnpj_emitente"),
                "cnpj_destinatario": d.get("cnpj_destinatario"),
            }
            for d in drafts
        ],
        use_container_width=True,
        hide_index=True,
    )

    col_sync, col_finish = st.columns(2)
    with col_sync:
        if st.button("Sincronizar Cadastros"):
            try:
                resumo_sync = _sync_terceiros_produtos(cliente_empresa_id, drafts)
                st.success("Sincronizacao de cadastros concluida.")
                st.write(f"Clientes criados: {resumo_sync.get('clientes_criados', 0)}")
                st.write(f"Fornecedores criados: {resumo_sync.get('fornecedores_criados', 0)}")
                st.write(f"Produtos sincronizados: {resumo_sync.get('produtos_sincronizados', 0)}")
            except Exception as exc:
                st.error(f"Falha na sincronizacao de cadastros: {exc}")

    with col_finish:
        if st.button("Finalizar Importacao", type="primary"):
            try:
                counters = _finalizar_importacao(cliente_empresa_id, drafts)
                st.session_state["importacao_counters"] = counters
                st.success("Importacao finalizada com sucesso.")
                st.session_state["importacao_drafts"] = []
            except Exception as exc:
                st.error(f"Falha ao finalizar importacao: {exc}")

    st.markdown("### Dashboard de Feedback do Ultimo Lote")
    _render_badges(st.session_state.get("importacao_counters", {}))

    counters = st.session_state.get("importacao_counters", {})
    st.write(f"Nao identificado: {int(counters.get('NAO_IDENTIFICADO', 0))}")
