# -*- coding: utf-8 -*-
"""
Odoo Proprietary License v1.0.

see License:
https://www.odoo.com/documentation/user/14.0/legal/licenses/licenses.html#odoo-apps
# Copyright ©2022 Bernard K. Too<bernard.too@optima.co.ke>
"""

from odoo import api, fields, models


class PaymentTemplates(models.Model):
    _inherit = "account.payment"

    @api.onchange("partner_id")
    def onchange_partner_style(self):
        self.style = (
            self.partner_id.style
            or self.env.user.company_id.df_style
            or self.env.ref("professional_templates.df_style_for_all_reports")
        )

    @api.model
    def create(self, vals):
        res = super(PaymentTemplates, self).create(vals)
        if res:  # trigger onchage after creating a payment to update the partner style
            res.onchange_partner_style()
        return res

    style = fields.Many2one(
        "report.template.settings",
        "Receipt Style",
        default=lambda self: self.partner_id.style or self.env.user.company_id.df_style,
    )

