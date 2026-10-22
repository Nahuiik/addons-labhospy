from odoo import models, fields, api, _

class CapPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    number_of_asset_ids = fields.Integer(compute="compute_asset_ids")

    def action_show_assets(self):
        action = {
            'type': 'ir.actions.act_window',
            'name': _("%(name)s's all assets", name=self.name),
            'res_model': 'account.asset',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.mapped('order_line').mapped('invoice_lines').mapped('asset_ids').ids)],
            'target': 'current'
        }
        return action

    def compute_asset_ids(self):
        self.number_of_asset_ids = 0
        if self and self.order_line and (self.mapped('order_line').mapped('invoice_lines') and (self.mapped('order_line').mapped('invoice_lines').mapped('asset_ids'))):
            self.number_of_asset_ids = len(self.mapped('order_line').mapped('invoice_lines').mapped('asset_ids').ids)