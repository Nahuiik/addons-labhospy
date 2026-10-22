from odoo import fields, models


class AccountAssetAsset(models.Model):
    _name = "account.asset.asset"
    _inherit = ["account.asset.asset", "mail.activity.mixin"]

    name = fields.Char(tracking=True)
    code = fields.Char(tracking=True)
    category_id = fields.Many2one(tracking=True)
    date = fields.Date(tracking=True)
    value = fields.Float(tracking=True)
    salvage_value = fields.Float(tracking=True)
    method = fields.Selection(tracking=True)
    method_number = fields.Integer(tracking=True)
    method_period = fields.Integer(tracking=True)
    method_time = fields.Selection(tracking=True)
    method_end = fields.Date(tracking=True)
    state = fields.Selection(tracking=True)
    partner_id = fields.Many2one(tracking=True)
    invoice_id = fields.Many2one(tracking=True)
