# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    salary_advance_journal_id = fields.Many2one(
        related="company_id.salary_advance_journal_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank', 'cash'))]",
    )
    salary_advance_debit_account_id = fields.Many2one(
        related="company_id.salary_advance_debit_account_id",
        readonly=False,
    )
    salary_advance_credit_account_id = fields.Many2one(
        related="company_id.salary_advance_credit_account_id",
        readonly=False,
    )
