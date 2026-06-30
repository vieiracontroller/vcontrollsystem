-- Migration: adiciona campos de conformidade para reforma tributaria em produtos

alter table public.produtos
    add column if not exists cfop_padrao text,
    add column if not exists cst_icms text,
    add column if not exists aliquota_ibs numeric(7,4) not null default 0,
    add column if not exists aliquota_cbs numeric(7,4) not null default 0;

-- Constraints para qualidade de dados fiscais
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_ncm_format'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_ncm_format
            CHECK (ncm IS NULL OR ncm ~ '^[0-9]{8}$');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_cest_format'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_cest_format
            CHECK (cest IS NULL OR cest = '' OR cest ~ '^[0-9]{7}$');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_cfop_format'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_cfop_format
            CHECK (cfop_padrao IS NULL OR cfop_padrao = '' OR cfop_padrao ~ '^[0-9]{4}$');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_cst_icms_format'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_cst_icms_format
            CHECK (cst_icms IS NULL OR cst_icms = '' OR cst_icms ~ '^[0-9]{2,3}$');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_aliquota_icms_range'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_aliquota_icms_range
            CHECK (aliquota_padrao_icms >= 0 AND aliquota_padrao_icms <= 100);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_aliquota_ibs_range'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_aliquota_ibs_range
            CHECK (aliquota_ibs >= 0 AND aliquota_ibs <= 100);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_aliquota_cbs_range'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_aliquota_cbs_range
            CHECK (aliquota_cbs >= 0 AND aliquota_cbs <= 100);
    END IF;
END $$;

create index if not exists idx_produtos_cfop on public.produtos (cfop_padrao);
