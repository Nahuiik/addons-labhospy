# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    banks_require_approval = fields.Boolean(
        related='company_id.banks_require_approval',
        readonly=False,
    )
