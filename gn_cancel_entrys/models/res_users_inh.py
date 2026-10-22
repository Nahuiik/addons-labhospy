from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    cancel_entrys = fields.Boolean(string='Allow Cancel Entry', compute='_compute_cancel_entrys')

    def _compute_cancel_entrys(self):
        manager_group = self.env.ref('gn_cancel_entrys.group_cancel_entries_manager')
        for user in self:
            user.cancel_entrys = manager_group in user.groups_id
