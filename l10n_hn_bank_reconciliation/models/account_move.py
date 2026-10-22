# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    is_reconciled = fields.Boolean("Conciliado")
    

class AccountMove(models.Model):
    _inherit = "account.move"
    
    dummy_account_id = fields.Many2one('account.account', related='line_ids.account_id', string='Account', store=False, readonly=True)
    is_reconciled = fields.Boolean("Conciliado")
    reconciliation_id = fields.Many2one("bank.reconciliation", "Conciliación")
    