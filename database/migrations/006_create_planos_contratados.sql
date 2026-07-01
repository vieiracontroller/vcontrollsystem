-- Migration: estrutura basica para controle de licenciamento por plano

create extension if not exists pgcrypto;

create table if not exists public.planos_contratados (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    plano text not null,
    recursos jsonb not null default '[]'::jsonb,
    permite_download boolean not null default true,
    permite_apuracao boolean not null default false,
    permite_sped boolean not null default false,
    ativo boolean not null default true,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_planos_contratados_cliente on public.planos_contratados (cliente_id);
create index if not exists idx_planos_contratados_ativo on public.planos_contratados (ativo);

drop trigger if exists trg_planos_contratados_updated_at on public.planos_contratados;
create trigger trg_planos_contratados_updated_at
before update on public.planos_contratados
for each row
execute function public.set_updated_at();
