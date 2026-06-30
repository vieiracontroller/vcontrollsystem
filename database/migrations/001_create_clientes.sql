-- Migration: cria estrutura inicial da tabela de clientes
-- Objetivo: suportar cadastro de clientes com campos JSONB para endereco e socios.

create extension if not exists pgcrypto;

create table if not exists public.clientes (
    id uuid primary key default gen_random_uuid(),
    razao_social text not null check (char_length(trim(razao_social)) > 0),
    cnpj text not null unique check (cnpj ~ '^[0-9]{14}$'),
    endereco jsonb not null default '{}'::jsonb,
    regime_tributario text not null check (regime_tributario in ('Simples Nacional', 'Presumido', 'Real')),
    socios jsonb not null default '[]'::jsonb,
    observacoes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_clientes_cnpj on public.clientes (cnpj);
create index if not exists idx_clientes_razao_social on public.clientes (lower(razao_social));

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists trg_clientes_updated_at on public.clientes;
create trigger trg_clientes_updated_at
before update on public.clientes
for each row
execute function public.set_updated_at();
