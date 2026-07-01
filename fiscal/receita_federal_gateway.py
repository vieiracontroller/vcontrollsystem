from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import os
import tempfile
from typing import Iterator, Protocol
import xml.etree.ElementTree as ET

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from fiscal.certificados import CertificateBundle
from fiscal.importador_xml import XMLProdutoPayload

SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
NFE_WS_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"
NFE_DFE_NS = "http://www.portalfiscal.inf.br/nfe"


@dataclass(frozen=True)
class ReceitaDownloadRequest:
    """Requisicao para distribuicao DF-e via NSU no ambiente oficial."""

    cnpj_autor: str
    uf_autor: str
    ult_nsu: str = "000000000000000"
    ambiente: str = "producao"
    max_documentos: int = 50


@dataclass(frozen=True)
class ReceitaDownloadResult:
    """Resultado do download de DF-e via webservice da Receita/SEFAZ."""

    xml_payloads: list[XMLProdutoPayload]
    status_codigo: str
    status_mensagem: str
    ultimo_nsu: str
    max_nsu: str
    warnings: list[str]


class ReceitaFederalGateway(Protocol):
    """Contrato de comunicacao com Receita/SEFAZ para download de NF-e."""

    def baixar_nfes(
        self,
        request: ReceitaDownloadRequest,
        certificate: CertificateBundle,
    ) -> ReceitaDownloadResult:
        ...


class SefazDistribuicaoDFeGateway:
    """
    Gateway HTTP para servico de distribuicao DF-e com certificado A1.

    URLs podem ser definidas via ambiente:
    - NFE_DFE_URL_PRODUCAO
    - NFE_DFE_URL_HOMOLOGACAO
    """

    def __init__(self, timeout_seconds: int = 45) -> None:
        self.timeout_seconds = timeout_seconds
        self.url_producao = os.getenv("NFE_DFE_URL_PRODUCAO", "").strip()
        self.url_homologacao = os.getenv("NFE_DFE_URL_HOMOLOGACAO", "").strip()

    def baixar_nfes(
        self,
        request: ReceitaDownloadRequest,
        certificate: CertificateBundle,
    ) -> ReceitaDownloadResult:
        endpoint = self._resolve_endpoint(request.ambiente)
        envelope = self._build_dist_nsu_envelope(request)

        with _pfx_to_pem_files(certificate) as (cert_path, key_path):
            response = requests.post(
                endpoint,
                data=envelope.encode("utf-8"),
                headers={"Content-Type": "application/soap+xml; charset=utf-8"},
                cert=(cert_path, key_path),
                timeout=self.timeout_seconds,
            )

        response.raise_for_status()

        return self._parse_response(response.text, request.max_documentos)

    def _resolve_endpoint(self, ambiente: str) -> str:
        env = ambiente.strip().lower()
        if env == "homologacao":
            if not self.url_homologacao:
                raise RuntimeError(
                    "Endpoint homologacao nao configurado. Defina NFE_DFE_URL_HOMOLOGACAO."
                )
            return self.url_homologacao

        if not self.url_producao:
            raise RuntimeError(
                "Endpoint producao nao configurado. Defina NFE_DFE_URL_PRODUCAO."
            )
        return self.url_producao

    def _build_dist_nsu_envelope(self, request: ReceitaDownloadRequest) -> str:
        uf_code = _uf_code(request.uf_autor)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")

        return f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<soap12:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" xmlns:soap12=\"{SOAP_NS}\">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns=\"{NFE_WS_NS}\">
      <nfeDadosMsg>
        <distDFeInt xmlns=\"{NFE_DFE_NS}\" versao=\"1.01\">
          <tpAmb>{'2' if request.ambiente.lower() == 'homologacao' else '1'}</tpAmb>
          <cUFAutor>{uf_code}</cUFAutor>
          <CNPJ>{request.cnpj_autor}</CNPJ>
          <distNSU>
            <ultNSU>{request.ult_nsu}</ultNSU>
          </distNSU>
        </distDFeInt>
      </nfeDadosMsg>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>""".replace("{now}", now)

    def _parse_response(self, xml_text: str, max_docs: int) -> ReceitaDownloadResult:
        root = ET.fromstring(xml_text)

        ns = {
            "soap": SOAP_NS,
            "nfe": NFE_DFE_NS,
        }

        ret = root.find(".//nfe:retDistDFeInt", ns)
        if ret is None:
            raise RuntimeError("Resposta invalida do webservice de distribuicao DF-e.")

        status_codigo = (ret.findtext("nfe:cStat", default="", namespaces=ns) or "").strip()
        status_mensagem = (ret.findtext("nfe:xMotivo", default="", namespaces=ns) or "").strip()
        ultimo_nsu = (ret.findtext("nfe:ultNSU", default="", namespaces=ns) or "").strip()
        max_nsu = (ret.findtext("nfe:maxNSU", default="", namespaces=ns) or "").strip()

        payloads: list[XMLProdutoPayload] = []
        warnings: list[str] = []

        for index, node in enumerate(ret.findall(".//nfe:docZip", ns), start=1):
            if len(payloads) >= max_docs:
                break

            schema = str(node.attrib.get("schema") or "nfe")
            nsu = str(node.attrib.get("NSU") or f"{index:03d}")
            encoded = (node.text or "").strip()

            if not encoded:
                continue

            try:
                compressed = base64.b64decode(encoded)
                xml_bytes = gzip.decompress(compressed)
                payloads.append(
                    XMLProdutoPayload(
                        file_name=f"{schema}_{nsu}.xml",
                        content=xml_bytes,
                    )
                )
            except Exception as exc:
                warnings.append(f"docZip NSU {nsu}: falha ao descompactar XML ({exc}).")

        return ReceitaDownloadResult(
            xml_payloads=payloads,
            status_codigo=status_codigo,
            status_mensagem=status_mensagem,
            ultimo_nsu=ultimo_nsu,
            max_nsu=max_nsu,
            warnings=warnings,
        )


@contextmanager
def _pfx_to_pem_files(bundle: CertificateBundle) -> Iterator[tuple[str, str]]:
    passphrase = bundle.password.encode("utf-8") if bundle.password else b""
    key, cert, additional = pkcs12.load_key_and_certificates(bundle.pfx_bytes, passphrase)

    if cert is None or key is None:
        raise RuntimeError("Certificado A1 invalido para autenticacao mTLS.")

    cert_bytes = cert.public_bytes(encoding=serialization.Encoding.PEM)
    key_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")

    try:
        cert_file.write(cert_bytes)
        cert_file.flush()
        key_file.write(key_bytes)
        key_file.flush()

        for item in additional or []:
            cert_file.write(item.public_bytes(encoding=serialization.Encoding.PEM))
            cert_file.flush()

        yield cert_file.name, key_file.name
    finally:
        cert_file.close()
        key_file.close()
        for path in (cert_file.name, key_file.name):
            try:
                os.remove(path)
            except OSError:
                pass


def _uf_code(uf: str) -> str:
    mapping = {
        "RO": "11",
        "AC": "12",
        "AM": "13",
        "RR": "14",
        "PA": "15",
        "AP": "16",
        "TO": "17",
        "MA": "21",
        "PI": "22",
        "CE": "23",
        "RN": "24",
        "PB": "25",
        "PE": "26",
        "AL": "27",
        "SE": "28",
        "BA": "29",
        "MG": "31",
        "ES": "32",
        "RJ": "33",
        "SP": "35",
        "PR": "41",
        "SC": "42",
        "RS": "43",
        "MS": "50",
        "MT": "51",
        "GO": "52",
        "DF": "53",
    }

    uf_code = mapping.get(uf.strip().upper(), "")
    if not uf_code:
        raise RuntimeError("UF do autor nao suportada para distribuicao DF-e.")

    return uf_code
