from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
from io import BytesIO
from typing import Any
import xml.etree.ElementTree as ET

import streamlit as st
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from db import fetch_rows, insert_rows
from fiscal.importador_xml import XMLProdutoPayload, sincronizar_produtos_por_xml
from fiscal.receita_federal_gateway import ReceitaDownloadRequest, SefazDistribuicaoDFeGateway
from modules.fiscal.apuracao import render_apuracao_impostos
from modules.produtos import render_produtos_module
from modules.sped import render_sped_module

NFE_NAMESPACE = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _load_empresas() -> list[dict[str, Any]]:
    return fetch_rows(
        table_name="clientes",
        columns="id,razao_social,cnpj,regime_tributario,endereco",
        order_by="razao_social",
        desc=False,
    )


def _find_text(node: ET.Element, path: str) -> str:
    found = node.find(path, NFE_NAMESPACE)
    return (found.text or "").strip() if found is not None else ""


def _to_float(value: str) -> float:
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _parse_nfe_row(content: bytes, file_name: str) -> dict[str, Any]:
    root = ET.parse(BytesIO(content)).getroot()
    emitente = _find_text(root, ".//nfe:emit/nfe:xNome")
    cnpj = _find_text(root, ".//nfe:emit/nfe:CNPJ")
    valor_total = _to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF"))

    return {
        "arquivo": file_name,
        "emitente": emitente,
        "cnpj_emitente": cnpj,
        "valor_total": valor_total,
        "origem": "puxador_sefaz",
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }


def _build_nfe_cache_row(cliente_id: str, content: bytes, file_name: str) -> dict[str, Any]:
    root = ET.parse(BytesIO(content)).getroot()

    dh_emi = _find_text(root, ".//nfe:ide/nfe:dhEmi")
    data_emissao = dh_emi[:10] if dh_emi else None
    tp_nf = _find_text(root, ".//nfe:ide/nfe:tpNF")
    operacao = "entrada" if tp_nf == "0" else "saida"

    return {
        "cliente_id": cliente_id,
        "arquivo": file_name,
        "data_emissao": data_emissao,
        "tipo_operacao": operacao,
        "cnpj_emitente": _find_text(root, ".//nfe:emit/nfe:CNPJ"),
        "cnpj_destinatario": _find_text(root, ".//nfe:dest/nfe:CNPJ") or _find_text(root, ".//nfe:dest/nfe:CPF"),
        "valor_total": _to_float(_find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF")),
        "xml_base64": base64.b64encode(content).decode("ascii"),
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return base64.b64encode(digest).decode("ascii")


def _sha256_file(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validar_certificado_a1(pfx_bytes: bytes, password: str) -> dict[str, Any]:
    try:
        from OpenSSL import crypto
    except ModuleNotFoundError as exc:
        raise RuntimeError("Biblioteca OpenSSL indisponivel. Adicione pyOpenSSL no ambiente.") from exc

    passphrase = password.encode("utf-8") if password else b""
    key, certificate, _ = pkcs12.load_key_and_certificates(pfx_bytes, passphrase)

    if key is None or certificate is None:
        raise ValueError("Certificado A1 invalido ou senha incorreta.")

    cert_pem = certificate.public_bytes(encoding=serialization.Encoding.PEM)
    x509 = crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem)

    not_after_raw = x509.get_notAfter().decode("ascii")
    valid_until = datetime.strptime(not_after_raw, "%Y%m%d%H%M%SZ").replace(tzinfo=timezone.utc)
    if valid_until <= datetime.now(timezone.utc):
        raise ValueError("Certificado A1 expirado.")

    return {
        "subject": certificate.subject.rfc4514_string(),
        "issuer": certificate.issuer.rfc4514_string(),
        "serial_number": hex(certificate.serial_number),
        "valid_until": valid_until,
    }


def _registrar_referencia_certificado(
    cliente_id: str,
    metadata: dict[str, Any],
    pfx_bytes: bytes,
    password: str,
) -> None:
    row = {
        "cliente_id": cliente_id,
        "certificado_sha256": _sha256_file(pfx_bytes),
        "senha_hash": _hash_password(password, metadata["serial_number"]),
        "subject": metadata["subject"],
        "issuer": metadata["issuer"],
        "serial_number": metadata["serial_number"],
        "valid_until": metadata["valid_until"].isoformat(),
        "origem": "fiscal_puxador_ui",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    insert_rows(table_name="certificados_a1_referencias", rows=[row])


def render_dashboard_fiscal() -> None:
    st.subheader("Dashboard Fiscal")

    try:
        notas = fetch_rows(
            table_name="fiscal_nfe_imports",
            columns="id,valor_total,criado_em",
            order_by="criado_em",
            desc=True,
            limit=500,
        )
    except Exception as exc:
        st.error(f"Falha ao carregar indicadores fiscais: {exc}")
        return

    total_notas = len(notas)
    valor_total = sum(float(item.get("valor_total") or 0.0) for item in notas)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Notas processadas", total_notas)
    with c2:
        st.metric("Valor total movimentado", f"R$ {valor_total:,.2f}")


def render_puxador() -> None:
    st.subheader("Puxador de Notas (SEFAZ)")
    st.caption("Valide o Certificado A1 antes de consultar a SEFAZ. O sistema nao persiste PFX/senha em texto puro.")

    try:
        empresas = _load_empresas()
    except Exception as exc:
        st.error(f"Falha ao carregar empresas: {exc}")
        return

    if not empresas:
        st.info("Cadastre ao menos uma empresa para usar o puxador SEFAZ.")
        return

    empresa_options = {f"{row.get('razao_social')} ({row.get('cnpj')})": row for row in empresas}
    selected_label = st.selectbox("Empresa", list(empresa_options.keys()), index=0)
    empresa = empresa_options[selected_label]

    c1, c2 = st.columns(2)
    with c1:
        arquivo_pfx = st.file_uploader("Certificado A1 (.pfx)", type=["pfx"])
    with c2:
        senha_certificado = st.text_input("Senha do Certificado", type="password")

    c3, c4 = st.columns(2)
    with c3:
        ambiente = st.selectbox("Ambiente SEFAZ", ["producao", "homologacao"], index=0)
    with c4:
        ult_nsu = st.text_input("Ultimo NSU", value="000000000000000")

    uf_empresa = str((empresa.get("endereco") or {}).get("estado") or "").strip().upper()
    cnpj_empresa = str(empresa.get("cnpj") or "").strip()
    cliente_id = str(empresa.get("id") or "")

    if st.button("Conectar e baixar notas", type="primary"):
        if arquivo_pfx is None:
            st.error("Envie o arquivo .pfx para continuar.")
            return
        if not senha_certificado:
            st.error("Informe a senha do certificado A1.")
            return
        if not uf_empresa:
            st.error("UF da empresa nao encontrada. Atualize o endereco do cliente.")
            return

        try:
            pfx_bytes = arquivo_pfx.getvalue()
            cert_meta = _validar_certificado_a1(pfx_bytes, senha_certificado)
            _registrar_referencia_certificado(
                cliente_id=cliente_id,
                metadata=cert_meta,
                pfx_bytes=pfx_bytes,
                password=senha_certificado,
            )

            from fiscal.certificados import CertificateBundle

            bundle = CertificateBundle(
                pfx_bytes=pfx_bytes,
                password=senha_certificado,
                subject=str(cert_meta["subject"]),
                issuer=str(cert_meta["issuer"]),
                serial_number=str(cert_meta["serial_number"]),
                valid_from=datetime.now(timezone.utc),
                valid_until=cert_meta["valid_until"],
            )

            gateway = SefazDistribuicaoDFeGateway()
            result = gateway.baixar_nfes(
                ReceitaDownloadRequest(
                    cnpj_autor=cnpj_empresa,
                    uf_autor=uf_empresa,
                    ult_nsu=ult_nsu.strip() or "000000000000000",
                    ambiente=ambiente,
                ),
                bundle,
            )

            st.success(
                "Conexao autorizada com SEFAZ. "
                f"Documentos recebidos: {len(result.xml_payloads)}"
            )
            st.caption(
                f"cStat: {result.status_codigo} | xMotivo: {result.status_mensagem} | ultNSU: {result.ultimo_nsu}"
            )

            if result.xml_payloads:
                rows = [_parse_nfe_row(item.content, item.file_name) for item in result.xml_payloads]
                insert_rows(table_name="fiscal_nfe_imports", rows=rows)

                cache_rows = [
                    _build_nfe_cache_row(cliente_id=cliente_id, content=item.content, file_name=item.file_name)
                    for item in result.xml_payloads
                ]
                insert_rows(table_name="fiscal_nfe_xml_cache", rows=cache_rows)

                sync_payloads = [
                    XMLProdutoPayload(file_name=item.file_name, content=item.content)
                    for item in result.xml_payloads
                ]
                sync_result = sincronizar_produtos_por_xml(sync_payloads)
                st.info(
                    "Sincronizacao de produtos concluida. "
                    f"Registros processados: {sync_result.get('processed', 0)}"
                )
        except Exception as exc:
            st.error(f"Falha no puxador SEFAZ: {exc}")


def render_relatorios_sped() -> None:
    render_sped_module()


def render_fiscal_module() -> None:
    st.title("Modulo Fiscal")

    menu_items = [
        "Dashboard Fiscal",
        "Puxador de Notas (SEFAZ)",
        "Cadastro de Produtos",
        "Apuracao de Impostos",
        "Relatorios e SPED",
    ]
    submenu = st.sidebar.radio("Menu Fiscal", menu_items, key="fiscal_menu_sidebar")

    routes = {
        "Dashboard Fiscal": render_dashboard_fiscal,
        "Puxador de Notas (SEFAZ)": render_puxador,
        "Cadastro de Produtos": render_produtos_module,
        "Apuracao de Impostos": render_apuracao_impostos,
        "Relatorios e SPED": render_relatorios_sped,
    }
    routes[submenu]()
