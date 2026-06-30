from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import xml.etree.ElementTree as ET

from db import fetch_rows, upsert_rows
from utils.tributario_validators import validar_produto_fiscal

NFE_NAMESPACE = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


@dataclass
class XMLProdutoPayload:
    """Representa um XML de NF-e em memoria para processamento."""

    file_name: str
    content: bytes


def _find_text(node: ET.Element, path: str) -> str:
    """Busca texto em caminho XML com namespace e retorna string limpa."""
    found = node.find(path, NFE_NAMESPACE)
    return (found.text or "").strip() if found is not None else ""


def _to_float(value: str) -> float:
    """Converte valor monetario para float com fallback seguro."""
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _find_cliente_id_by_cnpj(cnpj: str) -> str | None:
    """Localiza cliente por CNPJ para vincular produtos ao cliente_id."""
    if not cnpj:
        return None

    rows = fetch_rows(
        table_name="clientes",
        columns="id,cnpj",
        eq_filters={"cnpj": cnpj},
        limit=1,
    )
    if not rows:
        return None
    return str(rows[0].get("id") or "")


def _parse_produtos_nfe(content: bytes, cliente_id: str) -> list[dict[str, object]]:
    """Extrai itens da NF-e e monta payload para tabela produtos."""
    tree = ET.parse(BytesIO(content))
    root = tree.getroot()

    produtos: list[dict[str, object]] = []
    for det in root.findall(".//nfe:det", NFE_NAMESPACE):
        prod = det.find("nfe:prod", NFE_NAMESPACE)
        if prod is None:
            continue

        icms_node = det.find(".//nfe:ICMS/*", NFE_NAMESPACE)
        aliquota_icms = _to_float(_find_text(icms_node, "nfe:pICMS")) if icms_node is not None else 0.0
        cst_icms = ""
        cbenef = ""
        if icms_node is not None:
            cst_icms = _find_text(icms_node, "nfe:CST") or _find_text(icms_node, "nfe:CSOSN")
            cbenef = _find_text(icms_node, "nfe:cBenef")

        codigo = _find_text(prod, "nfe:cProd")
        if not codigo:
            continue

        produtos.append(
            {
                "cliente_id": cliente_id,
                "codigo_interno": codigo,
                "descricao": _find_text(prod, "nfe:xProd"),
                "ncm": _find_text(prod, "nfe:NCM"),
                "cest": _find_text(prod, "nfe:CEST"),
                "unidade_medida": _find_text(prod, "nfe:uCom"),
                "cfop_padrao": _find_text(prod, "nfe:CFOP"),
                "cst_icms": cst_icms,
                "cclasstrib": _find_text(prod, "nfe:cClassTrib"),
                "beneficios_fiscais": [
                    item
                    for item in [_find_text(prod, "nfe:cBenef"), cbenef]
                    if item
                ],
                "aliquota_padrao_icms": aliquota_icms,
                "aliquota_ibs": 0.0,
                "aliquota_cbs": 0.0,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

    return produtos


def sincronizar_produtos_por_xml(xml_payloads: list[XMLProdutoPayload]) -> dict[str, object]:
    """
    Sincroniza produtos a partir de XMLs de NF-e usando upsert.

    Regras:
    - Vincula cliente pelo CNPJ do emitente da nota.
    - Realiza upsert por (cliente_id, codigo_interno).
    - Insere novos produtos e atualiza existentes em uma unica operacao.
    """
    produtos_upsert: list[dict[str, object]] = []
    avisos: list[str] = []
    invalidos: list[str] = []

    for payload in xml_payloads:
        try:
            root = ET.parse(BytesIO(payload.content)).getroot()
            cnpj_emitente = _find_text(root, ".//nfe:emit/nfe:CNPJ")
            cliente_id = _find_cliente_id_by_cnpj(cnpj_emitente)

            if not cliente_id:
                avisos.append(
                    f"{payload.file_name}: cliente nao encontrado para CNPJ {cnpj_emitente}."
                )
                continue

            produtos = _parse_produtos_nfe(payload.content, cliente_id=cliente_id)

            for produto in produtos:
                normalized, errors, warnings = validar_produto_fiscal(produto)
                for warning in warnings:
                    avisos.append(
                        f"{payload.file_name} / {produto.get('codigo_interno')}: {warning}"
                    )

                if errors:
                    invalidos.append(
                        f"{payload.file_name} / {produto.get('codigo_interno')}: "
                        + "; ".join(errors)
                    )
                    continue

                produtos_upsert.append(normalized)
        except Exception as exc:
            avisos.append(f"{payload.file_name}: erro no processamento ({exc}).")

    if not produtos_upsert:
        return {
            "status": "skipped",
            "processed": 0,
            "warnings": avisos,
            "invalid": invalidos,
            "detail": "Nenhum produto elegivel para sincronizacao.",
        }

    result = upsert_rows(
        table_name="produtos",
        rows=produtos_upsert,
        on_conflict="cliente_id,codigo_interno",
    )

    result["warnings"] = avisos
    result["invalid"] = invalidos
    return result
