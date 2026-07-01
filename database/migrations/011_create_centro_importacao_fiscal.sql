-- Migration: centralizacao da importacao fiscal em tabelas unificadas

create extension if not exists pgcrypto;

create table if not exists public.notas_fiscais (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    tipo_documento text not null default 'NFE',
    tipo_operacao text not null,
    numero text,
    serie text,
    chave_acesso text,
    data_emissao date,
    cnpj_emitente text,
    cnpj_destinatario text,
    valor_total numeric(14,2) not null default 0,
    arquivo text not null,
    xml_base64 text,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_notas_fiscais_cliente on public.notas_fiscais (cliente_id);
create index if not exists idx_notas_fiscais_data on public.notas_fiscais (data_emissao);
create index if not exists idx_notas_fiscais_operacao on public.notas_fiscais (tipo_operacao);

create table if not exists public.notas_servico (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    numero text,
    data_emissao date,
    cnpj_prestador text,
    cnpj_tomador text,
    valor_servicos numeric(14,2) not null default 0,
    arquivo text not null,
    xml_base64 text,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_notas_servico_cliente on public.notas_servico (cliente_id);
create index if not exists idx_notas_servico_data on public.notas_servico (data_emissao);
