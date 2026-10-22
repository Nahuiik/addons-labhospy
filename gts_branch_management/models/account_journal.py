# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    branch_id = fields.Many2one(
        'res.branch',
        string='Sucursal',
        help='Sucursal asignada a este diario (opcional). Diarios sin sucursal están disponibles para todas.',
    )
