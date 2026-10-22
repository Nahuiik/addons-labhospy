# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    payslip_report_template = fields.Selection(
        related="company_id.payslip_report_template",
        readonly=False,
    )
