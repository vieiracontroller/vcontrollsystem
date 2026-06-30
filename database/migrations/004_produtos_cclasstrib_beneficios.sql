-- Migration: adiciona cClassTrib e beneficios fiscais por NCM na tabela produtos

alter table public.produtos
    add column if not exists cclasstrib text,
    add column if not exists beneficios_fiscais jsonb not null default '[]'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_cclasstrib_format'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_cclasstrib_format
            CHECK (cclasstrib IS NULL OR cclasstrib = '' OR cclasstrib ~ '^[A-Z0-9]{2,10}$');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_produtos_beneficios_json_array'
    ) THEN
        ALTER TABLE public.produtos
            ADD CONSTRAINT ck_produtos_beneficios_json_array
            CHECK (jsonb_typeof(beneficios_fiscais) = 'array');
    END IF;
END $$;

create index if not exists idx_produtos_cclasstrib on public.produtos (cclasstrib);
