from __future__ import annotations


def beneficios_sugeridos_por_ncm(ncm: str) -> list[str]:
    """
    Retorna codigos de beneficios fiscais sugeridos por prefixo de NCM.

    Observacao: esta matriz e inicial e deve ser refinada por UF/segmento.
    """
    ncm_digits = "".join(ch for ch in (ncm or "") if ch.isdigit())

    regras_prefixo: dict[str, list[str]] = {
        "0401": ["RED_BASE_AGRO", "CRED_PRESUMIDO_LACTEOS"],
        "1006": ["ISENCAO_CESTA_BASICA", "RED_BASE_ARROZ"],
        "2203": ["MONOFASICO_BEBIDAS", "ST_BEBIDAS"],
        "2710": ["MONOFASICO_COMBUSTIVEIS", "CIDE_COMBUSTIVEIS"],
        "3004": ["ISENCAO_FARMACIA_POPULAR", "RED_BASE_MEDICAMENTOS"],
        "8471": ["EX_TARIFARIO_TI", "CREDITO_OUTORGADO_TI"],
        "8703": ["RED_BASE_AUTOPECAS", "ST_VEICULOS"],
    }

    sugestoes: list[str] = []
    for prefixo, beneficios in regras_prefixo.items():
        if ncm_digits.startswith(prefixo):
            sugestoes.extend(beneficios)

    # Remove duplicados preservando ordem.
    vistos: set[str] = set()
    ordenado: list[str] = []
    for item in sugestoes:
        if item not in vistos:
            vistos.add(item)
            ordenado.append(item)

    return ordenado
