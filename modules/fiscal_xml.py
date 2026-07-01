from __future__ import annotations

import streamlit as st

from fiscal.importador_xml import XMLProdutoPayload
from fiscal.nfe_downloader import NFeDownloaderRequest, NFeDownloaderService
from fiscal.receita_federal_gateway import ReceitaDownloadRequest

DEFAULT_FISCAL_TABLE = "fiscal_nfe_imports"


def render_importacao_xml() -> None:
    """Renderiza interface de importacao de XML de NF-e."""
    st.subheader("Importacao XML NF-e")
    st.caption("Importe XML de NF-e e prepare os dados para gravacao no Supabase.")

    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos XML de NF-e",
        type=["xml"],
        accept_multiple_files=True,
    )

    st.markdown("### Download direto Receita/SEFAZ")
    baixar_da_receita = st.checkbox("Baixar NF-e direto da Receita", value=False)

    receita_request: ReceitaDownloadRequest | None = None
    if baixar_da_receita:
        col1, col2 = st.columns(2)
        with col1:
            cnpj_autor = st.text_input("CNPJ do autor", value="")
        with col2:
            uf_autor = st.text_input("UF do autor", value="").upper()

        col3, col4 = st.columns(2)
        with col3:
            ult_nsu = st.text_input("Ultimo NSU", value="000000000000000")
        with col4:
            ambiente = st.selectbox("Ambiente", ["producao", "homologacao"], index=0)

        receita_request = ReceitaDownloadRequest(
            cnpj_autor=cnpj_autor.strip(),
            uf_autor=uf_autor.strip(),
            ult_nsu=ult_nsu.strip() or "000000000000000",
            ambiente=ambiente,
        )

    if not uploaded_files and not baixar_da_receita:
        st.info("Aguardando upload dos XMLs.")
        return

    parsed_rows: list[dict[str, str | float]] = []
    xml_payloads: list[XMLProdutoPayload] = []
    errors: list[str] = []

    # Processa arquivo por arquivo para evitar falha total em lote misto.
    for file_obj in uploaded_files or []:
        try:
            content = file_obj.getvalue()
            parsed_rows.append({"arquivo": file_obj.name})
            xml_payloads.append(XMLProdutoPayload(file_name=file_obj.name, content=content))
        except Exception as exc:
            errors.append(f"{file_obj.name}: {exc}")

    if parsed_rows:
        st.dataframe(parsed_rows, use_container_width=True, hide_index=True)

    if errors:
        st.warning("Alguns arquivos nao puderam ser lidos:")
        for err in errors:
            st.write(f"- {err}")

    table_name = st.text_input("Tabela destino", value=DEFAULT_FISCAL_TABLE)
    solicitante = st.text_input("Solicitante (opcional)", value="streamlit_ui")

    col_apuracao, col_sped = st.columns(2)
    with col_apuracao:
        executar_apuracao = st.checkbox("Executar apuracao", value=False)
    with col_sped:
        executar_sped = st.checkbox("Gerar SPED", value=False)

    if st.button("Salvar XMLs no Supabase", type="primary"):
        try:
            service = NFeDownloaderService(fiscal_table=table_name)
            result = service.processar(
                NFeDownloaderRequest(
                    xml_payloads=xml_payloads,
                    solicitante=solicitante,
                    origem="streamlit_ui",
                    executar_apuracao=executar_apuracao,
                    executar_sped=executar_sped,
                    baixar_da_receita=baixar_da_receita,
                    receita_request=receita_request,
                )
            )

            status = str(result.get("status") or "")
            if status == "SUCCESS":
                st.success(
                    "Importacao concluida com sucesso. "
                    f"Registros processados: {result.get('processed', 0)}"
                )
            elif status == "CERTIFICATE_EXPIRED":
                st.error("Falha no certificado digital: certificado expirado.")
            elif status == "CERTIFICATE_MISSING":
                st.error("Cliente sem certificado A1 cadastrado para download.")
            elif status == "CERTIFICATE_INVALID":
                st.error("Certificado A1 invalido ou senha incorreta.")
            elif status == "PERMISSION_DENIED":
                st.error("Plano contratado nao permite essa operacao.")
            elif status == "CLIENT_NOT_FOUND":
                st.error("Cliente nao encontrado para os XMLs enviados.")
            else:
                st.error("Falha no processamento do servico de NF-e.")

            st.json(result)

            warnings = result.get("warnings", [])
            if isinstance(warnings, list):
                for warning in warnings:
                    st.warning(str(warning))

            invalids = result.get("invalid", [])
            if isinstance(invalids, list):
                for invalid in invalids:
                    st.error(str(invalid))
        except Exception as exc:
            st.error(f"Falha ao salvar no Supabase: {exc}")
