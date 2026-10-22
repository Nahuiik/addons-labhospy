# -*- coding: utf-8 -*-
# hr.payslip.run: estado histórico "close" → "done" (flujo alineado a borrador / hecho / pagado).


def migrate(cr, version):
    cr.execute(
        """
        UPDATE hr_payslip_run
        SET state = 'done'
        WHERE state = 'close'
        """
    )
