from __future__ import annotations

from typing import Any

# Estrutura base de faixas do Simples Nacional por anexo.
# Aliquota informada em formato decimal (ex.: 0.06 = 6%).
ANEXOS_SIMPLES: dict[str, list[dict[str, Any]]] = {
    "I": [
        {"limite": 180000.00, "aliquota": 0.04, "deducao": 0.00},
        {"limite": 360000.00, "aliquota": 0.073, "deducao": 5940.00},
        {"limite": 720000.00, "aliquota": 0.095, "deducao": 13860.00},
        {"limite": 1800000.00, "aliquota": 0.107, "deducao": 22500.00},
        {"limite": 3600000.00, "aliquota": 0.143, "deducao": 87300.00},
        {"limite": 4800000.00, "aliquota": 0.19, "deducao": 378000.00},
    ],
    "II": [
        {"limite": 180000.00, "aliquota": 0.045, "deducao": 0.00},
        {"limite": 360000.00, "aliquota": 0.078, "deducao": 5940.00},
        {"limite": 720000.00, "aliquota": 0.10, "deducao": 13860.00},
        {"limite": 1800000.00, "aliquota": 0.112, "deducao": 22500.00},
        {"limite": 3600000.00, "aliquota": 0.147, "deducao": 85500.00},
        {"limite": 4800000.00, "aliquota": 0.30, "deducao": 720000.00},
    ],
    "III": [
        {"limite": 180000.00, "aliquota": 0.06, "deducao": 0.00},
        {"limite": 360000.00, "aliquota": 0.112, "deducao": 9360.00},
        {"limite": 720000.00, "aliquota": 0.135, "deducao": 17640.00},
        {"limite": 1800000.00, "aliquota": 0.16, "deducao": 35640.00},
        {"limite": 3600000.00, "aliquota": 0.21, "deducao": 125640.00},
        {"limite": 4800000.00, "aliquota": 0.33, "deducao": 648000.00},
    ],
    "IV": [
        {"limite": 180000.00, "aliquota": 0.045, "deducao": 0.00},
        {"limite": 360000.00, "aliquota": 0.09, "deducao": 8100.00},
        {"limite": 720000.00, "aliquota": 0.102, "deducao": 12420.00},
        {"limite": 1800000.00, "aliquota": 0.14, "deducao": 39780.00},
        {"limite": 3600000.00, "aliquota": 0.22, "deducao": 183780.00},
        {"limite": 4800000.00, "aliquota": 0.33, "deducao": 828000.00},
    ],
    "V": [
        {"limite": 180000.00, "aliquota": 0.155, "deducao": 0.00},
        {"limite": 360000.00, "aliquota": 0.18, "deducao": 4500.00},
        {"limite": 720000.00, "aliquota": 0.195, "deducao": 9900.00},
        {"limite": 1800000.00, "aliquota": 0.205, "deducao": 17100.00},
        {"limite": 3600000.00, "aliquota": 0.23, "deducao": 62100.00},
        {"limite": 4800000.00, "aliquota": 0.305, "deducao": 540000.00},
    ],
}


def obter_faixa_anexo(anexo: str, receita_bruta_12m: float) -> dict[str, Any] | None:
    """Retorna a faixa aplicavel para o anexo informado, baseado na receita dos ultimos 12 meses."""
    anexos = ANEXOS_SIMPLES.get(anexo.upper())
    if not anexos:
        return None

    for faixa in anexos:
        if receita_bruta_12m <= float(faixa["limite"]):
            return faixa

    return None
