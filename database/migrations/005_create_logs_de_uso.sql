-- Migration: cria tabela de auditoria de uso do motor de servicos (SaaS billing)

create extension if not exists pgcrypto;

create table if not exists public.logs_de_uso (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    solicitante text,
    origem text not null default 'api_interna',
    operacao text not null,
    status text not null,
    detalhe text,
    custo numeric(12,2),
    quantidade_documentos integer not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    started_at timestamptz,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_logs_de_uso_cliente on public.logs_de_uso (cliente_id);
create index if not exists idx_logs_de_uso_operacao on public.logs_de_uso (operacao);
create index if not exists idx_logs_de_uso_created_at on public.logs_de_uso (created_at desc);
create index if not exists idx_logs_de_uso_status on public.logs_de_uso (status);
