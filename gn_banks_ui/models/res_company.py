# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    banks_require_approval = fields.Boolean(
        string='Requerir aprobación de tesorería para operaciones bancarias',
        default=False,
        help='Si está activo, las operaciones bancarias deben enviarse y aprobarse antes de validarse.',
    )
