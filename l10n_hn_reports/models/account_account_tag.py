# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    casilla_904 = fields.Integer(
        string='Casilla Form 904',
        help='Número de casilla del formulario SAR 904 (ISV).',
    )
