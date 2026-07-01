from __future__ import annotations

from datetime import date
from typing import Any

from fiscal.apuracoes.base import ApuracaoResultado, ApuracaoTributoBase, DocumentoFiscal


class IrpjCsllApuracaoPlugin(ApuracaoTributoBase):
    """Apuracao de IRPJ/CSLL com base no Decreto 9.580/2018 (RIR) e Lei 7.689/1988."""

    codigo = "irpj_csll"
    nome = "IRPJ/CSLL"
    base_legal = "Decreto 9.580/2018 (RIR), Lei 7.689/1988 e Lei 9.249/1995."

    def validar_legislacao(self, periodo_inicio: date, periodo_fim: date) -> list[str]:
        warnings: list[str] = []
        if periodo_inicio > periodo_fim:
            warnings.append("Periodo invalido para apuracao de IRPJ/CSLL.")
        return warnings

    def calcular(
        self,
        documentos: list[DocumentoFiscal],
        periodo_inicio: date,
        periodo_fim: date,
        contexto: dict[str, Any] | None = None,
    ) -> ApuracaoResultado:
        ctx = contexto or {}
        base_receita = sum(doc.valor_total for doc in documentos if doc.operacao == "saida")

        perc_presumido_ir = float(ctx.get("percentual_presumido_ir", 8.0)) / 100.0
        perc_presumido_csll = float(ctx.get("percentual_presumido_csll", 12.0)) / 100.0

        base_ir = base_receita * perc_presumido_ir
        base_csll = base_receita * perc_presumido_csll

        irpj = base_ir * 0.15
        csll = base_csll * 0.09

        meses_periodo = max(((periodo_fim.year - periodo_inicio.year) * 12) + (periodo_fim.month - periodo_inicio.month) + 1, 1)
        limite_adicional = 20000.0 * meses_periodo
        adicional_irpj = max(base_ir - limite_adicional, 0.0) * 0.10

        total = max(irpj + adicional_irpj + csll, 0.0)

        memoria = [
            {
                "etapa": "Base IRPJ",
                "formula": "Receita de saidas * percentual presumido IR",
                "valor": base_ir,
            },
            {
                "etapa": "Base CSLL",
                "formula": "Receita de saidas * percentual presumido CSLL",
                "valor": base_csll,
            },
            {
                "etapa": "IRPJ devido",
                "formula": "Base IRPJ * 15% + adicional de 10% sobre excedente legal",
                "valor": irpj + adicional_irpj,
            },
            {
                "etapa": "CSLL devida",
                "formula": "Base CSLL * 9%",
                "valor": csll,
            },
            {
                "etapa": "Total IRPJ/CSLL",
                "formula": "IRPJ + Adicional + CSLL",
                "valor": total,
            },
        ]

        return ApuracaoResultado(
            tributo=self.nome,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            valor_apurado=total,
            resumo={
                "base_receita": base_receita,
                "base_ir": base_ir,
                "base_csll": base_csll,
                "irpj": irpj,
                "adicional_irpj": adicional_irpj,
                "csll": csll,
                "total": total,
            },
            memoria_calculo=memoria,
            base_legal=self.base_legal,
        )

    def gerar_memoria_calculo(self, resultado: ApuracaoResultado) -> list[dict[str, Any]]:
        return resultado.memoria_calculo
