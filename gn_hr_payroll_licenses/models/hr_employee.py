# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    license_ids = fields.One2many(
        "hr.employee.license",
        "employee_id",
        string="Licencias de Conducir",
    )
