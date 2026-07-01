from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.serialization import pkcs12

from db import fetch_rows


class CertificateStoreError(Exception):
    """Erro base para operacoes de certificado digital A1."""


class CertificateMissingError(CertificateStoreError):
    """Certificado A1 nao encontrado para o cliente."""


class CertificateInvalidError(CertificateStoreError):
    """Certificado A1 invalido para uso no servico."""


@dataclass(frozen=True)
class CertificateBundle:
    """Representa certificado A1 carregado para autenticacao mTLS."""

    pfx_bytes: bytes
    password: str
    subject: str
    issuer: str
    serial_number: str
    valid_from: datetime
    valid_until: datetime


class ClienteCertificateStore:
    """Carrega certificado digital A1 ativo de um cliente no Supabase."""

    table_name = "certificados_clientes"

    def load(self, cliente_id: str) -> CertificateBundle:
        rows = fetch_rows(
            table_name=self.table_name,
            columns="*",
            eq_filters={"cliente_id": cliente_id},
            order_by="created_at",
            desc=True,
            limit=20,
        )

        if not rows:
            raise CertificateMissingError(
                "Certificado A1 nao cadastrado para o cliente."
            )

        selected = self._select_active(rows)

        pfx_base64 = str(
            selected.get("certificado_pfx_base64")
            or selected.get("certificado_pfx_b64")
            or ""
        ).strip()
        password = str(
            selected.get("senha_certificado")
            or selected.get("certificate_password")
            or ""
        )

        if not pfx_base64:
            raise CertificateInvalidError(
                "Registro de certificado sem conteudo PFX base64."
            )

        try:
            pfx_bytes = base64.b64decode(pfx_base64)
        except Exception as exc:
            raise CertificateInvalidError(
                "Certificado A1 em formato base64 invalido."
            ) from exc

        return self._validate_bundle(pfx_bytes, password)

    def _select_active(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        for row in rows:
            if row.get("ativo") is True or row.get("active") is True:
                return row
        return rows[0]

    def _validate_bundle(self, pfx_bytes: bytes, password: str) -> CertificateBundle:
        passphrase = password.encode("utf-8") if password else b""

        try:
            _, certificate, _ = pkcs12.load_key_and_certificates(pfx_bytes, passphrase)
        except Exception as exc:
            raise CertificateInvalidError(
                "Nao foi possivel abrir o PFX. Verifique senha e integridade do certificado."
            ) from exc

        if certificate is None:
            raise CertificateInvalidError("PFX sem certificado publico valido.")

        valid_from = certificate.not_valid_before
        valid_until = certificate.not_valid_after

        if valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)

        return CertificateBundle(
            pfx_bytes=pfx_bytes,
            password=password,
            subject=certificate.subject.rfc4514_string(),
            issuer=certificate.issuer.rfc4514_string(),
            serial_number=hex(certificate.serial_number),
            valid_from=valid_from,
            valid_until=valid_until,
        )


def is_certificate_expired(bundle: CertificateBundle) -> bool:
    """Retorna True quando o A1 ja ultrapassou a validade."""
    return bundle.valid_until <= datetime.now(timezone.utc)
