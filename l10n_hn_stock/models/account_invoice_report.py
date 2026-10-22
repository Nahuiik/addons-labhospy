from odoo import fields, models


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    price_margin = fields.Float(
        string="Margin",
    )





