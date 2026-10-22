# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    banks_accrual_provision_journal_id = fields.Many2one(
        related='company_id.banks_accrual_provision_journal_id',
        readonly=False,
    )
    banks_fx_differential_journal_id = fields.Many2one(
        related='company_id.banks_fx_differential_journal_id',
        readonly=False,
    )
