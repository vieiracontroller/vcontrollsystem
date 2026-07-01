from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from db import fetch_rows
from fiscal.apuracoes.base import ApuracaoTributoBase


@dataclass(frozen=True)
class RegimeApuracaoStrategy:
    """Strategia de apuracao por regime tributario da empresa."""

    nome: str
    tributos_habilitados: set[str]
    contexto_padrao: dict[str, Any]

    def permite(self, plugin: ApuracaoTributoBase) -> bool:
        return plugin.codigo in self.tributos_habilitados

    def aplicar_contexto(self, contexto: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.contexto_padrao)
        merged.update(contexto)
        return merged


def motor_simples_nacional() -> RegimeApuracaoStrategy:
    """Regras de apuracao para empresas no Simples Nacional (LC 123/2006)."""
    return RegimeApuracaoStrategy(
        nome="Simples Nacional",
        tributos_habilitados={"icms", "ipi", "iss", "pis_cofins", "irpj_csll"},
        contexto_padrao={
            "regime_apuracao": "simples_nacional",
            "percentual_presumido_ir": 0.0,
            "percentual_presumido_csll": 0.0,
        },
    )


def motor_lucro_presumido() -> RegimeApuracaoStrategy:
    """Regras de apuracao para empresas no Lucro Presumido."""
    return RegimeApuracaoStrategy(
        nome="Lucro Presumido",
        tributos_habilitados={"icms", "ipi", "pis_cofins", "iss", "irpj_csll"},
        contexto_padrao={
            "regime_apuracao": "lucro_presumido",
            "percentual_presumido_ir": 8.0,
            "percentual_presumido_csll": 12.0,
        },
    )


def motor_lucro_real() -> RegimeApuracaoStrategy:
    """Regras de apuracao para empresas no Lucro Real."""
    return RegimeApuracaoStrategy(
        nome="Lucro Real",
        tributos_habilitados={"icms", "ipi", "pis_cofins", "iss", "irpj_csll"},
        contexto_padrao={
            "regime_apuracao": "lucro_real",
            "percentual_presumido_ir": 0.0,
            "percentual_presumido_csll": 0.0,
        },
    )


def _normalizar_regime(regime: str) -> str:
    text = (regime or "").strip().lower()
    aliases = {
        "simples nacional": "simples nacional",
        "lucro presumido": "lucro presumido",
        "presumido": "lucro presumido",
        "lucro real": "lucro real",
        "real": "lucro real",
    }
    return aliases.get(text, text)


def selecionar_motor_apuracao(cliente_id: str) -> RegimeApuracaoStrategy:
    """
    Seleciona estrategia de apuracao com base no regime tributario do cliente.

    Fluxo:
    1) consulta regime_tributario na tabela clientes
    2) retorna estrategia especializada (pattern Strategy)
    """
    rows = fetch_rows(
        table_name="clientes",
        columns="id,regime_tributario",
        eq_filters={"id": cliente_id},
        limit=1,
    )

    if not rows:
        raise ValueError("Cliente nao encontrado para selecao do motor de apuracao.")

    regime = _normalizar_regime(str(rows[0].get("regime_tributario") or ""))

    if regime == "simples nacional":
        return motor_simples_nacional()
    if regime == "lucro presumido":
        return motor_lucro_presumido()
    if regime == "lucro real":
        return motor_lucro_real()

    raise ValueError("Regime tributario nao suportado para selecao do motor de apuracao.")
