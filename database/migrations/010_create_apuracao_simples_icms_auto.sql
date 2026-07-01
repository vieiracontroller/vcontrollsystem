-- Migration: suporte a apuracao Simples estilo e-CAC e automacao de ICMS

create extension if not exists pgcrypto;

create table if not exists public.fiscal_nfe_xml_cache (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    arquivo text not null,
    data_emissao date,
    tipo_operacao text,
    cnpj_emitente text,
    cnpj_destinatario text,
    valor_total numeric(14,2) not null default 0,
    xml_base64 text,
    criado_em timestamptz not null default timezone('utc', now())
);

create index if not exists idx_nfe_cache_cliente on public.fiscal_nfe_xml_cache (cliente_id);
create index if not exists idx_nfe_cache_data on public.fiscal_nfe_xml_cache (data_emissao);

create table if not exists public.apuracoes_simples (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    mes integer not null check (mes between 1 and 12),
    ano integer not null check (ano between 2020 and 2100),
    regime_tributario text,
    receita_bruta_periodo numeric(14,2) not null default 0,
    receita_bruta_12m numeric(14,2) not null default 0,
    folha_12m numeric(14,2) not null default 0,
    fator_r numeric(10,6) not null default 0,
    anexo_servicos_recomendado text,
    payload_declaracao jsonb not null default '{}'::jsonb,
    memoria_calculo jsonb not null default '[]'::jsonb,
    total_das numeric(14,2) not null default 0,
    status text not null default 'PRONTO_CONFERENCIA',
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_apuracoes_simples_cliente_periodo on public.apuracoes_simples (cliente_id, ano, mes);

create table if not exists public.pendencias_classificacao_fiscal (
    id uuid primary key default gen_random_uuid(),
    cliente_id uuid not null references public.clientes(id) on delete cascade,
    nota_id text,
    arquivo text,
    ncm text,
    cst_csosn text,
    status text not null default 'Pendente de Classificacao Fiscal',
    motivo text,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_pendencias_fiscal_cliente on public.pendencias_classificacao_fiscal (cliente_id);
create index if not exists idx_pendencias_fiscal_status on public.pendencias_classificacao_fiscal (status);

create table if not exists public.tabela_icms_2026 (
    id uuid primary key default gen_random_uuid(),
    ncm text not null,
    uf_origem text,
    uf_destino text,
    aliquota_interna_destino numeric(7,4) not null,
    aliquota_interestadual numeric(7,4) not null,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_tabela_icms_2026_ncm on public.tabela_icms_2026 (ncm);
create index if not exists idx_tabela_icms_2026_ufs on public.tabela_icms_2026 (uf_origem, uf_destino);
