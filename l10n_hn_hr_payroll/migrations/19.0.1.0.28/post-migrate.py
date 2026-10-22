# -*- coding: utf-8 -*-
"""Migrate deduction_type (Selection) to deduction_type_id (Many2one).

Existing records have deduction_type = 'afp'|'afp_nomina'|'colegio_profesional'|'otros'.
We set deduction_type_id from the new l10n.hn.isr.deduction.type records by code.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Check if old column exists
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'l10n_hn_isr_employee_deduction'
          AND column_name = 'deduction_type'
    """)
    if not cr.fetchone():
        _logger.info("l10n_hn_isr_employee_deduction: no deduction_type column, skip migration")
        return

    # Build code -> type_id mapping
    cr.execute("SELECT id, code FROM l10n_hn_isr_deduction_type")
    code_to_id = {row[1]: row[0] for row in cr.fetchall()}

    # Update records that have old deduction_type but no deduction_type_id
    cr.execute("""
        SELECT id, deduction_type
        FROM l10n_hn_isr_employee_deduction
        WHERE deduction_type_id IS NULL
          AND deduction_type IS NOT NULL
    """)
    rows = cr.fetchall()
    updated = 0
    for ded_id, old_code in rows:
        type_id = code_to_id.get(old_code)
        if type_id:
            cr.execute(
                "UPDATE l10n_hn_isr_employee_deduction SET deduction_type_id = %s WHERE id = %s",
                (type_id, ded_id),
            )
            updated += 1
        else:
            # Fallback to 'otros' if unknown code
            type_id = code_to_id.get('otros')
            if type_id:
                cr.execute(
                    "UPDATE l10n_hn_isr_employee_deduction SET deduction_type_id = %s WHERE id = %s",
                    (type_id, ded_id),
                )
                updated += 1
                _logger.warning(
                    "l10n_hn_isr_employee_deduction id=%s: unknown deduction_type '%s', set to 'otros'",
                    ded_id, old_code,
                )

    if updated:
        _logger.info(
            "l10n_hn_isr_employee_deduction: migrated %d records from deduction_type to deduction_type_id",
            updated,
        )
