from __future__ import annotations

from fiscal.config_anexos import obter_faixa_anexo


def _normalize_percent(value: float) -> float:
    """Normaliza percentual aceitando entrada em decimal (0.1) ou percentual (10)."""
    if value < 0:
        raise ValueError("Aliquota nao pode ser negativa.")
    return value / 100 if value > 1 else value


def calcular_das(
    receita_bruta: float,
    anexo: str,
    aliquota_efetiva: float | None,
    deducoes: float | None,
) -> dict[str, float | str]:
    """
    Calcula o valor do DAS do Simples Nacional para um anexo.

    Regras utilizadas:
    - Se aliquota_efetiva for informada: DAS = receita_bruta * aliquota_efetiva - deducoes.
    - Se aliquota_efetiva nao for informada: calcula aliquota efetiva com base na faixa do anexo:
      aliquota_efetiva = ((receita_bruta * aliquota_nominal) - deducao_faixa) / receita_bruta.
    """
    receita = float(receita_bruta)
    if receita < 0:
        raise ValueError("Receita bruta nao pode ser negativa.")

    if receita == 0:
        return {
            "anexo": anexo,
            "receita_bruta": 0.0,
            "aliquota_efetiva": 0.0,
            "deducao": 0.0,
            "valor_das": 0.0,
        }

    deducao_informada = float(deducoes or 0.0)
    deducao_aplicada = deducao_informada

    if aliquota_efetiva is None:
        faixa = obter_faixa_anexo(anexo=anexo, receita_bruta_12m=receita)
        if faixa is None:
            raise ValueError(f"Nao ha faixa configurada para o anexo {anexo}.")

        aliquota_nominal = float(faixa["aliquota"])
        deducao_faixa = float(faixa["deducao"])
        aliquota_efetiva_decimal = ((receita * aliquota_nominal) - deducao_faixa) / receita
        deducao_aplicada = deducao_faixa
    else:
        aliquota_efetiva_decimal = _normalize_percent(float(aliquota_efetiva))

    valor_das = max((receita * aliquota_efetiva_decimal) - deducao_aplicada, 0.0)

    return {
        "anexo": anexo.upper(),
        "receita_bruta": receita,
        "aliquota_efetiva": aliquota_efetiva_decimal,
        "deducao": deducao_aplicada,
        "valor_das": valor_das,
    }
