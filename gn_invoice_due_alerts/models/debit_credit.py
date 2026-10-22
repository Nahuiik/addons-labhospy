# -*- coding: utf-8 -*-
from odoo import fields, models


class DebitCredit(models.Model):
    _inherit = 'debit.credit'

    loan_id = fields.Many2one(
        'gn.bank.loan', string='Prestamo',
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]")
