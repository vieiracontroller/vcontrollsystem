from __future__ import annotations

import base64
from datetime import date, datetime
from io import BytesIO
import json
from typing import Any
import xml.etree.ElementTree as ET

import streamlit as st

from db import fetch_rows, insert_rows
from fiscal.config_anexos import obter_faixa_anexo

NFE_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
CST_RECONHECIDOS = {"00", "10", "20", "30", "40", "41", "50", "51", "60", "70", "90"}
CSOSN_RECONHECIDOS = {"101", "102", "103", "201", "202", "203", "300", "400", "500", "900"}
ANEXOS = ["I", "II", "III", "IV", "V"]


def _to_float(value: str) -> float:
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    found = node.find(path, NFE_NS)
    return (found.text or "").strip() if found is not None else ""


def _parse_iso_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None

    if len(text) >= 10:
        text = text[:10]

    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _load_empresas() -> list[dict[str, Any]]:
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,regime_tributario,endereco",
        order_by="razao_social",
        desc=False,
    )


def _decode_xml_from_row(row: dict[str, Any]) -> bytes | None:
    if row.get("xml_base64"):
        try:
            return base64.b64decode(str(row.get("xml_base64")))
        except Exception:
            return None

    raw = row.get("xml_content") or row.get("xml")
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return None


def _load_notas_saida(cliente_id: str, inicio: date, fim: date) -> list[dict[str, Any]]:
    rows = fetch_rows(
        table_name="fiscal_nfe_xml_cache",
        columns="*",
        eq_filters={"cliente_id": cliente_id},
        order_by="data_emissao",
        desc=False,
        limit=5000,
    )

    notas: list[dict[str, Any]] = []
    for row in rows:
        dt = _parse_iso_date(str(row.get("data_emissao") or "")) or _parse_iso_date(
            str(row.get("criado_em") or "")
        )
        if dt is None:
            continue
        if not (inicio <= dt <= fim):
            continue

        tipo = str(row.get("tipo_operacao") or "").strip().lower()
        if tipo and tipo != "saida":
            continue

        notas.append(row)
    return notas


def _load_notas_ultimos_12_meses(cliente_id: str, referencia_fim: date) -> list[dict[str, Any]]:
    inicio_12m = date(referencia_fim.year - 1, referencia_fim.month, 1)
    return _load_notas_saida(cliente_id, inicio_12m, referencia_fim)


def _classificar_anexo_nota(root: ET.Element, fator_r: float) -> str:
    valor_iss = _to_float(_text(root, ".//nfe:total/nfe:ISSQNtot/nfe:vISS"))
    valor_ipi = _to_float(_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vIPI"))

    if valor_iss > 0:
        return "III" if fator_r >= 0.28 else "V"
    if valor_ipi > 0:
        return "II"
    return "I"


def _anexo_expander_ui(anexo: str, receita_bruta: float) -> dict[str, float]:
    with st.expander(f"Anexo {anexo}", expanded=(receita_bruta > 0)):
        st.metric("Receita Bruta (XML de saida)", f"R$ {receita_bruta:,.2f}")
        receita_st = st.number_input(
            "Receita com substituicao tributaria",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key=f"simples_st_{anexo}",
        )
        receita_monofasia = st.number_input(
            "Receita sujeita ao regime de monofasia",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key=f"simples_mono_{anexo}",
        )
        receita_exportacao = st.number_input(
            "Receita com exportacao",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key=f"simples_exp_{anexo}",
        )

    return {
        "receita_bruta": receita_bruta,
        "receita_st": receita_st,
        "receita_monofasia": receita_monofasia,
        "receita_exportacao": receita_exportacao,
    }


def _registrar_pendencia_classificacao(
    cliente_id: str,
    nota_id: str,
    arquivo: str,
    ncm: str,
    cst_csosn: str,
    motivo: str,
) -> None:
    row = {
        "cliente_id": cliente_id,
        "nota_id": nota_id,
        "arquivo": arquivo,
        "ncm": ncm,
        "cst_csosn": cst_csosn,
        "status": "Pendente de Classificacao Fiscal",
        "motivo": motivo,
        "created_at": datetime.utcnow().isoformat(),
    }
    insert_rows(table_name="pendencias_classificacao_fiscal", rows=[row])


def _aliquotas_por_ncm(ncm: str, uf_origem: str, uf_destino: str) -> tuple[float | None, float | None]:
    if not ncm:
        return None, None

    try:
        rows = fetch_rows(
            table_name="tabela_icms_2026",
            columns="*",
            eq_filters={"ncm": ncm},
            limit=50,
        )
    except Exception:
        return None, None

    if not rows:
        return None, None

    selected = rows[0]
    for row in rows:
        origem_ok = (str(row.get("uf_origem") or "").strip().upper() in {"", uf_origem})
        destino_ok = (str(row.get("uf_destino") or "").strip().upper() in {"", uf_destino})
        if origem_ok and destino_ok:
            selected = row
            break

    interna = float(selected.get("aliquota_interna_destino") or 0.0)
    interestadual = float(selected.get("aliquota_interestadual") or 0.0)

    if interna <= 0 and selected.get("aliquota_interna") is not None:
        interna = float(selected.get("aliquota_interna") or 0.0)

    if interestadual <= 0 and selected.get("aliquota_origem") is not None:
        interestadual = float(selected.get("aliquota_origem") or 0.0)

    if interna <= 0 or interestadual <= 0:
        return None, None
    return interna, interestadual


def calcular_base_icms(cliente_id: str, periodo: tuple[int, int]) -> dict[str, Any]:
    """
    Filtra XMLs de saida do periodo, soma vProd por regra CST/CSOSN e identifica aliquota na tabela_icms_2026.
    """
    ano, mes = periodo
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, 28)
    while True:
        try:
            fim = date(ano, mes, fim.day + 1)
        except ValueError:
            break

    notas = _load_notas_saida(cliente_id, inicio, fim)
    resumo_itens: list[dict[str, Any]] = []
    notas_pendentes: list[dict[str, Any]] = []
    base_total = 0.0

    for nota in notas:
        nota_id = str(nota.get("id") or "")
        arquivo = str(nota.get("arquivo") or "")
        xml_bytes = _decode_xml_from_row(nota)
        if not xml_bytes:
            notas_pendentes.append({"nota_id": nota_id, "arquivo": arquivo, "motivo": "XML nao encontrado"})
            _registrar_pendencia_classificacao(cliente_id, nota_id, arquivo, "", "", "XML nao encontrado")
            continue

        try:
            root = ET.parse(BytesIO(xml_bytes)).getroot()
        except Exception:
            notas_pendentes.append({"nota_id": nota_id, "arquivo": arquivo, "motivo": "XML invalido"})
            _registrar_pendencia_classificacao(cliente_id, nota_id, arquivo, "", "", "XML invalido")
            continue

        uf_origem = _text(root, ".//nfe:emit/nfe:enderEmit/nfe:UF").upper()
        uf_destino = _text(root, ".//nfe:dest/nfe:enderDest/nfe:UF").upper()

        for det in root.findall(".//nfe:det", NFE_NS):
            prod = det.find("nfe:prod", NFE_NS)
            icms_node = det.find(".//nfe:ICMS/*", NFE_NS)

            ncm = _text(prod, "nfe:NCM") if prod is not None else ""
            vprod = _to_float(_text(prod, "nfe:vProd") if prod is not None else "0")
            cst = _text(icms_node, "nfe:CST") if icms_node is not None else ""
            csosn = _text(icms_node, "nfe:CSOSN") if icms_node is not None else ""
            cst_csosn = cst or csosn

            if cst and cst not in CST_RECONHECIDOS:
                _registrar_pendencia_classificacao(
                    cliente_id,
                    nota_id,
                    arquivo,
                    ncm,
                    cst,
                    "CST nao reconhecido",
                )
                notas_pendentes.append({"nota_id": nota_id, "arquivo": arquivo, "motivo": "CST nao reconhecido"})
                continue

            if csosn and csosn not in CSOSN_RECONHECIDOS:
                _registrar_pendencia_classificacao(
                    cliente_id,
                    nota_id,
                    arquivo,
                    ncm,
                    csosn,
                    "CSOSN nao reconhecido",
                )
                notas_pendentes.append({"nota_id": nota_id, "arquivo": arquivo, "motivo": "CSOSN nao reconhecido"})
                continue

            if not cst_csosn:
                _registrar_pendencia_classificacao(
                    cliente_id,
                    nota_id,
                    arquivo,
                    ncm,
                    "",
                    "CST/CSOSN ausente",
                )
                notas_pendentes.append({"nota_id": nota_id, "arquivo": arquivo, "motivo": "CST/CSOSN ausente"})
                continue

            aliq_interna, aliq_inter = _aliquotas_por_ncm(ncm, uf_origem, uf_destino)
            if aliq_interna is None or aliq_inter is None:
                _registrar_pendencia_classificacao(
                    cliente_id,
                    nota_id,
                    arquivo,
                    ncm,
                    cst_csosn,
                    "NCM sem aliquota mapeada na tabela_icms_2026",
                )
                notas_pendentes.append({"nota_id": nota_id, "arquivo": arquivo, "motivo": "NCM sem aliquota"})
                continue

            base_total += vprod
            resumo_itens.append(
                {
                    "nota_id": nota_id,
                    "arquivo": arquivo,
                    "ncm": ncm,
                    "cst_csosn": cst_csosn,
                    "valor_item": vprod,
                    "aliquota_interna": aliq_interna,
                    "aliquota_interestadual": aliq_inter,
                    "status": "Classificado",
                }
            )

    return {
        "periodo": f"{mes:02d}/{ano}",
        "base_icms_total": base_total,
        "itens_classificados": resumo_itens,
        "pendencias": notas_pendentes,
        "notas_processadas": len(notas),
    }


def calcular_icms_complementacao_to(nota_id: str) -> dict[str, Any]:
    """
    Calcula ICMS Complementacao (TO): Base * (Aliquota Interna - Aliquota Interestadual).
    """
    rows = fetch_rows(
        table_name="fiscal_nfe_xml_cache",
        columns="*",
        eq_filters={"id": nota_id},
        limit=1,
    )
    if not rows:
        return {"nota_id": nota_id, "aplica": False, "motivo": "Nota nao encontrada"}

    nota = rows[0]
    cliente_id = str(nota.get("cliente_id") or "")
    cliente_rows = fetch_rows(
        table_name="clientes",
        columns="id,regime_tributario,endereco",
        eq_filters={"id": cliente_id},
        limit=1,
    )
    if not cliente_rows:
        return {"nota_id": nota_id, "aplica": False, "motivo": "Cliente nao encontrado"}

    cliente = cliente_rows[0]
    uf = str((cliente.get("endereco") or {}).get("estado") or "").strip().upper()
    regime = str(cliente.get("regime_tributario") or "").strip()

    if uf != "TO" or regime != "Simples Nacional":
        return {
            "nota_id": nota_id,
            "aplica": False,
            "motivo": "Regra aplica apenas para TO no Simples Nacional",
        }

    xml_bytes = _decode_xml_from_row(nota)
    if not xml_bytes:
        return {"nota_id": nota_id, "aplica": False, "motivo": "XML nao encontrado"}

    root = ET.parse(BytesIO(xml_bytes)).getroot()
    uf_origem = _text(root, ".//nfe:emit/nfe:enderEmit/nfe:UF").upper()
    uf_destino = _text(root, ".//nfe:dest/nfe:enderDest/nfe:UF").upper() or "TO"

    detalhes: list[dict[str, Any]] = []
    total = 0.0

    for det in root.findall(".//nfe:det", NFE_NS):
        prod = det.find("nfe:prod", NFE_NS)
        icms_node = det.find(".//nfe:ICMS/*", NFE_NS)

        ncm = _text(prod, "nfe:NCM") if prod is not None else ""
        cst = _text(icms_node, "nfe:CST") if icms_node is not None else ""
        csosn = _text(icms_node, "nfe:CSOSN") if icms_node is not None else ""
        cst_csosn = cst or csosn
        base_item = _to_float(_text(prod, "nfe:vProd") if prod is not None else "0")

        if not cst_csosn:
            _registrar_pendencia_classificacao(
                cliente_id,
                nota_id,
                str(nota.get("arquivo") or ""),
                ncm,
                "",
                "CST/CSOSN ausente para complemento TO",
            )
            continue

        aliq_interna, aliq_inter = _aliquotas_por_ncm(ncm, uf_origem, uf_destino)
        if aliq_interna is None or aliq_inter is None:
            _registrar_pendencia_classificacao(
                cliente_id,
                nota_id,
                str(nota.get("arquivo") or ""),
                ncm,
                cst_csosn,
                "NCM sem aliquota para complemento TO",
            )
            continue

        diff = max((aliq_interna - aliq_inter) / 100.0, 0.0)
        valor = base_item * diff
        total += valor

        detalhes.append(
            {
                "ncm": ncm,
                "base_calculo": base_item,
                "aliquota_interna": aliq_interna,
                "aliquota_interestadual": aliq_inter,
                "diferencial": max(aliq_interna - aliq_inter, 0.0),
                "valor_complementacao": valor,
                "formula": "Base * (Aliquota Interna - Aliquota Interestadual)",
            }
        )

    return {
        "nota_id": nota_id,
        "aplica": True,
        "valor_total": total,
        "detalhes": detalhes,
    }


def _render_simples_nacional_ecac(empresa: dict[str, Any], mes: int, ano: int) -> None:
    cliente_id = str(empresa.get("id") or "")
    fim_periodo = date(ano, mes, 1)
    while True:
        try:
            fim_periodo = date(ano, mes, fim_periodo.day + 1)
        except ValueError:
            break

    inicio_periodo = date(ano, mes, 1)
    notas_periodo = _load_notas_saida(cliente_id, inicio_periodo, fim_periodo)
    notas_12m = _load_notas_ultimos_12_meses(cliente_id, fim_periodo)

    receita_12m = 0.0
    for nota in notas_12m:
        receita_12m += float(nota.get("valor_total") or 0.0)

    folha_12m = st.number_input(
        "Folha de pagamento (ultimos 12 meses)",
        min_value=0.0,
        value=0.0,
        step=100.0,
        help="Utilizado para calculo automatico do Fator R.",
    )

    fator_r = (folha_12m / receita_12m) if receita_12m > 0 else 0.0
    anexo_servicos = "III" if fator_r >= 0.28 else "V"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Receita 12m", f"R$ {receita_12m:,.2f}")
    with c2:
        st.metric("Folha 12m", f"R$ {folha_12m:,.2f}")
    with c3:
        st.metric("Fator R", f"{fator_r:.4f}")

    st.caption(f"Anexo sugerido para servicos pelo Fator R: {anexo_servicos}")

    receitas_por_anexo = {anexo: 0.0 for anexo in ANEXOS}
    for nota in notas_periodo:
        xml_bytes = _decode_xml_from_row(nota)
        if not xml_bytes:
            continue
        try:
            root = ET.parse(BytesIO(xml_bytes)).getroot()
        except Exception:
            continue

        anexo = _classificar_anexo_nota(root, fator_r)
        receitas_por_anexo[anexo] += _to_float(_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF"))

    st.markdown("### Declaracao por Anexo (estilo PGDAS-D)")

    declaracao_anexos: dict[str, dict[str, float]] = {}
    for anexo in ANEXOS:
        declaracao_anexos[anexo] = _anexo_expander_ui(anexo, receitas_por_anexo[anexo])

    if st.button("Gerar memoria de calculo do Simples", type="primary"):
        memoria: list[dict[str, Any]] = []
        total_das = 0.0

        for anexo, payload in declaracao_anexos.items():
            receita_bruta = float(payload["receita_bruta"])
            receita_tributavel = max(
                receita_bruta
                - float(payload["receita_st"])
                - float(payload["receita_monofasia"])
                - float(payload["receita_exportacao"]),
                0.0,
            )

            if receita_tributavel <= 0:
                continue

            faixa = obter_faixa_anexo(anexo, receita_12m)
            if faixa is None:
                continue

            aliquota_nominal = float(faixa["aliquota"])
            parcela_deduzir = float(faixa["deducao"])
            aliquota_efetiva = 0.0
            if receita_12m > 0:
                aliquota_efetiva = ((receita_12m * aliquota_nominal) - parcela_deduzir) / receita_12m

            valor_das = max(receita_tributavel * aliquota_efetiva, 0.0)
            total_das += valor_das

            memoria.append(
                {
                    "anexo": anexo,
                    "receita_bruta": receita_bruta,
                    "receita_tributavel": receita_tributavel,
                    "aliquota_nominal": aliquota_nominal,
                    "parcela_deduzir": parcela_deduzir,
                    "aliquota_efetiva": aliquota_efetiva,
                    "valor_das": valor_das,
                    "formula": "Aliquota_efetiva = ((Valor_bruto * Aliquota_nominal) - Parcela_deduzir) / Valor_bruto",
                }
            )

        if not memoria:
            st.warning("Nao ha receitas tributaveis para gerar declaracao.")
            return

        st.markdown("### Memoria de Calculo")
        st.latex(r"Aliquota_{efetiva} = \\frac{Valor_{bruto} \\times Aliquota_{nominal} - Parcela_{deduzir}}{Valor_{bruto}}")
        st.dataframe(memoria, use_container_width=True, hide_index=True)

        insert_rows(
            table_name="apuracoes_simples",
            rows=[
                {
                    "cliente_id": cliente_id,
                    "mes": mes,
                    "ano": ano,
                    "regime_tributario": str(empresa.get("regime_tributario") or ""),
                    "receita_bruta_periodo": sum(v["receita_bruta"] for v in declaracao_anexos.values()),
                    "receita_bruta_12m": receita_12m,
                    "folha_12m": folha_12m,
                    "fator_r": fator_r,
                    "anexo_servicos_recomendado": anexo_servicos,
                    "payload_declaracao": declaracao_anexos,
                    "memoria_calculo": memoria,
                    "total_das": total_das,
                    "status": "PRONTO_CONFERENCIA",
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
        )

        st.success("Calculos do Simples Nacional prontos para conferencia.")


def _render_icms_automatizado(empresa: dict[str, Any], mes: int, ano: int) -> None:
    cliente_id = str(empresa.get("id") or "")

    if st.button("Processar apuracao automatica de ICMS", type="primary"):
        resultado = calcular_base_icms(cliente_id=cliente_id, periodo=(ano, mes))

        itens = resultado.get("itens_classificados", [])
        pendencias = resultado.get("pendencias", [])

        st.markdown("### Resumo da Base ICMS")
        st.metric("Base de calculo total", f"R$ {float(resultado.get('base_icms_total') or 0.0):,.2f}")
        st.caption(
            f"Notas processadas: {resultado.get('notas_processadas', 0)} | "
            f"Itens classificados: {len(itens)} | Pendencias: {len(pendencias)}"
        )

        if itens:
            st.dataframe(itens, use_container_width=True, hide_index=True)

        complemento_total = 0.0
        detalhes_comp: list[dict[str, Any]] = []
        nota_ids = sorted({str(item.get("nota_id") or "") for item in itens if item.get("nota_id")})

        for nota_id in nota_ids:
            comp = calcular_icms_complementacao_to(nota_id)
            if comp.get("aplica") and float(comp.get("valor_total") or 0.0) > 0:
                complemento_total += float(comp.get("valor_total") or 0.0)
                for row in comp.get("detalhes", []):
                    row_copy = dict(row)
                    row_copy["nota_id"] = nota_id
                    detalhes_comp.append(row_copy)

        st.markdown("### ICMS Complementacao (TO)")
        st.metric("Valor de complementacao no mes", f"R$ {complemento_total:,.2f}")
        if detalhes_comp:
            st.dataframe(detalhes_comp, use_container_width=True, hide_index=True)

        if pendencias:
            st.warning("Foram encontradas notas pendentes de classificacao fiscal.")
            st.dataframe(pendencias, use_container_width=True, hide_index=True)

        if st.button("Validar resultado da apuracao", type="secondary"):
            st.success("Resultado validado. Apuracao automatica concluida para conferencia.")


def render_apuracao_impostos() -> None:
    st.subheader("Apuracao de Impostos")

    try:
        empresas = _load_empresas()
    except Exception as exc:
        st.error(f"Falha ao carregar empresas: {exc}")
        return

    if not empresas:
        st.info("Cadastre ao menos uma empresa antes de apurar impostos.")
        return

    options = {f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in empresas}
    selected_label = st.selectbox("Empresa", list(options.keys()), index=0)
    empresa = options[selected_label]

    c1, c2 = st.columns(2)
    with c1:
        mes = st.selectbox("Mes de referencia", list(range(1, 13)), index=max(0, date.today().month - 1), format_func=lambda m: f"{m:02d}")
    with c2:
        ano = st.number_input("Ano de referencia", min_value=2020, max_value=2100, value=date.today().year, step=1)

    tab_simples, tab_icms = st.tabs([
        "Apuracao Simples Nacional (Estilo e-CAC)",
        "ICMS Automatizado",
    ])

    with tab_simples:
        _render_simples_nacional_ecac(empresa, int(mes), int(ano))

    with tab_icms:
        _render_icms_automatizado(empresa, int(mes), int(ano))
