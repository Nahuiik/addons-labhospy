# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    branch_id = fields.Many2one('res.branch', 'Branch')

    def _select(self):
        return SQL('%s, line.branch_id', super()._select())
