from __future__ import annotations

from datetime import date
from typing import Any

from fiscal.apuracoes.base import ApuracaoResultado, ApuracaoTributoBase, DocumentoFiscal


class IssApuracaoPlugin(ApuracaoTributoBase):
    """Apuracao de ISS com base na Lei Complementar 116/2003."""

    codigo = "iss"
    nome = "ISS"
    base_legal = "Lei Complementar 116/2003."

    def validar_legislacao(self, periodo_inicio: date, periodo_fim: date) -> list[str]:
        warnings: list[str] = []
        if periodo_inicio > periodo_fim:
            warnings.append("Periodo invalido para apuracao de ISS.")
        return warnings

    def calcular(
        self,
        documentos: list[DocumentoFiscal],
        periodo_inicio: date,
        periodo_fim: date,
        contexto: dict[str, Any] | None = None,
    ) -> ApuracaoResultado:
        saidas = [doc for doc in documentos if doc.operacao == "saida"]
        base = sum(doc.valor_total for doc in saidas)
        valor_xml = sum(doc.valor_iss for doc in saidas)

        aliquota_percent = float((contexto or {}).get("aliquota_iss_percent", 5.0))
        aliquota_decimal = aliquota_percent / 100.0
        valor_teorico = base * aliquota_decimal
        valor_final = valor_xml if valor_xml > 0 else valor_teorico

        memoria = [
            {
                "etapa": "Base de calculo ISS",
                "formula": "soma(vNF das saidas)",
                "valor": base,
            },
            {
                "etapa": "Aliquota aplicada",
                "formula": "parametro municipal (%)",
                "valor": aliquota_percent,
            },
            {
                "etapa": "Valor apurado",
                "formula": "usa vISS do XML quando disponivel; senao base * aliquota",
                "valor": valor_final,
            },
        ]

        return ApuracaoResultado(
            tributo=self.nome,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            valor_apurado=max(valor_final, 0.0),
            resumo={
                "base_calculo": base,
                "valor_xml": valor_xml,
                "valor_teorico": valor_teorico,
                "valor_final": max(valor_final, 0.0),
            },
            memoria_calculo=memoria,
            base_legal=self.base_legal,
        )

    def gerar_memoria_calculo(self, resultado: ApuracaoResultado) -> list[dict[str, Any]]:
        return resultado.memoria_calculo
