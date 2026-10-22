from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    inventory_bridge_journal_id = fields.Many2one(
        related="company_id.inventory_bridge_journal_id",
        readonly=False,
    )
    inventory_bridge_expense_account_id = fields.Many2one(
        related="company_id.inventory_bridge_expense_account_id",
        readonly=False,
    )
    inventory_bridge_stock_account_id = fields.Many2one(
        related="company_id.inventory_bridge_stock_account_id",
        readonly=False,
    )

