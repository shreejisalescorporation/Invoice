BEGIN;

ALTER TABLE public.customer
    ADD COLUMN IF NOT EXISTS customer_id uuid,
    ADD COLUMN IF NOT EXISTS customer_type text,
    ADD COLUMN IF NOT EXISTS gst_number text,
    ADD COLUMN IF NOT EXISTS address_line_1 text,
    ADD COLUMN IF NOT EXISTS address_line_2 text,
    ADD COLUMN IF NOT EXISTS area_landmark text,
    ADD COLUMN IF NOT EXISTS city_village_district text,
    ADD COLUMN IF NOT EXISTS state text,
    ADD COLUMN IF NOT EXISTS pincode text,
    ADD COLUMN IF NOT EXISTS mobile text,
    ADD COLUMN IF NOT EXISTS email text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz;

UPDATE public.customer
SET customer_id = COALESCE(customer_id, gen_random_uuid()),
    customer_type = CASE
        WHEN NULLIF(BTRIM(gst), '') IS NULL OR UPPER(BTRIM(gst)) LIKE 'RETAIL%'
            THEN 'retail'
        ELSE 'business'
    END,
    gst_number = CASE
        WHEN NULLIF(BTRIM(gst), '') IS NULL OR UPPER(BTRIM(gst)) LIKE 'RETAIL%'
            THEN NULL
        ELSE UPPER(BTRIM(gst))
    END,
    address_line_1 = COALESCE(
        NULLIF(BTRIM(address_line_1), ''),
        NULLIF(BTRIM(address), '')
    ),
    created_at = COALESCE(created_at, NOW());

ALTER TABLE public.customer
    ALTER COLUMN customer_id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN customer_id SET NOT NULL,
    ALTER COLUMN customer_type SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN created_at SET NOT NULL;

DO $$
DECLARE
    constraint_row record;
BEGIN
    FOR constraint_row IN
        SELECT conrelid::regclass AS relation_name, conname
        FROM pg_constraint
        WHERE contype = 'f'
          AND confrelid = 'public.customer'::regclass
    LOOP
        EXECUTE format(
            'ALTER TABLE %s DROP CONSTRAINT %I',
            constraint_row.relation_name,
            constraint_row.conname
        );
    END LOOP;

    FOR constraint_row IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.customer'::regclass
          AND contype = 'p'
    LOOP
        EXECUTE format(
            'ALTER TABLE public.customer DROP CONSTRAINT %I',
            constraint_row.conname
        );
    END LOOP;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'invoice_data'
          AND column_name = 'gst'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'invoice_data'
          AND column_name = 'gst_number'
    ) THEN
        ALTER TABLE public.invoice_data RENAME COLUMN gst TO gst_number;
    END IF;
END $$;

ALTER TABLE public.invoice_data
    ADD COLUMN IF NOT EXISTS customer_id uuid,
    ADD COLUMN IF NOT EXISTS gst_number text;

UPDATE public.invoice_data AS invoice
SET customer_id = customer.customer_id,
    gst_number = CASE
        WHEN customer.customer_type = 'retail' THEN NULL
        ELSE customer.gst_number
    END
FROM public.customer AS customer
WHERE invoice.customer_id IS NULL
  AND invoice.gst_number = customer.gst;

ALTER TABLE public.invoice_data
    ALTER COLUMN gst_number DROP NOT NULL;

ALTER TABLE public.customer
    ADD CONSTRAINT customer_pkey PRIMARY KEY (customer_id);

ALTER TABLE public.customer
    DROP CONSTRAINT IF EXISTS customer_customer_type_check,
    ADD CONSTRAINT customer_customer_type_check
        CHECK (customer_type IN ('business', 'retail')),
    DROP CONSTRAINT IF EXISTS customer_gst_type_check,
    ADD CONSTRAINT customer_gst_type_check
        CHECK (
            (customer_type = 'business' AND gst_number IS NOT NULL)
            OR (customer_type = 'retail' AND gst_number IS NULL)
        ),
    DROP CONSTRAINT IF EXISTS customer_pincode_check,
    ADD CONSTRAINT customer_pincode_check
        CHECK (pincode IS NULL OR pincode ~ '^[0-9]{6}$');

CREATE UNIQUE INDEX IF NOT EXISTS customer_gst_number_unique
    ON public.customer (gst_number)
    WHERE gst_number IS NOT NULL;

ALTER TABLE public.invoice_data
    ADD CONSTRAINT invoice_data_customer_id_fkey
        FOREIGN KEY (customer_id)
        REFERENCES public.customer (customer_id)
        ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS invoice_data_customer_id_idx
    ON public.invoice_data (customer_id);

ALTER TABLE public.customer
    DROP COLUMN IF EXISTS gst,
    DROP COLUMN IF EXISTS address;

COMMIT;
