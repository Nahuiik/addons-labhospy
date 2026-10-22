# -*- coding: utf-8 -*-
# En Enterprise el campo `unique_import_id` lo añade `account_bank_statement_import`.
# En Community lo define este módulo (evitar duplicados al importar).
from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    unique_import_id = fields.Char(string='Import ID', readonly=True, copy=False, index='btree_not_null')

    _gn_qif_unique_import = models.Constraint(
        'unique (unique_import_id)',
        "Una transacción bancaria con este identificador de importación ya existe.",
    )
