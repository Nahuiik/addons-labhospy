# -*- coding: utf-8 -*-
"""Add apply_in_quincena column to l10n_hn_isr_employee_deduction."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    try:
        cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'l10n_hn_isr_employee_deduction'
              AND column_name = 'apply_in_quincena'
        """)
        if cr.fetchone():
            _logger.info("l10n_hn_isr_employee_deduction.apply_in_quincena already exists")
            return

        cr.execute("""
            ALTER TABLE l10n_hn_isr_employee_deduction
            ADD COLUMN apply_in_quincena VARCHAR(16) DEFAULT 'both'
        """)
        cr.execute("""
            UPDATE l10n_hn_isr_employee_deduction
            SET apply_in_quincena = 'both'
            WHERE apply_in_quincena IS NULL
        """)
        _logger.info("Added apply_in_quincena to l10n_hn_isr_employee_deduction")
    except Exception as e:
        _logger.warning("Migration apply_in_quincena: %s", e)
