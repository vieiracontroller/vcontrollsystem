-- Migration: armazena apenas referencia segura do certificado A1 (sem PFX/senha em texto puro)

create extension if not exists pgcrypto;

create table if not exists public.certificados_a1_referencias (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    certificado_sha256 text not null,
    senha_hash text not null,
    subject text,
    issuer text,
    serial_number text,
    valid_until timestamptz,
    origem text not null default 'fiscal_puxador_ui',
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_cert_a1_ref_cliente on public.certificados_a1_referencias (cliente_id);
create index if not exists idx_cert_a1_ref_cert_hash on public.certificados_a1_referencias (certificado_sha256);
