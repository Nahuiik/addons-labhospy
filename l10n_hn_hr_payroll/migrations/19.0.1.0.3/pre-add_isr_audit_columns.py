# -*- coding: utf-8 -*-
# Add salary_annual and excess_vacations to l10n_hn_isr_audit if missing

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add salary_annual and excess_vacations columns to l10n_hn_isr_audit if they don't exist."""
    # First check if the table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'l10n_hn_isr_audit'
        )
    """)
    table_exists = cr.fetchone()[0]
    
    if not table_exists:
        _logger.info("Table l10n_hn_isr_audit does not exist, skipping column addition")
        return
    
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'l10n_hn_isr_audit'
        AND column_name IN ('salary_annual', 'excess_vacations')
    """)
    existing = {row[0] for row in cr.fetchall()}

    if 'salary_annual' not in existing:
        cr.execute("ALTER TABLE l10n_hn_isr_audit ADD COLUMN salary_annual NUMERIC(12,2)")
        _logger.info("Added column l10n_hn_isr_audit.salary_annual")

    if 'excess_vacations' not in existing:
        cr.execute("ALTER TABLE l10n_hn_isr_audit ADD COLUMN excess_vacations NUMERIC(12,2)")
        _logger.info("Added column l10n_hn_isr_audit.excess_vacations")
