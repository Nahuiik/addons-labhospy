# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

M2X_BOOLEAN_PARAMS = {
    "m2x_create": "web_m2x_options.create",
    "m2x_create_edit": "web_m2x_options.create_edit",
    "m2x_open": "web_m2x_options.open",
    "m2x_search_more": "web_m2x_options.search_more",
}

M2X_INTEGER_PARAMS = {
    "m2x_limit": "web_m2x_options.limit",
    "m2x_field_limit_entries": "web_m2x_options.field_limit_entries",
}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    m2x_create = fields.Boolean(
        string="Allow 'Create' in dropdowns",
        default=True,
    )
    m2x_create_edit = fields.Boolean(
        string="Allow 'Create and Edit...' in dropdowns",
        default=True,
    )
    m2x_open = fields.Boolean(
        string="Allow 'Open' in dropdowns",
        default=True,
    )
    m2x_search_more = fields.Boolean(
        string="Always show 'Search More...'",
    )
    m2x_limit = fields.Integer(
        string="Dropdown record limit",
        config_parameter="web_m2x_options.limit",
        default=8,
    )
    m2x_field_limit_entries = fields.Integer(
        string="One2many subview line limit",
        config_parameter="web_m2x_options.field_limit_entries",
        default=0,
    )

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        for field_name, param_key in M2X_BOOLEAN_PARAMS.items():
            ICP.set_param(param_key, str(self[field_name]))

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        for field_name, param_key in M2X_BOOLEAN_PARAMS.items():
            val = ICP.get_param(param_key, default=None)
            if val is not None:
                res[field_name] = val == "True"
        return res
