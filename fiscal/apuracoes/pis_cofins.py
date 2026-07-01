from __future__ import annotations

from datetime import date
from typing import Any

from fiscal.apuracoes.base import ApuracaoResultado, ApuracaoTributoBase, DocumentoFiscal


class PisCofinsApuracaoPlugin(ApuracaoTributoBase):
    """Apuracao de PIS/COFINS conforme Leis 10.637/2002 e 10.833/2003."""

    codigo = "pis_cofins"
    nome = "PIS/COFINS"
    base_legal = "Leis 10.637/2002 e 10.833/2003."

    def validar_legislacao(self, periodo_inicio: date, periodo_fim: date) -> list[str]:
        warnings: list[str] = []
        if periodo_inicio > periodo_fim:
            warnings.append("Periodo invalido para apuracao de PIS/COFINS.")
        return warnings

    def calcular(
        self,
        documentos: list[DocumentoFiscal],
        periodo_inicio: date,
        periodo_fim: date,
        contexto: dict[str, Any] | None = None,
    ) -> ApuracaoResultado:
        debito_pis = sum(doc.valor_pis for doc in documentos if doc.operacao == "saida")
        credito_pis = sum(doc.valor_pis for doc in documentos if doc.operacao == "entrada")
        debito_cofins = sum(doc.valor_cofins for doc in documentos if doc.operacao == "saida")
        credito_cofins = sum(doc.valor_cofins for doc in documentos if doc.operacao == "entrada")

        saldo_pis = max(debito_pis - credito_pis, 0.0)
        saldo_cofins = max(debito_cofins - credito_cofins, 0.0)
        saldo_total = saldo_pis + saldo_cofins

        memoria = [
            {
                "etapa": "PIS devido",
                "formula": "max(sum(PIS saidas) - sum(PIS entradas), 0)",
                "valor": saldo_pis,
            },
            {
                "etapa": "COFINS devida",
                "formula": "max(sum(COFINS saidas) - sum(COFINS entradas), 0)",
                "valor": saldo_cofins,
            },
            {
                "etapa": "Total PIS/COFINS",
                "formula": "PIS devido + COFINS devida",
                "valor": saldo_total,
            },
        ]

        return ApuracaoResultado(
            tributo=self.nome,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            valor_apurado=saldo_total,
            resumo={
                "debito_pis": debito_pis,
                "credito_pis": credito_pis,
                "saldo_pis": saldo_pis,
                "debito_cofins": debito_cofins,
                "credito_cofins": credito_cofins,
                "saldo_cofins": saldo_cofins,
                "saldo_total": saldo_total,
            },
            memoria_calculo=memoria,
            base_legal=self.base_legal,
        )

    def gerar_memoria_calculo(self, resultado: ApuracaoResultado) -> list[dict[str, Any]]:
        return resultado.memoria_calculo
