# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class HrPayslipInput(models.Model):
    _inherit = "hr.payslip.input"

    recurring_concept_id = fields.Many2one(
        "hr.employee.recurring.concept",
        string="Concepto recurrente",
        index=True,
        ondelete="set null",
        copy=False,
    )
