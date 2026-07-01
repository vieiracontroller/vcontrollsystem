from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from typing import Any
import xml.etree.ElementTree as ET

NFE_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


@dataclass(frozen=True)
class DocumentoFiscal:
    """Representa os valores principais extraidos de um XML NF-e."""

    arquivo: str
    data_emissao: date | None
    operacao: str
    valor_total: float
    base_icms: float
    valor_icms: float
    valor_icms_st: float
    valor_icms_difal_destino: float
    valor_icms_difal_origem: float
    valor_icms_complementar: float
    tem_icms_st: bool
    tem_icms_difal: bool
    is_complementar: bool
    valor_ipi: float
    valor_pis: float
    valor_cofins: float
    valor_iss: float
    valor_ir: float
    valor_csll: float


@dataclass(frozen=True)
class ApuracaoResultado:
    """Resultado padrao para qualquer plugin de apuracao."""

    tributo: str
    periodo_inicio: date
    periodo_fim: date
    valor_apurado: float
    resumo: dict[str, float | int]
    memoria_calculo: list[dict[str, Any]]
    base_legal: str
    detalhes_conferencia: list[dict[str, Any]] = field(default_factory=list)


class ApuracaoTributoBase(ABC):
    """Contrato base para plugins de tributos."""

    codigo: str = "base"
    nome: str = "Base"
    base_legal: str = "Base legal nao informada."

    @abstractmethod
    def validar_legislacao(self, periodo_inicio: date, periodo_fim: date) -> list[str]:
        """Valida regras legais minimas para o periodo solicitado."""

    @abstractmethod
    def calcular(
        self,
        documentos: list[DocumentoFiscal],
        periodo_inicio: date,
        periodo_fim: date,
        contexto: dict[str, Any] | None = None,
    ) -> ApuracaoResultado:
        """Executa apuracao tributaria no periodo e retorna resultado consolidado."""

    @abstractmethod
    def gerar_memoria_calculo(self, resultado: ApuracaoResultado) -> list[dict[str, Any]]:
        """Retorna memoria de calculo detalhada para conferencia tecnica."""


def parse_documentos_fiscais(xml_files: list[tuple[str, bytes]]) -> list[DocumentoFiscal]:
    """Converte arquivos XML NF-e em documentos padronizados para os plugins."""
    docs: list[DocumentoFiscal] = []

    for file_name, content in xml_files:
        root = ET.parse(BytesIO(content)).getroot()

        data_emissao = _parse_date(_find_text(root, ".//nfe:ide/nfe:dhEmi"))
        operacao = _resolve_operacao(_find_text(root, ".//nfe:ide/nfe:tpNF"))
        finalidade_nfe = _find_text(root, ".//nfe:ide/nfe:finNFe")
        info_adicional = " ".join(
            [
                _find_text(root, ".//nfe:infAdic/nfe:infAdFisco"),
                _find_text(root, ".//nfe:infAdic/nfe:infCpl"),
            ]
        ).strip()

        valor_icms = _to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vICMS"))
        valor_icms_st = _to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vST"))
        valor_icms_difal_destino = _to_float(
            _find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vICMSUFDest")
        )
        valor_icms_difal_origem = _to_float(
            _find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vICMSUFRemet")
        )

        is_complementar = _is_nota_complementar(finalidade_nfe, info_adicional)
        tem_icms_st = valor_icms_st > 0
        tem_icms_difal = (valor_icms_difal_destino > 0) or (valor_icms_difal_origem > 0)
        valor_icms_complementar = valor_icms if is_complementar else 0.0

        docs.append(
            DocumentoFiscal(
                arquivo=file_name,
                data_emissao=data_emissao,
                operacao=operacao,
                valor_total=_to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF")),
                base_icms=_to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vBC")),
                valor_icms=valor_icms,
                valor_icms_st=valor_icms_st,
                valor_icms_difal_destino=valor_icms_difal_destino,
                valor_icms_difal_origem=valor_icms_difal_origem,
                valor_icms_complementar=valor_icms_complementar,
                tem_icms_st=tem_icms_st,
                tem_icms_difal=tem_icms_difal,
                is_complementar=is_complementar,
                valor_ipi=_to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vIPI")),
                valor_pis=_to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vPIS")),
                valor_cofins=_to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vCOFINS")),
                valor_iss=_to_float(_find_text(root, ".//nfe:total/nfe:ISSQNtot/nfe:vISS")),
                valor_ir=_to_float(_find_text(root, ".//nfe:total/nfe:retTrib/nfe:vIR")),
                valor_csll=_to_float(_find_text(root, ".//nfe:total/nfe:retTrib/nfe:vCSLL")),
            )
        )

    return docs


def filtrar_documentos_periodo(
    documentos: list[DocumentoFiscal],
    periodo_inicio: date,
    periodo_fim: date,
) -> list[DocumentoFiscal]:
    """Filtra documentos por data de emissao no intervalo informado."""
    filtered: list[DocumentoFiscal] = []
    for doc in documentos:
        if doc.data_emissao is None:
            continue
        if periodo_inicio <= doc.data_emissao <= periodo_fim:
            filtered.append(doc)
    return filtered


def _resolve_operacao(tp_nf: str) -> str:
    return "entrada" if tp_nf.strip() == "0" else "saida"


def _find_text(node: ET.Element, path: str) -> str:
    found = node.find(path, NFE_NS)
    return (found.text or "").strip() if found is not None else ""


def _to_float(value: str) -> float:
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _parse_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None

    iso_part = text[:10]
    try:
        return datetime.strptime(iso_part, "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_nota_complementar(finalidade_nfe: str, info_adicional: str) -> bool:
    if finalidade_nfe.strip() == "2":
        return True

    text = (info_adicional or "").strip().lower()
    if not text:
        return False

    return ("complement" in text) or ("complementa" in text)
