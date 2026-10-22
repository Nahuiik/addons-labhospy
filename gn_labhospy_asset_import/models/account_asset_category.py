from odoo import fields, models


class AccountAssetCategory(models.Model):
    _name = "account.asset.category"
    _inherit = ["account.asset.category", "mail.thread", "mail.activity.mixin"]

    name = fields.Char(tracking=True)
    account_asset_id = fields.Many2one(tracking=True)
    account_depreciation_id = fields.Many2one(tracking=True)
    account_depreciation_expense_id = fields.Many2one(tracking=True)
    journal_id = fields.Many2one(tracking=True)
    method = fields.Selection(tracking=True)
    method_time = fields.Selection(tracking=True)
    method_number = fields.Integer(tracking=True)
    method_period = fields.Integer(tracking=True)
    method_progress_factor = fields.Float(tracking=True)
    prorata = fields.Boolean(tracking=True)
    open_asset = fields.Boolean(tracking=True)
    group_entries = fields.Boolean(tracking=True)
