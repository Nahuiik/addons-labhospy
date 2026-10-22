# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class HrContractType(models.Model):
    _inherit = 'hr.contract.type'

    is_permanent = fields.Boolean(
        string='Permanente',
        default=True,
        help='Marque si este tipo de contrato es permanente. Desmárquelo para contratos temporales.'
    )
