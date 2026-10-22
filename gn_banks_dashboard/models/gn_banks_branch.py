# -*- coding: utf-8 -*-
"""Sucursal en documentos gn_banks (requerido por el dashboard de tesorería)."""

from odoo import fields, models


class DebitCreditBranch(models.Model):
    _inherit = 'debit.credit'

    branch_id = fields.Many2one(
        'res.branch',
        string='Branch',
        default=lambda self: self.env.user.branch_id.id or False,
        tracking=42,
    )


class BankCheckBranch(models.Model):
    _inherit = 'bank.check'

    branch_id = fields.Many2one(
        'res.branch',
        string='Branch',
        default=lambda self: self.env.user.branch_id.id or False,
        tracking=42,
    )


class BankTransferBranch(models.Model):
    _inherit = 'bank.transfer'

    branch_id = fields.Many2one(
        'res.branch',
        string='Branch',
        default=lambda self: self.env.user.branch_id.id or False,
        tracking=42,
    )
