from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
import logging
import re
from typing import Any
import xml.etree.ElementTree as ET

from db import fetch_rows, insert_rows
from fiscal.certificados import (
    CertificateInvalidError,
    CertificateMissingError,
    ClienteCertificateStore,
    is_certificate_expired,
)
from fiscal.importador_xml import XMLProdutoPayload, sincronizar_produtos_por_xml
from fiscal.motor_icms import NotaFiscalICMSInput, apurar_icms_dict
from fiscal.receita_federal_gateway import (
    ReceitaDownloadRequest,
    ReceitaFederalGateway,
    SefazDistribuicaoDFeGateway,
)
from fiscal.sped_mapper import map_xml_to_sped_records, render_sped_txt

NFE_NAMESPACE = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
DEFAULT_FISCAL_TABLE = "fiscal_nfe_imports"
DEFAULT_USAGE_LOG_TABLE = "logs_de_uso"

STATUS_SUCCESS = "SUCCESS"
STATUS_FAIL = "FAIL"
STATUS_PERMISSION_DENIED = "PERMISSION_DENIED"
STATUS_CERTIFICATE_EXPIRED = "CERTIFICATE_EXPIRED"
STATUS_CERTIFICATE_MISSING = "CERTIFICATE_MISSING"
STATUS_CERTIFICATE_INVALID = "CERTIFICATE_INVALID"
STATUS_CLIENT_NOT_FOUND = "CLIENT_NOT_FOUND"

FEATURE_DOWNLOAD = "download"
FEATURE_APURACAO = "apuracao"
FEATURE_SPED = "sped"


class NFeDownloaderServiceError(Exception):
    """Erro base do servico de download NF-e."""


class PlanPermissionError(NFeDownloaderServiceError):
    """Erro de permissao de plano do cliente."""


class CertificateExpiredError(NFeDownloaderServiceError):
    """Erro de certificado expirado para operacao de download."""


@dataclass(frozen=True)
class NFeDownloaderRequest:
    """Payload para execucao do servico desacoplado de interface."""

    xml_payloads: list[XMLProdutoPayload] = field(default_factory=list)
    cliente_id: str | None = None
    solicitante: str | None = None
    origem: str = "api_interna"
    custo: float | None = None
    executar_apuracao: bool = False
    executar_sped: bool = False
    mes_referencia: int | None = None
    ano_referencia: int | None = None
    baixar_da_receita: bool = False
    receita_request: ReceitaDownloadRequest | None = None


class NFeDownloaderService:
    """
    Servico de processamento de NF-e sem dependencia de Streamlit.

    Responsabilidades:
    - Validar permissao por plano contratado.
    - Persistir importacao de NF-e.
    - Sincronizar cadastro inteligente de produtos.
    - Expor status deterministico para API interna.
    - Registrar auditoria de uso para faturamento SaaS.
    """

    def __init__(
        self,
        fiscal_table: str = DEFAULT_FISCAL_TABLE,
        usage_log_table: str = DEFAULT_USAGE_LOG_TABLE,
        certificate_store: ClienteCertificateStore | None = None,
        receita_gateway: ReceitaFederalGateway | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.fiscal_table = fiscal_table
        self.usage_log_table = usage_log_table
        self.certificate_store = certificate_store or ClienteCertificateStore()
        self.receita_gateway = receita_gateway or SefazDistribuicaoDFeGateway()
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def processar(self, request: NFeDownloaderRequest) -> dict[str, Any]:
        """Executa processamento completo e retorna status para camada chamadora."""
        started_at = datetime.now(timezone.utc)
        cliente_id = request.cliente_id
        payloads = list(request.xml_payloads)
        receita_result: dict[str, Any] | None = None
        receita_warnings: list[str] = []
        status = STATUS_SUCCESS
        detail = ""

        try:
            if not cliente_id:
                cliente_id = self._resolve_cliente_id_from_xml(payloads)

            if not cliente_id and request.receita_request is not None:
                cliente_id = self._resolve_cliente_id_from_cnpj(
                    request.receita_request.cnpj_autor
                )

            if not cliente_id:
                status = STATUS_CLIENT_NOT_FOUND
                detail = "Cliente nao encontrado para os XMLs enviados."
                return {
                    "status": status,
                    "detail": detail,
                    "processed": 0,
                    "warnings": [],
                    "invalid": [],
                }

            certificate = self.certificate_store.load(cliente_id)
            if is_certificate_expired(certificate):
                raise CertificateExpiredError(
                    "Certificado digital expirado para operacao de download."
                )

            if request.baixar_da_receita:
                receita_req = request.receita_request
                if receita_req is None:
                    raise NFeDownloaderServiceError(
                        "Requisicao para Receita ausente. Informe receita_request."
                    )
                if not receita_req.cnpj_autor:
                    raise NFeDownloaderServiceError(
                        "CNPJ do autor e obrigatorio para consulta na Receita."
                    )

                receita_result_raw = self.receita_gateway.baixar_nfes(receita_req, certificate)
                payloads.extend(receita_result_raw.xml_payloads)
                receita_warnings = list(receita_result_raw.warnings)

                receita_result = {
                    "status_codigo": receita_result_raw.status_codigo,
                    "status_mensagem": receita_result_raw.status_mensagem,
                    "ultimo_nsu": receita_result_raw.ultimo_nsu,
                    "max_nsu": receita_result_raw.max_nsu,
                    "documentos_recebidos": len(receita_result_raw.xml_payloads),
                }

            features = self._get_plan_features(cliente_id)
            self._assert_permissions(
                features=features,
                executar_apuracao=request.executar_apuracao,
                executar_sped=request.executar_sped,
            )

            if not payloads:
                return {
                    "status": STATUS_SUCCESS,
                    "detail": "Nenhuma NF-e disponivel para o periodo consultado.",
                    "processed": 0,
                    "warnings": [],
                    "invalid": [],
                    "cliente_id": cliente_id,
                    "features": sorted(features),
                }

            parsed_rows, parse_errors = self._parse_xml_payloads(payloads)
            if not parsed_rows:
                status = STATUS_FAIL
                detail = "Nenhum XML valido para importacao."
                return {
                    "status": status,
                    "detail": detail,
                    "processed": 0,
                    "warnings": parse_errors,
                    "invalid": [],
                    "cliente_id": cliente_id,
                    "features": sorted(features),
                }

            insert_result = insert_rows(table_name=self.fiscal_table, rows=parsed_rows)
            sync_result = sincronizar_produtos_por_xml(payloads)

            apuracao_result: list[dict[str, Any]] = []
            if request.executar_apuracao:
                apuracao_result = self._executar_apuracao(cliente_id=cliente_id, payloads=payloads)

            sped_result: dict[str, Any] | None = None
            if request.executar_sped:
                sped_result = self._gerar_sped(payloads, request.mes_referencia, request.ano_referencia)

            warnings = list(parse_errors)
            warnings.extend(receita_warnings)
            warnings.extend(sync_result.get("warnings", []))

            return {
                "status": STATUS_SUCCESS,
                "detail": "Processamento concluido com sucesso.",
                "cliente_id": cliente_id,
                "features": sorted(features),
                "insert": insert_result,
                "sync_produtos": sync_result,
                "receita": receita_result,
                "apuracao": apuracao_result,
                "sped": sped_result,
                "processed": len(parsed_rows),
                "warnings": warnings,
                "invalid": sync_result.get("invalid", []),
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        except CertificateMissingError as exc:
            status = STATUS_CERTIFICATE_MISSING
            detail = str(exc)
            self.logger.warning("Certificado ausente para cliente %s: %s", cliente_id, detail)
            return {
                "status": status,
                "detail": detail,
                "processed": 0,
                "warnings": [],
                "invalid": [],
                "cliente_id": cliente_id,
            }
        except CertificateInvalidError as exc:
            status = STATUS_CERTIFICATE_INVALID
            detail = str(exc)
            self.logger.warning("Certificado invalido para cliente %s: %s", cliente_id, detail)
            return {
                "status": status,
                "detail": detail,
                "processed": 0,
                "warnings": [],
                "invalid": [],
                "cliente_id": cliente_id,
            }
        except CertificateExpiredError as exc:
            status = STATUS_CERTIFICATE_EXPIRED
            detail = str(exc)
            self.logger.warning("Certificado expirado: %s", detail)
            return {
                "status": status,
                "detail": detail,
                "processed": 0,
                "warnings": [],
                "invalid": [],
            }
        except PlanPermissionError as exc:
            status = STATUS_PERMISSION_DENIED
            detail = str(exc)
            self.logger.warning("Permissao negada para cliente %s: %s", cliente_id, detail)
            return {
                "status": status,
                "detail": detail,
                "processed": 0,
                "warnings": [],
                "invalid": [],
                "cliente_id": cliente_id,
            }
        except Exception as exc:
            status = STATUS_FAIL
            detail = str(exc)
            self.logger.exception("Falha inesperada no NFeDownloaderService")
            return {
                "status": status,
                "detail": detail,
                "processed": 0,
                "warnings": [],
                "invalid": [],
                "cliente_id": cliente_id,
            }
        finally:
            try:
                self._registrar_log_uso(
                    cliente_id=cliente_id,
                    request=request,
                    status=status,
                    detail=detail,
                    processed=len(payloads),
                    started_at=started_at,
                )
            except Exception:
                self.logger.exception("Falha ao registrar log de uso")

    def _parse_xml_payloads(
        self, payloads: list[XMLProdutoPayload]
    ) -> tuple[list[dict[str, str | float]], list[str]]:
        parsed_rows: list[dict[str, str | float]] = []
        errors: list[str] = []

        for payload in payloads:
            try:
                parsed_rows.append(self._parse_nfe_xml(payload.content, payload.file_name))
            except Exception as exc:
                errors.append(f"{payload.file_name}: {exc}")

        return parsed_rows, errors

    def _parse_nfe_xml(self, content: bytes, original_name: str) -> dict[str, str | float]:
        root = ET.parse(BytesIO(content)).getroot()
        emitente = self._find_text(root, ".//nfe:emit/nfe:xNome")
        cnpj = self._find_text(root, ".//nfe:emit/nfe:CNPJ")
        valor_str = self._find_text(root, ".//nfe:total/nfe:ICMSTot/nfe:vNF")

        valor = 0.0
        if valor_str:
            valor = float(valor_str.replace(",", "."))

        return {
            "arquivo": original_name,
            "emitente": emitente,
            "cnpj_emitente": cnpj,
            "valor_total": valor,
            "origem": "nfe_downloader_service",
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }

    def _resolve_cliente_id_from_xml(self, payloads: list[XMLProdutoPayload]) -> str | None:
        for payload in payloads:
            try:
                root = ET.parse(BytesIO(payload.content)).getroot()
                cnpj = self._find_text(root, ".//nfe:emit/nfe:CNPJ")
                if not cnpj:
                    continue
                cliente_id = self._resolve_cliente_id_from_cnpj(cnpj)
                if cliente_id:
                    return cliente_id
            except Exception:
                continue
        return None

    def _resolve_cliente_id_from_cnpj(self, cnpj: str) -> str | None:
        rows = fetch_rows(
            table_name="clientes",
            columns="id,cnpj",
            eq_filters={"cnpj": cnpj},
            limit=1,
        )
        if not rows:
            return None
        return str(rows[0].get("id") or "")

    def _get_plan_features(self, cliente_id: str) -> set[str]:
        rows = fetch_rows(
            table_name="planos_contratados",
            columns="*",
            eq_filters={"cliente_id": cliente_id},
            order_by="created_at",
            desc=True,
            limit=20,
        )

        if not rows:
            raise PlanPermissionError(
                "Nenhum plano contratado encontrado para o cliente."
            )

        row = rows[0]
        if len(rows) > 1:
            active_rows = [
                item for item in rows if item.get("ativo") is True or item.get("active") is True
            ]
            if active_rows:
                row = active_rows[0]

        features = self._extract_features_from_plan_row(row)

        if FEATURE_DOWNLOAD not in features:
            raise PlanPermissionError(
                "Plano contratado nao possui permissao para download de NF-e."
            )

        return features

    def _extract_features_from_plan_row(self, row: dict[str, Any]) -> set[str]:
        features: set[str] = set()

        if bool(row.get("permite_download")):
            features.add(FEATURE_DOWNLOAD)
        if bool(row.get("permite_apuracao")):
            features.add(FEATURE_APURACAO)
        if bool(row.get("permite_sped")):
            features.add(FEATURE_SPED)

        for key in ("recursos", "features", "modulos"):
            value = row.get(key)
            features.update(self._normalize_feature_value(value))

        plano_texto = row.get("plano") or row.get("nome_plano") or row.get("tipo_plano")
        features.update(self._infer_features_from_plan_name(str(plano_texto or "")))

        return features

    def _normalize_feature_value(self, value: Any) -> set[str]:
        if value is None:
            return set()

        raw_items: list[str] = []

        if isinstance(value, list):
            raw_items = [str(item) for item in value]
        elif isinstance(value, dict):
            for key, enabled in value.items():
                if bool(enabled):
                    raw_items.append(str(key))
        else:
            text = str(value)
            normalized = re.sub(r"[+|;/]", ",", text)
            raw_items = [item.strip() for item in normalized.split(",") if item.strip()]

        mapped: set[str] = set()
        for item in raw_items:
            item_lower = item.strip().lower()
            if "download" in item_lower:
                mapped.add(FEATURE_DOWNLOAD)
            if "apur" in item_lower:
                mapped.add(FEATURE_APURACAO)
            if "sped" in item_lower:
                mapped.add(FEATURE_SPED)

        return mapped

    def _infer_features_from_plan_name(self, plan_name: str) -> set[str]:
        text = plan_name.strip().lower()
        if not text:
            return set()

        if text == "apenas download":
            return {FEATURE_DOWNLOAD}
        if text == "download + apuracao":
            return {FEATURE_DOWNLOAD, FEATURE_APURACAO}
        if text == "download + apuracao + sped":
            return {FEATURE_DOWNLOAD, FEATURE_APURACAO, FEATURE_SPED}

        return self._normalize_feature_value(text)

    def _assert_permissions(
        self,
        features: set[str],
        executar_apuracao: bool,
        executar_sped: bool,
    ) -> None:
        if executar_apuracao and FEATURE_APURACAO not in features:
            raise PlanPermissionError(
                "Plano contratado nao permite executar apuracao."
            )

        if executar_sped and FEATURE_SPED not in features:
            raise PlanPermissionError(
                "Plano contratado nao permite gerar SPED."
            )

    def _executar_apuracao(
        self,
        cliente_id: str,
        payloads: list[XMLProdutoPayload],
    ) -> list[dict[str, Any]]:
        rows = fetch_rows(
            table_name="clientes",
            columns="cnpj,endereco",
            eq_filters={"id": cliente_id},
            limit=1,
        )
        if not rows:
            return []

        empresa = rows[0]
        cnpj_empresa = str(empresa.get("cnpj") or "")
        endereco = empresa.get("endereco") or {}
        uf_empresa = str(endereco.get("estado") or "").strip().upper()

        results: list[dict[str, Any]] = []
        for payload in payloads:
            mapped = map_xml_to_sped_records(BytesIO(payload.content), file_name=payload.file_name)
            c100 = mapped.get("C100", {})
            nota_input = NotaFiscalICMSInput(
                cnpj_empresa=cnpj_empresa,
                uf_empresa=uf_empresa,
                uf_destinatario=str(c100.get("UF_DEST") or ""),
                base_calculo=float(c100.get("VL_BC_ICMS") or c100.get("VL_DOC") or 0.0),
                aplicar_st=True,
                aplicar_difal=True,
                aplicar_complementacao=False,
            )
            results.append(apurar_icms_dict(nota_input))

        return results

    def _gerar_sped(
        self,
        payloads: list[XMLProdutoPayload],
        mes_referencia: int | None,
        ano_referencia: int | None,
    ) -> dict[str, Any]:
        mapped_records: list[dict[str, object]] = []
        for payload in payloads:
            mapped_records.append(
                map_xml_to_sped_records(BytesIO(payload.content), file_name=payload.file_name)
            )

        if not mapped_records:
            return {"status": "skipped", "detail": "Sem XMLs validos para SPED."}

        now = datetime.now(timezone.utc)
        mes = int(mes_referencia or now.month)
        ano = int(ano_referencia or now.year)
        sped_txt = render_sped_txt(mapped_records, mes=mes, ano=ano)

        return {
            "status": "ok",
            "mes": mes,
            "ano": ano,
            "records": len(mapped_records),
            "sped_txt": sped_txt,
        }

    def _registrar_log_uso(
        self,
        cliente_id: str | None,
        request: NFeDownloaderRequest,
        status: str,
        detail: str,
        processed: int,
        started_at: datetime,
    ) -> None:
        if not cliente_id:
            return

        log_row = {
            "cliente_id": cliente_id,
            "solicitante": request.solicitante,
            "origem": request.origem,
            "operacao": "nfe_download",
            "status": status,
            "detalhe": detail,
            "custo": request.custo,
            "quantidade_documentos": processed,
            "metadata": {
                "executar_apuracao": request.executar_apuracao,
                "executar_sped": request.executar_sped,
            },
            "started_at": started_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        insert_rows(table_name=self.usage_log_table, rows=[log_row])

    def _find_text(self, node: ET.Element | None, path: str) -> str:
        if node is None:
            return ""
        found = node.find(path, NFE_NAMESPACE)
        return (found.text or "").strip() if found is not None else ""
