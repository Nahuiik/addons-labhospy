from odoo import models, api


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def cur_user_has_group_js(self, group_id):
        return self.env.user.has_group(group_id)
