# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import datetime
from odoo import fields, models, api, _

class AccountAccount(models.Model):
	_inherit = 'account.account'

	current_debit_balance = fields.Float(compute='_compute_debit_credit_balance',string="Current Debit",store=True)
	current_credit_balance = fields.Float(compute='_compute_debit_credit_balance',string="Current Credit",store=True)
	move_line_ids = fields.Many2many('account.move.line')

	@api.depends_context('company')
	def _compute_debit_credit_balance(self):
		credit_balances = {
			account.id: balance
			for account, balance in self.env['account.move.line']._read_group(
				domain=[('account_id', 'in', self.ids), ('parent_state', '=', 'posted'), ('company_id', '=', self.env.company.id)],
				groupby=['account_id'],
				aggregates=['credit:sum'],
			)
		}

		debit_balances = {
			account.id: balance
			for account, balance in self.env['account.move.line']._read_group(
				domain=[('account_id', 'in', self.ids), ('parent_state', '=', 'posted'), ('company_id', '=', self.env.company.id)],
				groupby=['account_id'],
				aggregates=['debit:sum'],
			)
		}

		for record in self:
			record.current_credit_balance = credit_balances.get(record.id, 0)
			record.current_debit_balance = debit_balances.get(record.id, 0)

