# -*- coding: utf-8 -*-
# Migración: Reemplazar first_deduction_date por initial_paid_installments.
# Elimina first_deduction_date y añade initial_paid_installments para préstamos
# que iniciaron antes de que el empleado fuera incluido en nómina.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    table = 'hr_employee_recurring_concept'
    try:
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'initial_paid_installments'
            """,
            (table,),
        )
        if cr.fetchone():
            _logger.info("Column initial_paid_installments already exists in %s", table)
        else:
            cr.execute(
                f'ALTER TABLE "{table}" ADD COLUMN initial_paid_installments INTEGER DEFAULT 0'
            )
            _logger.info("Added initial_paid_installments column")

        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'first_deduction_date'
            """,
            (table,),
        )
        if cr.fetchone():
            cr.execute(f'ALTER TABLE "{table}" DROP COLUMN first_deduction_date')
            _logger.info("Dropped first_deduction_date column")
    except Exception as e:
        _logger.warning("Migration %s: %s", table, e)
