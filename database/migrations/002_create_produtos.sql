-- Migration: cria tabela de produtos para cadastro inteligente via XML

create extension if not exists pgcrypto;

create table if not exists public.produtos (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    codigo_interno text not null,
    descricao text not null,
    ncm text,
    cest text,
    unidade_medida text,
    aliquota_padrao_icms numeric(7,4) not null default 0,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint uq_produtos_cliente_codigo unique (cliente_id, codigo_interno)
);

create index if not exists idx_produtos_cliente on public.produtos (cliente_id);
create index if not exists idx_produtos_ncm on public.produtos (ncm);

drop trigger if exists trg_produtos_updated_at on public.produtos;
create trigger trg_produtos_updated_at
before update on public.produtos
for each row
execute function public.set_updated_at();
