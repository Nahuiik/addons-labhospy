# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class HrPayrollStructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    max_advance_percentage = fields.Float(
        string="Anticipo: % máximo",
        digits=(5, 2),
        default=0.0,
        help="Tope de anticipo como porcentaje sobre la base indicada. "
             "0 = sin límite por porcentaje (solo otras validaciones).",
    )
    advance_max_base = fields.Selection(
        selection=[
            ("contract_gross", "Neto estimado del período (bruto − deducciones recurrentes)"),
            ("last_payslip_net", "Neto de la última nómina cerrada (línea NET)"),
        ],
        string="Base del tope de anticipo",
        default="contract_gross",
        required=True,
        help="Define la base sobre la que se aplica el porcentaje máximo de anticipo.",
    )
    min_days_advance = fields.Integer(
        string="Anticipo: días mínimos desde último pago",
        default=0,
        help="Días desde el fin del último período de nómina pagado para permitir una nueva solicitud. "
             "0 = sin restricción.",
    )
