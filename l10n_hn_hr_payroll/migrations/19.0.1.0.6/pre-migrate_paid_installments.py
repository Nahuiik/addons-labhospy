# -*- coding: utf-8 -*-
# Migración: Añadir manual_paid_installments y first_deduction_date.
# Copiar paid_installments a manual_paid_installments antes de que paid_installments
# pase a ser campo computado.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    table = 'hr_employee_recurring_concept'
    try:
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'manual_paid_installments'
            """,
            (table,),
        )
        if cr.fetchone():
            _logger.info("Column manual_paid_installments already exists in %s", table)
        else:
            cr.execute(
                f'ALTER TABLE "{table}" ADD COLUMN manual_paid_installments INTEGER DEFAULT 0'
            )
            cr.execute(
                f'UPDATE "{table}" SET manual_paid_installments = paid_installments'
            )
            _logger.info("Migrated paid_installments to manual_paid_installments")

        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'first_deduction_date'
            """,
            (table,),
        )
        if cr.fetchone():
            _logger.info("Column first_deduction_date already exists in %s", table)
        else:
            cr.execute(
                f'ALTER TABLE "{table}" ADD COLUMN first_deduction_date DATE'
            )
            _logger.info("Added first_deduction_date column")
    except Exception as e:
        _logger.warning("Migration %s: %s", table, e)
