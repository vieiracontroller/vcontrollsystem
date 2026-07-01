-- Migration: gestao de fornecedores e vinculos de terceiros nas notas importadas

create extension if not exists pgcrypto;

create table if not exists public.fornecedores (
    id uuid primary key default gen_random_uuid(),
    razao_social text not null,
    cnpj text not null unique,
    observacoes text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_fornecedores_cnpj on public.fornecedores (cnpj);
create index if not exists idx_fornecedores_razao on public.fornecedores (lower(razao_social));

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'set_updated_at'
    ) THEN
        DROP TRIGGER IF EXISTS trg_fornecedores_updated_at ON public.fornecedores;
        CREATE TRIGGER trg_fornecedores_updated_at
        BEFORE UPDATE ON public.fornecedores
        FOR EACH ROW
        EXECUTE FUNCTION public.set_updated_at();
    END IF;
END $$;

alter table public.notas_fiscais
    add column if not exists fornecedor_id uuid references public.fornecedores(id),
    add column if not exists cliente_terceiro_id uuid references public.clientes(id),
    add column if not exists classificacao_importacao text;

alter table public.notas_servico
    add column if not exists fornecedor_id uuid references public.fornecedores(id),
    add column if not exists cliente_terceiro_id uuid references public.clientes(id),
    add column if not exists tipo_operacao text,
    add column if not exists classificacao_importacao text;

create index if not exists idx_notas_fiscais_fornecedor on public.notas_fiscais (fornecedor_id);
create index if not exists idx_notas_servico_fornecedor on public.notas_servico (fornecedor_id);
create index if not exists idx_notas_fiscais_classificacao on public.notas_fiscais (classificacao_importacao);
create index if not exists idx_notas_servico_classificacao on public.notas_servico (classificacao_importacao);
