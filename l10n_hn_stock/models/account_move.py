from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    consume_id = fields.Many2one("consume.product", string="Consume Document")





