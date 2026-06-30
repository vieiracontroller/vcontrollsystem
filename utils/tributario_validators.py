from __future__ import annotations

import re
from typing import Any

from utils.beneficios_ncm import beneficios_sugeridos_por_ncm


def _digits(value: str) -> str:
    """Remove caracteres nao numericos para validacoes fiscais."""
    return re.sub(r"\D", "", value or "")


def _is_between(value: float, minimum: float, maximum: float) -> bool:
    """Valida limites inclusivos para percentuais monetarios."""
    return minimum <= value <= maximum


def validar_produto_fiscal(produto: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    """
    Valida e normaliza campos fiscais do produto para conformidade operacional.

    Escopo atual de conformidade:
    - NCM com 8 digitos.
    - CEST com 7 digitos quando informado.
    - CFOP com 4 digitos quando informado.
    - CST/CSOSN ICMS com 2 ou 3 digitos quando informado.
    - Aliquotas ICMS/IBS/CBS no intervalo de 0 a 100.
    - Alertas de transicao da reforma tributaria (IBS/CBS).
    """
    errors: list[str] = []
    warnings: list[str] = []

    codigo_interno = str(produto.get("codigo_interno") or "").strip()
    descricao = str(produto.get("descricao") or "").strip()
    ncm = _digits(str(produto.get("ncm") or ""))
    cest = _digits(str(produto.get("cest") or ""))
    cfop = _digits(str(produto.get("cfop_padrao") or ""))
    cst_icms = _digits(str(produto.get("cst_icms") or ""))
    cclasstrib = str(produto.get("cclasstrib") or "").strip().upper()
    beneficios_raw = produto.get("beneficios_fiscais") or []

    aliquota_icms = float(produto.get("aliquota_padrao_icms") or 0.0)
    aliquota_ibs = float(produto.get("aliquota_ibs") or 0.0)
    aliquota_cbs = float(produto.get("aliquota_cbs") or 0.0)

    beneficios: list[str]
    if isinstance(beneficios_raw, list):
        beneficios = [str(item).strip().upper() for item in beneficios_raw if str(item).strip()]
    else:
        beneficios = [
            item.strip().upper()
            for item in str(beneficios_raw).split(",")
            if item.strip()
        ]

    if not codigo_interno:
        errors.append("Codigo interno e obrigatorio.")

    if not descricao:
        errors.append("Descricao do produto e obrigatoria.")

    if not ncm or len(ncm) != 8:
        errors.append("NCM deve conter exatamente 8 digitos.")

    if cest and len(cest) != 7:
        errors.append("CEST deve conter 7 digitos quando informado.")

    if cfop and len(cfop) != 4:
        errors.append("CFOP deve conter 4 digitos quando informado.")

    if cst_icms and len(cst_icms) not in (2, 3):
        errors.append("CST/CSOSN ICMS deve conter 2 ou 3 digitos quando informado.")

    if cclasstrib and not re.fullmatch(r"[A-Z0-9]{2,10}", cclasstrib):
        errors.append("cClassTrib deve ter 2 a 10 caracteres alfanumericos.")

    for beneficio in beneficios:
        if not re.fullmatch(r"[A-Z0-9_\-]{2,40}", beneficio):
            errors.append(
                f"Beneficio fiscal invalido '{beneficio}'. Use apenas letras, numeros, '_' ou '-'."
            )

    if not _is_between(aliquota_icms, 0.0, 100.0):
        errors.append("Aliquota padrao de ICMS deve estar entre 0 e 100.")

    if not _is_between(aliquota_ibs, 0.0, 100.0):
        errors.append("Aliquota de IBS deve estar entre 0 e 100.")

    if not _is_between(aliquota_cbs, 0.0, 100.0):
        errors.append("Aliquota de CBS deve estar entre 0 e 100.")

    # Regra de transicao da reforma: campos IBS/CBS devem ser monitorados.
    if aliquota_ibs == 0.0 and aliquota_cbs == 0.0:
        warnings.append(
            "IBS/CBS em zero. Revise periodicamente os parametros da reforma tributaria."
        )

    if (aliquota_ibs > 0.0 or aliquota_cbs > 0.0) and not cfop:
        warnings.append("CFOP padrao nao informado para produto com IBS/CBS configurado.")

    sugestoes = beneficios_sugeridos_por_ncm(ncm)
    if sugestoes and not beneficios:
        warnings.append(
            "NCM com beneficios fiscais potenciais. Revise codigos sugeridos: "
            + ", ".join(sugestoes)
        )

    if sugestoes and beneficios:
        fora_da_sugestao = [b for b in beneficios if b not in sugestoes]
        if fora_da_sugestao:
            warnings.append(
                "Beneficios fora da matriz sugerida para este NCM: "
                + ", ".join(fora_da_sugestao)
            )

    normalized = {
        **produto,
        "codigo_interno": codigo_interno,
        "descricao": descricao,
        "ncm": ncm,
        "cest": cest,
        "cfop_padrao": cfop,
        "cst_icms": cst_icms,
        "cclasstrib": cclasstrib,
        "beneficios_fiscais": beneficios,
        "aliquota_padrao_icms": aliquota_icms,
        "aliquota_ibs": aliquota_ibs,
        "aliquota_cbs": aliquota_cbs,
    }

    return normalized, errors, warnings
