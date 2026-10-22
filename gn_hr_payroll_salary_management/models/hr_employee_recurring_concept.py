# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class HrEmployeeRecurringConcept(models.Model):
    _inherit = "hr.employee.recurring.concept"

    salary_advance_id = fields.Many2one(
        "salary.advance",
        string="Anticipo salarial origen",
        ondelete="set null",
        readonly=True,
        copy=False,
        help="Solicitud de anticipo que generó esta deducción recurrente.",
    )
