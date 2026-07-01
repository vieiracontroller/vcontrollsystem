from __future__ import annotations

from datetime import date
from typing import Any

from fiscal.apuracoes.base import ApuracaoResultado, ApuracaoTributoBase, DocumentoFiscal


class IcmsApuracaoPlugin(ApuracaoTributoBase):
    """Apuracao de ICMS com base na LC 87/1996 (Lei Kandir) e regulamentos estaduais."""

    codigo = "icms"
    nome = "ICMS"
    base_legal = "LC 87/1996 (Lei Kandir) e regulamentos estaduais de ICMS."

    def validar_legislacao(self, periodo_inicio: date, periodo_fim: date) -> list[str]:
        warnings: list[str] = []
        if periodo_inicio > periodo_fim:
            warnings.append("Periodo invalido para apuracao de ICMS.")
        return warnings

    def calcular(
        self,
        documentos: list[DocumentoFiscal],
        periodo_inicio: date,
        periodo_fim: date,
        contexto: dict[str, Any] | None = None,
    ) -> ApuracaoResultado:
        debito = sum(doc.valor_icms for doc in documentos if doc.operacao == "saida")
        credito = sum(doc.valor_icms for doc in documentos if doc.operacao == "entrada")
        saldo = max(debito - credito, 0.0)

        memoria = [
            {
                "etapa": "Debito ICMS (saidas)",
                "formula": "soma(vICMS das saidas)",
                "valor": debito,
            },
            {
                "etapa": "Credito ICMS (entradas)",
                "formula": "soma(vICMS das entradas)",
                "valor": credito,
            },
            {
                "etapa": "Saldo a recolher",
                "formula": "max(Debito - Credito, 0)",
                "valor": saldo,
            },
        ]

        return ApuracaoResultado(
            tributo=self.nome,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            valor_apurado=saldo,
            resumo={"debito": debito, "credito": credito, "saldo": saldo},
            memoria_calculo=memoria,
            base_legal=self.base_legal,
        )

    def gerar_memoria_calculo(self, resultado: ApuracaoResultado) -> list[dict[str, Any]]:
        return resultado.memoria_calculo
