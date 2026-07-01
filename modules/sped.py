from __future__ import annotations

import base64
from datetime import date
from datetime import datetime
from io import BytesIO
from typing import Any

import streamlit as st

from db import fetch_rows
from fiscal.motor_icms import NotaFiscalICMSInput, apurar_icms_dict
from fiscal.sped_mapper import map_xml_to_sped_records, render_sped_txt


def _load_empresas() -> list[dict[str, Any]]:
    """Busca empresas cadastradas para contexto da apuracao fiscal."""
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,endereco",
        order_by="razao_social",
        desc=False,
    )


def _empresa_uf(empresa: dict[str, Any]) -> str:
    """Extrai UF da empresa a partir do JSON de endereco."""
    endereco = empresa.get("endereco") or {}
    return str(endereco.get("estado") or "").strip().upper()


def _parse_iso_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _load_xmls_importados(cliente_id: str, inicio: date, fim: date) -> list[tuple[str, bytes]]:
    rows = fetch_rows(
        table_name="fiscal_nfe_xml_cache",
        columns="arquivo,data_emissao,xml_base64",
        eq_filters={"cliente_id": cliente_id},
        order_by="data_emissao",
        desc=False,
        limit=5000,
    )

    xmls: list[tuple[str, bytes]] = []
    for row in rows:
        dt = _parse_iso_date(str(row.get("data_emissao") or ""))
        if dt is None:
            continue
        if not (inicio <= dt <= fim):
            continue

        encoded = str(row.get("xml_base64") or "").strip()
        if not encoded:
            continue

        try:
            xmls.append((str(row.get("arquivo") or "sem_nome.xml"), base64.b64decode(encoded)))
        except Exception:
            continue

    return xmls


def render_sped_module() -> None:
    """Tela de apuracao ICMS e exportacao de arquivo SPED Fiscal (.txt)."""
    st.title("SPED Fiscal")
    st.caption("Apuracao de ICMS e geracao de arquivo EFD-ICMS/IPI em layout simplificado.")

    try:
        empresas = _load_empresas()
    except Exception as exc:
        st.error(f"Falha ao carregar empresas no Supabase: {exc}")
        return

    if not empresas:
        st.info("Cadastre ao menos uma empresa no modulo de clientes para continuar.")
        return

    empresa_options = {
        f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in empresas
    }
    selected = st.selectbox("Empresa", list(empresa_options.keys()), index=0)
    empresa = empresa_options[selected]

    col1, col2 = st.columns(2)
    with col1:
        mes = st.selectbox(
            "Mes de referencia",
            list(range(1, 13)),
            index=max(0, date.today().month - 1),
            format_func=lambda m: f"{m:02d}",
        )
    with col2:
        ano = st.number_input(
            "Ano de referencia",
            min_value=2020,
            max_value=2100,
            value=date.today().year,
            step=1,
        )

    inicio = date(int(ano), int(mes), 1)
    fim = date(int(ano), int(mes), 28)
    while True:
        try:
            fim = date(int(ano), int(mes), fim.day + 1)
        except ValueError:
            break

    st.info("Importacao de XML centralizada no menu fiscal em 'Centro de Importacao Fiscal'.")
    arquivos = _load_xmls_importados(str(empresa.get("id") or ""), inicio, fim)
    if not arquivos:
        st.warning("Nenhum XML importado encontrado no periodo. Use o Centro de Importacao Fiscal.")
        return

    mapped_records: list[dict[str, object]] = []
    apuracoes_icms: list[dict[str, Any]] = []
    avisos: list[str] = []

    uf_empresa = _empresa_uf(empresa)
    cnpj_empresa = str(empresa.get("cnpj") or "")

    for file_name, xml_content in arquivos:
        try:
            mapped = map_xml_to_sped_records(BytesIO(xml_content), file_name=file_name)
            mapped_records.append(mapped)

            c100 = mapped["C100"]
            payload = NotaFiscalICMSInput(
                cnpj_empresa=cnpj_empresa,
                uf_empresa=uf_empresa,
                uf_destinatario=str(c100.get("UF_DEST") or ""),
                base_calculo=float(c100.get("VL_BC_ICMS") or c100.get("VL_DOC") or 0.0),
                aplicar_st=True,
                aplicar_difal=True,
                aplicar_complementacao=False,
            )
            apuracoes_icms.append(apurar_icms_dict(payload))
        except Exception as exc:
            avisos.append(f"{file_name}: {exc}")

    for aviso in avisos:
        st.warning(aviso)

    if not mapped_records:
        st.error("Nenhum XML valido para gerar SPED.")
        return

    total_icms = sum(float(r.get("icms_total", 0.0)) for r in apuracoes_icms)
    st.metric("ICMS total apurado", f"R$ {total_icms:,.2f}")

    st.subheader("Resumo de apuracao ICMS")
    st.dataframe(apuracoes_icms, use_container_width=True, hide_index=True)

    sped_txt = render_sped_txt(mapped_records, mes=mes, ano=int(ano))
    st.download_button(
        label="Baixar SPED Fiscal (.txt)",
        data=sped_txt.encode("utf-8"),
        file_name=f"sped_fiscal_{int(ano)}_{mes:02d}.txt",
        mime="text/plain",
    )
