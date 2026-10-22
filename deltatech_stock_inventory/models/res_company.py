from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    inventory_bridge_journal_id = fields.Many2one(
        "account.journal",
        string="Inventory Bridge Journal",
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
        help="Journal used to record inventory valuation adjustments generated from the stock-accounting bridge.",
    )
    inventory_bridge_expense_account_id = fields.Many2one(
        "account.account",
        string="Inventory Variation Account",
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
        help="Expense or variation account that receives the debit/credit when generating valuation entries.",
    )
    inventory_bridge_stock_account_id = fields.Many2one(
        "account.account",
        string="Inventory Valuation Account",
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
        help="Balance sheet account used on the opposite line of the valuation adjustment.",
    )

