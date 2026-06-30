from __future__ import annotations

from datetime import datetime
from io import BytesIO
import xml.etree.ElementTree as ET


NFE_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _text(node: ET.Element, path: str) -> str:
    """Retorna texto de um caminho XML com namespace NF-e."""
    found = node.find(path, NFE_NS)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _to_float(value: str) -> float:
    """Converte string numerica de XML para float, com fallback seguro."""
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0


def map_xml_to_sped_records(xml_file: BytesIO, file_name: str = "") -> dict[str, object]:
    """Mapeia XML NF-e para estrutura de registros SPED C100/C170."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    nfe_id = _text(root, ".//nfe:infNFe")
    chv_nfe = ""
    if nfe_id.startswith("NFe"):
        chv_nfe = nfe_id[3:]

    c100 = {
        "REG": "C100",
        "IND_OPER": "0",
        "IND_EMIT": "1",
        "COD_PART": _text(root, ".//nfe:dest/nfe:CNPJ") or _text(root, ".//nfe:dest/nfe:CPF"),
        "COD_MOD": _text(root, ".//nfe:ide/nfe:mod") or "55",
        "COD_SIT": "00",
        "SER": _text(root, ".//nfe:ide/nfe:serie"),
        "NUM_DOC": _text(root, ".//nfe:ide/nfe:nNF"),
        "CHV_NFE": chv_nfe,
        "DT_DOC": _text(root, ".//nfe:ide/nfe:dhEmi")[:10].replace("-", ""),
        "VL_DOC": _to_float(_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF")),
        "VL_ICMS": _to_float(_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vICMS")),
        "VL_BC_ICMS": _to_float(_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vBC")),
        "UF_DEST": _text(root, ".//nfe:dest/nfe:enderDest/nfe:UF"),
        "ORIGEM_ARQUIVO": file_name,
    }

    c170: list[dict[str, object]] = []
    det_nodes = root.findall(".//nfe:det", NFE_NS)
    for det in det_nodes:
        prod = det.find("nfe:prod", NFE_NS)
        icms = det.find(".//nfe:ICMS/*", NFE_NS)

        c170.append(
            {
                "REG": "C170",
                "NUM_ITEM": det.attrib.get("nItem", ""),
                "COD_ITEM": _text(prod, "nfe:cProd") if prod is not None else "",
                "DESCR_COMPL": _text(prod, "nfe:xProd") if prod is not None else "",
                "QTD": _to_float(_text(prod, "nfe:qCom") if prod is not None else "0"),
                "UNID": _text(prod, "nfe:uCom") if prod is not None else "",
                "VL_ITEM": _to_float(_text(prod, "nfe:vProd") if prod is not None else "0"),
                "CST_ICMS": _text(icms, "nfe:CST") if icms is not None else "",
                "CFOP": _text(prod, "nfe:CFOP") if prod is not None else "",
                "ALIQ_ICMS": _to_float(_text(icms, "nfe:pICMS") if icms is not None else "0"),
                "VL_BC_ICMS": _to_float(_text(icms, "nfe:vBC") if icms is not None else "0"),
                "VL_ICMS": _to_float(_text(icms, "nfe:vICMS") if icms is not None else "0"),
            }
        )

    return {
        "meta": {
            "arquivo": file_name,
            "gerado_em": datetime.utcnow().isoformat(),
        },
        "C100": c100,
        "C170": c170,
    }


def render_sped_txt(records: list[dict[str, object]], mes: int, ano: int) -> str:
    """Monta texto EFD simplificado com blocos C100 e C170."""
    lines: list[str] = []

    lines.append(f"|0000|LECD|010120{ano}|3112{ano}|VCONTROLL|")
    lines.append(f"|0001|0|")
    lines.append(f"|C001|0|{mes:02d}{ano}|")

    for nota in records:
        c100 = nota["C100"]
        c170 = nota["C170"]

        lines.append(
            "|C100|{IND_OPER}|{IND_EMIT}|{COD_PART}|{COD_MOD}|{COD_SIT}|{SER}|{NUM_DOC}|{CHV_NFE}|{DT_DOC}|{VL_DOC:.2f}|{VL_BC_ICMS:.2f}|{VL_ICMS:.2f}|".format(
                **c100
            )
        )

        for item in c170:
            lines.append(
                "|C170|{NUM_ITEM}|{COD_ITEM}|{DESCR_COMPL}|{QTD:.4f}|{UNID}|{VL_ITEM:.2f}|{CST_ICMS}|{CFOP}|{VL_BC_ICMS:.2f}|{ALIQ_ICMS:.2f}|{VL_ICMS:.2f}|".format(
                    **item
                )
            )

    lines.append("|C990|{}|".format(len(lines) + 1))
    lines.append("|9990|1|")
    lines.append("|9999|{}|".format(len(lines) + 1))
    return "\n".join(lines) + "\n"
