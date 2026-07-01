from __future__ import annotations

from datetime import date
from typing import Any

from fiscal.apuracoes.base import ApuracaoResultado, ApuracaoTributoBase, DocumentoFiscal


class IpiApuracaoPlugin(ApuracaoTributoBase):
    """Apuracao de IPI com base no Decreto 7.212/2010 (RIPI) e CTN."""

    codigo = "ipi"
    nome = "IPI"
    base_legal = "Decreto 7.212/2010 (RIPI) e CTN."

    def validar_legislacao(self, periodo_inicio: date, periodo_fim: date) -> list[str]:
        warnings: list[str] = []
        if periodo_inicio > periodo_fim:
            warnings.append("Periodo invalido para apuracao de IPI.")
        return warnings

    def calcular(
        self,
        documentos: list[DocumentoFiscal],
        periodo_inicio: date,
        periodo_fim: date,
        contexto: dict[str, Any] | None = None,
    ) -> ApuracaoResultado:
        debito = sum(doc.valor_ipi for doc in documentos if doc.operacao == "saida")
        credito = sum(doc.valor_ipi for doc in documentos if doc.operacao == "entrada")
        saldo = max(debito - credito, 0.0)

        memoria = [
            {
                "etapa": "Debito IPI (saidas)",
                "formula": "soma(vIPI das saidas)",
                "valor": debito,
            },
            {
                "etapa": "Credito IPI (entradas)",
                "formula": "soma(vIPI das entradas)",
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
