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
        notas_complementares = [doc for doc in documentos if doc.is_complementar]
        notas_st = [
            doc for doc in documentos if (doc.tem_icms_st and (not doc.is_complementar))
        ]
        notas_difal = [
            doc for doc in documentos if (doc.tem_icms_difal and (not doc.is_complementar))
        ]
        notas_normais = [
            doc
            for doc in documentos
            if (not doc.is_complementar) and (not doc.tem_icms_st) and (not doc.tem_icms_difal)
        ]

        debito_normal = sum(
            doc.valor_icms for doc in notas_normais if doc.operacao == "saida"
        )
        credito_normal = sum(
            doc.valor_icms for doc in notas_normais if doc.operacao == "entrada"
        )
        saldo_normal = max(debito_normal - credito_normal, 0.0)

        icms_st = sum(doc.valor_icms_st for doc in notas_st if doc.operacao == "saida")
        icms_difal = sum(
            doc.valor_icms_difal_destino
            for doc in notas_difal
            if doc.operacao == "saida"
        )
        icms_complementar = sum(
            doc.valor_icms_complementar
            for doc in notas_complementares
            if doc.operacao == "saida"
        )

        detalhes_conferencia = [
            {
                "arquivo": doc.arquivo,
                "operacao": doc.operacao,
                "tipo_icms": self._classificar_tipo_icms(doc),
                "icms_normal": doc.valor_icms,
                "icms_st": doc.valor_icms_st,
                "icms_difal_destino": doc.valor_icms_difal_destino,
                "icms_difal_origem": doc.valor_icms_difal_origem,
                "icms_complementar": doc.valor_icms_complementar,
            }
            for doc in documentos
        ]

        saldo_total = saldo_normal + icms_st + icms_difal + icms_complementar

        memoria = [
            {
                "etapa": "ICMS Normal - Debito",
                "formula": "soma(vICMS das notas normais de saida)",
                "valor": debito_normal,
            },
            {
                "etapa": "ICMS Normal - Credito",
                "formula": "soma(vICMS das notas normais de entrada)",
                "valor": credito_normal,
            },
            {
                "etapa": "ICMS Normal - Saldo",
                "formula": "max(Debito normal - Credito normal, 0)",
                "valor": saldo_normal,
            },
            {
                "etapa": "ICMS ST",
                "formula": "soma(vST das notas identificadas como ST)",
                "valor": icms_st,
            },
            {
                "etapa": "ICMS DIFAL",
                "formula": "soma(vICMSUFDest das notas com partilha DIFAL)",
                "valor": icms_difal,
            },
            {
                "etapa": "ICMS Complementar",
                "formula": "soma(vICMS das notas complementares)",
                "valor": icms_complementar,
            },
            {
                "etapa": "Total ICMS a recolher",
                "formula": "Saldo normal + ST + DIFAL + Complementar",
                "valor": saldo_total,
            },
        ]

        return ApuracaoResultado(
            tributo=self.nome,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            valor_apurado=saldo_total,
            resumo={
                "qtd_notas_normais": len(notas_normais),
                "qtd_notas_st": len(notas_st),
                "qtd_notas_difal": len(notas_difal),
                "qtd_notas_complementares": len(notas_complementares),
                "debito_normal": debito_normal,
                "credito_normal": credito_normal,
                "saldo_normal": saldo_normal,
                "icms_st": icms_st,
                "icms_difal": icms_difal,
                "icms_complementar": icms_complementar,
                "total_icms_recolher": saldo_total,
            },
            memoria_calculo=memoria,
            base_legal=self.base_legal,
            detalhes_conferencia=detalhes_conferencia,
        )

    def gerar_memoria_calculo(self, resultado: ApuracaoResultado) -> list[dict[str, Any]]:
        return resultado.memoria_calculo

    def _classificar_tipo_icms(self, doc: DocumentoFiscal) -> str:
        if doc.is_complementar:
            return "ICMS Complementar"

        tipos: list[str] = []
        if doc.tem_icms_st:
            tipos.append("ICMS ST")
        if doc.tem_icms_difal:
            tipos.append("ICMS DIFAL")

        if not tipos:
            return "ICMS Normal"

        return " + ".join(tipos)
