# -*- coding: utf-8 -*-
from odoo import fields, models


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    move_type = fields.Selection(
        selection_add=[
            ('provision', 'Provisiones'),
            ('fx_differential', 'Diferencial cambiario (provisiones)'),
        ],
    )
