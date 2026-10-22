# -*- coding: utf-8 -*-
"""Remove old DED_ISR_EMPLEADO salary rules (replaced by per-type rules)."""
import logging

_logger = logging.getLogger(__name__)

OLD_RULE_NAMES = [
    'salary_rule_ded_isr_empleado_monthly',
    'salary_rule_ded_isr_empleado_biweekly',
]


def migrate(cr, version):
    if not version:
        return

    for name in OLD_RULE_NAMES:
        try:
            cr.execute("""
                SELECT imd.res_id
                FROM ir_model_data imd
                WHERE imd.module = 'l10n_hn_hr_payroll'
                  AND imd.name = %s
                  AND imd.model = 'hr.salary.rule'
                  AND imd.res_id IS NOT NULL
            """, (name,))
            row = cr.fetchone()
            if row:
                rule_id = int(row[0])
                cr.execute(
                    "DELETE FROM hr_payslip_line WHERE salary_rule_id = %s",
                    (rule_id,),
                )
                cr.execute("DELETE FROM hr_salary_rule WHERE id = %s", (rule_id,))
                cr.execute("""
                    DELETE FROM ir_model_data
                    WHERE module = 'l10n_hn_hr_payroll' AND name = %s
                      AND model = 'hr.salary.rule'
                """, (name,))
                _logger.info("Removed old salary rule: %s", name)
        except Exception as e:
            _logger.warning("Could not remove %s: %s", name, e)
