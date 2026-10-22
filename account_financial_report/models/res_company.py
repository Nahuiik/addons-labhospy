from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    age_partner_config_id = fields.Many2one(
        "account.age.report.configuration",
        string="Default aged partner configuration",
        help="Configuration used as default for the aged partner balance wizard.",
    )
