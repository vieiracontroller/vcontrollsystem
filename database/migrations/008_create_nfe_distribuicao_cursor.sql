-- Migration: controle de NSU por cliente para consultas incrementais na distribuicao DF-e

create extension if not exists pgcrypto;

create table if not exists public.nfe_distribuicao_cursor (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    ambiente text not null default 'producao',
    ult_nsu text not null default '000000000000000',
    max_nsu text,
    updated_at timestamptz not null default timezone('utc', now()),
    created_at timestamptz not null default timezone('utc', now()),
    constraint uq_nfe_distribuicao_cursor unique (cliente_id, ambiente)
);

create index if not exists idx_nfe_distribuicao_cursor_cliente on public.nfe_distribuicao_cursor (cliente_id);

-- Trigger opcional para manter updated_at coerente
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'set_updated_at'
    ) THEN
        DROP TRIGGER IF EXISTS trg_nfe_distribuicao_cursor_updated_at ON public.nfe_distribuicao_cursor;
        CREATE TRIGGER trg_nfe_distribuicao_cursor_updated_at
        BEFORE UPDATE ON public.nfe_distribuicao_cursor
        FOR EACH ROW
        EXECUTE FUNCTION public.set_updated_at();
    END IF;
END $$;
