from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass
class NotaFiscalICMSInput:
    """Payload de entrada do motor de ICMS, desacoplado da interface."""

    cnpj_empresa: str
    uf_empresa: str | None
    uf_destinatario: str
    base_calculo: float
    aplicar_st: bool = False
    mva_percentual: float | None = None
    aplicar_difal: bool = True
    aplicar_complementacao: bool = False
    valor_operacao_final: float | None = None


@dataclass
class ApuracaoICMSResult:
    """Resultado consolidado da apuracao de ICMS para uma nota."""

    uf_empresa: str
    uf_destinatario: str
    regra_aplicada: str
    aliquota_propria: float
    aliquota_interna_destino: float
    base_calculo: float
    icms_proprio: float
    icms_st: float
    icms_difal: float
    icms_complementacao: float
    icms_total: float


def _normalize_uf(value: str | None) -> str:
    """Normaliza UF em formato de duas letras."""
    return (value or "").strip().upper()


def _load_regras() -> dict[str, Any]:
    """Carrega regras de ICMS de arquivo JSON versionado no projeto."""
    rules_path = Path(__file__).with_name("icms_regras.json")
    with rules_path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def identificar_uf_empresa(cnpj_empresa: str, uf_cadastrada: str | None) -> str:
    """
    Identifica a UF da empresa.

    Prioridade:
    1) UF cadastrada no cliente (endereco/parametro).
    2) Mapeamento explicito de CNPJ no arquivo de regras (cnpj_uf_map).
    """
    uf = _normalize_uf(uf_cadastrada)
    if uf:
        return uf

    regras = _load_regras()
    cnpj_map = regras.get("cnpj_uf_map", {})
    uf_from_map = _normalize_uf(cnpj_map.get(cnpj_empresa, ""))
    if uf_from_map:
        return uf_from_map

    raise ValueError(
        "Nao foi possivel identificar a UF da empresa. "
        "Informe a UF no cadastro do cliente ou em cnpj_uf_map."
    )


def _aliquota_interna(uf: str, regras: dict[str, Any]) -> float:
    """Retorna aliquota interna percentual da UF informada."""
    internas = regras.get("aliquotas_internas", {})
    if uf not in internas:
        raise ValueError(f"Nao ha aliquota interna configurada para UF {uf}.")
    return float(internas[uf])


def _aliquota_interestadual(uf_origem: str, uf_destino: str, regras: dict[str, Any]) -> float:
    """Define aliquota interestadual usando regra padrao simplificada 7/12."""
    interstate = regras.get("interestadual", {})
    sul_sudeste = set(interstate.get("uf_sul_sudeste", []))
    nnco = set(interstate.get("uf_norte_nordeste_co", []))

    if uf_origem in sul_sudeste and uf_destino in nnco:
        return float(interstate.get("origem_sul_sudeste_para_norte_nordeste_co", 7.0))

    return float(interstate.get("padrao", 12.0))


def _percent_to_decimal(value: float) -> float:
    """Converte percentual para decimal (18 -> 0.18)."""
    return float(value) / 100.0


def calcular_icms_nota(payload: NotaFiscalICMSInput) -> ApuracaoICMSResult:
    """
    Calcula ICMS proprio, ST, DIFAL e complementacao para uma nota.

    Regra de localidade obrigatoria:
    - Se UF_Destinatario == UF_Empresa: operacao interna.
    - Se diferente: operacao interestadual.
    """
    if payload.base_calculo < 0:
        raise ValueError("Base de calculo nao pode ser negativa.")

    regras = _load_regras()
    uf_empresa = identificar_uf_empresa(payload.cnpj_empresa, payload.uf_empresa)
    uf_dest = _normalize_uf(payload.uf_destinatario)

    if not uf_dest:
        raise ValueError("UF do destinatario e obrigatoria para apuracao de ICMS.")

    interna_dest = _aliquota_interna(uf_dest, regras)

    if uf_dest == uf_empresa:
        regra = "interna"
        aliquota_percentual = interna_dest
    else:
        regra = "interestadual"
        aliquota_percentual = _aliquota_interestadual(uf_empresa, uf_dest, regras)

    base = float(payload.base_calculo)
    aliquota_decimal = _percent_to_decimal(aliquota_percentual)
    interna_dest_decimal = _percent_to_decimal(interna_dest)

    icms_proprio = base * aliquota_decimal

    icms_difal = 0.0
    if regra == "interestadual" and payload.aplicar_difal:
        difal_rate = max(interna_dest_decimal - aliquota_decimal, 0.0)
        icms_difal = base * difal_rate

    icms_st = 0.0
    if payload.aplicar_st:
        mva = (
            float(payload.mva_percentual)
            if payload.mva_percentual is not None
            else float(regras.get("mva_st_padrao", 0.0))
        )
        if mva < 0:
            raise ValueError("MVA nao pode ser negativa.")
        base_st = base * (1.0 + _percent_to_decimal(mva))
        icms_st_teorico = base_st * interna_dest_decimal
        icms_st = max(icms_st_teorico - icms_proprio, 0.0)

    icms_complementacao = 0.0
    if payload.aplicar_complementacao:
        if payload.valor_operacao_final is None:
            raise ValueError("Informe valor_operacao_final para calcular complementacao.")
        if payload.valor_operacao_final < 0:
            raise ValueError("valor_operacao_final nao pode ser negativo.")

        valor_final = float(payload.valor_operacao_final)
        if valor_final > base:
            icms_complementacao = (valor_final - base) * interna_dest_decimal

    total = icms_proprio + icms_st + icms_difal + icms_complementacao

    return ApuracaoICMSResult(
        uf_empresa=uf_empresa,
        uf_destinatario=uf_dest,
        regra_aplicada=regra,
        aliquota_propria=aliquota_percentual,
        aliquota_interna_destino=interna_dest,
        base_calculo=base,
        icms_proprio=icms_proprio,
        icms_st=icms_st,
        icms_difal=icms_difal,
        icms_complementacao=icms_complementacao,
        icms_total=total,
    )


def apurar_icms_dict(payload: NotaFiscalICMSInput) -> dict[str, Any]:
    """Wrapper para serializacao simples (dict), util para UI e APIs."""
    return asdict(calcular_icms_nota(payload))
