# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import fields, models


class ResBank(models.Model):
    _inherit = 'res.bank'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    bank_id = fields.Many2one(
        'res.bank',
        string='Bank',
        check_company=True,
    )
