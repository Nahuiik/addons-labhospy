# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrEmployeeRecurringConceptHn(models.Model):
    _inherit = 'hr.employee.recurring.concept'

    payroll_sheet_line_bd_id = fields.Many2one(
        'l10n.hn.payroll.line.bd',
        string='Origen Planilla BD',
        ondelete='set null',
        readonly=True,
        help='Línea de planilla que creó este concepto (para reversión)',
    )
