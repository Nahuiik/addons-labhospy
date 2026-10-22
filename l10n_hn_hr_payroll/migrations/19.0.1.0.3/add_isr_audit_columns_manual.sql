-- Ejecutar manualmente si la migración no corre: añade las columnas faltantes a l10n_hn_isr_audit
-- Uso: psql -d TU_BASE -f add_isr_audit_columns_manual.sql

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'l10n_hn_isr_audit' AND column_name = 'salary_annual'
    ) THEN
        ALTER TABLE l10n_hn_isr_audit ADD COLUMN salary_annual NUMERIC(12,2);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'l10n_hn_isr_audit' AND column_name = 'excess_vacations'
    ) THEN
        ALTER TABLE l10n_hn_isr_audit ADD COLUMN excess_vacations NUMERIC(12,2);
    END IF;
END $$;
