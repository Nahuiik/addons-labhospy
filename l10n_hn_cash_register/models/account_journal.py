# -*- coding: utf-8 -*-
from odoo import fields, models

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_purchase = fields.Boolean(
        string='Purchase Bank Journal',
        help='Activa esta opción para solicitar información de cheque al registrar pagos desde este diario.'
    )
