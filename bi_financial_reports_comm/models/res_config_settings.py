# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bi_totals_below_sections = fields.Boolean(
        related="company_id.bi_totals_below_sections",
        readonly=False,
    )
