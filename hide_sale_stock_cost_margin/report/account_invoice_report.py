# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AccountInvoiceReport(models.Model):
    _inherit = 'account.invoice.report'

    price_margin = fields.Float()
