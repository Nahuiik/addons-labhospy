# -*- coding: utf-8 -*-
from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    gn_for_employee_portal = fields.Boolean(
        string='Es para portal',
        default=True,
        help='Si está activo, el tipo de ausencia se muestra en el portal del empleado '
             '(nueva solicitud, resumen en inicio y calendario personal).',
    )
