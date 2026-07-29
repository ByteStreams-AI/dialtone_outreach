-- Migration: 008_normalize_lead_phone_tel_uri
-- Created: 2026-07-28
-- Description: Convert valid lead phone numbers to dialable tel: URIs

BEGIN;

CREATE TEMP TABLE normalized_lead_phones ON COMMIT DROP AS
WITH parsed AS (
    SELECT
        lead_id,
        phone,
        BTRIM(phone) AS trimmed_phone,
        REGEXP_REPLACE(
            REGEXP_REPLACE(BTRIM(phone), '^tel:\s*', '', 'i'),
            '[^0-9]',
            '',
            'g'
        ) AS digits,
        REGEXP_REPLACE(BTRIM(phone), '^tel:\s*', '', 'i') ~ '^\s*(\+|00)' AS international
    FROM leads
    WHERE phone IS NOT NULL AND BTRIM(phone) <> ''
), canonical AS (
    SELECT
        lead_id,
        phone,
        CASE
            WHEN international AND digits LIKE '00%' THEN SUBSTRING(digits FROM 3)
            ELSE digits
        END AS digits,
        international
    FROM parsed
)
SELECT
    lead_id,
    phone AS old_phone,
    CASE
        WHEN international THEN 'tel:+' || digits
        WHEN LENGTH(digits) = 10 THEN 'tel:+1' || digits
        WHEN LENGTH(digits) = 11 AND digits LIKE '1%' THEN 'tel:+' || digits
        ELSE 'tel:' || digits
    END AS new_phone
FROM canonical
WHERE LENGTH(digits) BETWEEN 3 AND 15
  AND NOT (international AND digits LIKE '0%');

DO $$
DECLARE
    duplicate_phone TEXT;
BEGIN
    SELECT new_phone
    INTO duplicate_phone
    FROM normalized_lead_phones
    GROUP BY new_phone
    HAVING COUNT(*) > 1
    LIMIT 1;

    IF duplicate_phone IS NOT NULL THEN
        RAISE EXCEPTION
            'Cannot normalize leads.phone: multiple rows map to %. Merge those leads first.',
            duplicate_phone;
    END IF;
END;
$$;

-- Clear changed values first so the existing UNIQUE constraint cannot fail
-- when one row already contains another row's canonical representation.
UPDATE leads AS lead
SET phone = NULL
FROM normalized_lead_phones AS normalized
WHERE lead.lead_id = normalized.lead_id
  AND lead.phone IS DISTINCT FROM normalized.new_phone;

UPDATE leads AS lead
SET phone = normalized.new_phone
FROM normalized_lead_phones AS normalized
WHERE lead.lead_id = normalized.lead_id
  AND lead.phone IS DISTINCT FROM normalized.new_phone;

COMMIT;