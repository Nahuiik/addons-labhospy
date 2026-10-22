# -*- coding: utf-8 -*-
# Puentes hr_payroll / hr_work_entry_enterprise / hr_payroll_account retirados del código.
def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_module_module
        SET state = 'uninstalled'
        WHERE name IN (
            'hr_payroll',
            'hr_work_entry_enterprise',
            'hr_payroll_account'
        )
        """
    )
