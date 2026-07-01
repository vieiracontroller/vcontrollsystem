-- Migration: certificados A1 por cliente para autenticacao de download NF-e

create extension if not exists pgcrypto;

create table if not exists public.certificados_clientes (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    apelido text,
    certificado_pfx_base64 text not null,
    senha_certificado text not null,
    subject text,
    issuer text,
    serial_number text,
    valid_from timestamptz,
    valid_until timestamptz,
    ativo boolean not null default true,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_certificados_clientes_cliente on public.certificados_clientes (cliente_id);
create index if not exists idx_certificados_clientes_ativo on public.certificados_clientes (ativo);

drop trigger if exists trg_certificados_clientes_updated_at on public.certificados_clientes;
create trigger trg_certificados_clientes_updated_at
before update on public.certificados_clientes
for each row
execute function public.set_updated_at();
