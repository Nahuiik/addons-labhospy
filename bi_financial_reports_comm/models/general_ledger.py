# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from datetime import datetime
from odoo.tools.misc import formatLang
from odoo import fields, models, api, _

class GeneralLedgerReport(models.Model):
	_name = 'general.ledger.report'
	_description = 'General Ledger Report'


	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string = 'Date To')
	journal_ids = fields.Many2many('account.journal',string='Journal')
	account_ids = fields.Many2many('account.account',string='Account')
	display_account = fields.Selection([('all', 'All'), ('movement', 'With movements'),
									('not_zero', 'With balance is not equal to 0'), ],
									string='Display Accounts', required=True, default='movement')
	target_move = fields.Selection([('posted', 'All Posted Entries'),
									('all', 'All Entries'),
									], string='Target Moves', required=True, default='all')

	analytic_account_ids = fields.Many2many('account.analytic.account', string="Analytic Accounts")
	partner_ids = fields.Many2many('res.partner', string="Partner")
	

	def action_apply_filters_general(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'display_account':self.display_account,
			'target_move':self.target_move,
			'analytic_account_ids':self.analytic_account_ids.ids if self.analytic_account_ids else None,
			'date_from':self.date_from,
			'date_to':self.date_to,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'partner_ids':self.partner_ids.ids if self.partner_ids else None,
			'account_ids':self.account_ids.ids if self.account_ids else None,
		}
		records = self.with_context(context).get_data_general_ledger()
		return {
			"type": "ir.actions.client",
			"tag": "bi_account_report",
			"name": "General Ledger",
			"context": {"report_type": "general_ledger"},
			"params": {
				"filtered_records": records if records else [],
			},
			"target": "current",
		}

	@api.model
	def get_data_general_ledger(self, balance_account_id=None):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		domain = []
		total_balance = 0.0
		total_credit = 0.0
		total_debit = 0.0
	
		display_account = context.get("display_account", "movement") or existing_record.display_account
		target_move = context.get("target_move", "all") or existing_record.target_move
		analytic_account_ids = context.get("analytic_account_ids", []) or existing_record.analytic_account_ids.ids
		date_from = context.get("date_from") or existing_record.date_from
		date_to = context.get("date_to") or existing_record.date_to
		journal_ids = context.get("journal_ids", []) or existing_record.journal_ids.ids
		analytic_filter = context.get("analytic_filter") or ""
		partner_ids = context.get("partner_ids", []) or existing_record.partner_ids.ids
		account_ids = [balance_account_id] if balance_account_id else (
			context.get("account_ids", []) or existing_record.account_ids.ids
		)
		account_filter = context.get("account_filter") or ""

		if analytic_filter:
			analytic_account_ids = self.env["account.analytic.account"].search([
				"|",
				("code", "ilike", analytic_filter),
				("name", "ilike", analytic_filter),
			]).ids or []
		if balance_account_id:
			account_ids = [balance_account_id]
		elif account_filter:
			filter_domain = [
				"|",
				("code", "ilike", account_filter),
				("name", "ilike", account_filter),
			]
			account_ids = self.env["account.account"].search(filter_domain).ids or []

		if target_move == 'posted':
			domain.append(('parent_state', '=', 'posted'))
		elif target_move == 'all':
			domain.append(('parent_state', 'in', ['draft', 'posted']))

		# Filtrar por compañía (incluir subsidiarias con child_of)
		domain.append(('company_id', 'child_of', self.env.company.id))

		if date_from:
			domain.append(('date', '>=', date_from))

		if date_to:
			domain.append(('date', '<=', date_to))

		if journal_ids:
			domain.append(('journal_id', 'in', journal_ids))

		if analytic_account_ids:
			domain.append(('analytic_distribution', 'in', analytic_account_ids))

		if partner_ids:
			domain.append(('partner_id', 'in', partner_ids))

		if account_ids:
			account_ids = [int(acc_id) for acc_id in account_ids]
			domain.append(('account_id', 'in', account_ids))

		account_domain = []

		if account_filter and not account_ids:
			account_domain = [("id", "=", -1)]
		elif account_ids:
			account_domain = [("id", "in", account_ids)]
		elif display_account in ("movement", "not_zero"):
			# Obtener cuentas desde líneas de apunte en el período (evita depender de campos
			# current_debit/credit_balance que pueden estar desactualizados)
			line_account_ids = self.env["account.move.line"].search(domain).mapped("account_id").ids
			account_domain = [("id", "in", line_account_ids)] if line_account_ids else [("id", "=", -1)]
		elif display_account == "all":
			# Todas las cuentas de la compañía (excluir tipo 'view' para no incluir cabeceras)
			try:
				company_domain = list(self.env["account.account"]._check_company_domain(self.env.company))
			except Exception:
				company_domain = [("company_ids", "in", [self.env.company.id])] if "company_ids" in self.env["account.account"]._fields else [("company_id", "=", self.env.company.id)]
			account_domain = company_domain + [("account_type", "!=", "view")]

		accounts = self.env["account.account"].with_company(self.env.company).search(account_domain)
		account_data = []

		company_currency = self.env.company.currency_id

		for account in accounts:
			account_currency = account.currency_id or company_currency
			account_item_domain = domain.copy()
			account_item_domain.append(("account_id", "=", account.id))
			journal_items = self.env["account.move.line"].search(account_item_domain)

			def fmt_amt(amount, curr=None):
				c = curr or company_currency
				return formatLang(self.env, amount, currency_obj=c, grouping=True)

			journal_item_data = []
			account_debit_balance = 0.00
			account_credit_balance = 0.00
			account_balance = 0.00

			for item in journal_items:
				ccy = company_currency
				debit_fmt = formatLang(self.env, item.debit, currency_obj=ccy, grouping=True)
				credit_fmt = formatLang(self.env, item.credit, currency_obj=ccy, grouping=True)
				balance_fmt = formatLang(self.env, item.balance, currency_obj=ccy, grouping=True)
				show_fx = bool(item.currency_id and item.currency_id != ccy)
				orig_fmt = ''
				rate_val = None
				if show_fx and item.amount_currency:
					orig_fmt = formatLang(
						self.env, item.amount_currency, currency_obj=item.currency_id, grouping=True)
					if abs(item.amount_currency) > 1e-9:
						try:
							rate_val = item.balance / item.amount_currency
						except ZeroDivisionError:
							rate_val = None
				journal_item_data.append({
					'id': item.id,
					'partner_id': item.partner_id.name if item.partner_id else False,
					'currency_id': item.currency_id.name if item.currency_id else False,
					'debit': debit_fmt,
					'credit': credit_fmt,
					'balance': balance_fmt,
					'balance_negative': item.balance < 0,
					'balance_zero': item.balance == 0,
					'amount_original_formatted': orig_fmt,
					'has_fx_line': show_fx,
					'implicit_rate': rate_val,
					'move_name': item.move_name or 'Draft',
					'name': item.name,
					'date': item.date.strftime('%d/%m/%Y') if item.date else '',
					'journal_id': item.journal_id.code if item.journal_id else False,
				})

				account_debit_balance += item.debit
				account_credit_balance += item.credit
				account_balance += item.balance

			# Para "not_zero" excluir cuentas con balance 0 en el período
			if display_account == "not_zero" and account_balance == 0.00:
				continue

			total_debit += account_debit_balance
			total_credit += account_credit_balance
			total_balance += account_balance

			account_data.append({
				'id': account.id,
				'code': account.code,
				'name': account.name,
				'debit': fmt_amt(account_debit_balance, company_currency),
				'credit': fmt_amt(account_credit_balance, company_currency),
				'balance': fmt_amt(account_balance, company_currency),
				'balance_negative': account_balance < 0,
				'balance_zero': account_balance == 0,
				'journal_items': journal_item_data,
			})

		total_balance_negative = total_balance < 0
		total_credit = formatLang(self.env, total_credit, currency_obj=company_currency, grouping=True)
		total_debit = formatLang(self.env, total_debit, currency_obj=company_currency, grouping=True)
		total_balance = formatLang(self.env, total_balance, currency_obj=company_currency, grouping=True)

		# Advertencia: asientos en borrador anteriores o incluidos en el período
		has_draft_warning = False
		if date_from or date_to:
			draft_domain = [
				('company_id', 'child_of', self.env.company.id),
				('parent_state', '=', 'draft'),
			]
			if date_to:
				draft_domain.append(('date', '<=', date_to))
			if journal_ids:
				draft_domain.append(('journal_id', 'in', journal_ids))
			has_draft_warning = bool(
				self.env["account.move.line"].search(draft_domain, limit=1)
			)

		return account_data, total_balance, total_credit, total_debit, total_balance_negative, has_draft_warning

	@api.model
	def general_ledger_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("General Ledger")

		header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 250;'
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)

		title_style = xlwt.easyxf(
			'font: bold True, name Arial, height 320; '
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)

		sub_header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 240; '
			'align: vertical center, horizontal center; '
		)

		account_header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)

		line_style = xlwt.easyxf(
			'font: name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)

		amount_style = xlwt.easyxf(
			'font: name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)

		total_style = xlwt.easyxf(
			'font: bold True, name Arial, height 230; '
			'align: horizontal center; '
			# 'pattern: pattern solid;'
		)

		col_widths = [30, 25, 20, 40, 30, 20, 20, 20,20, 20]
		for i, width in enumerate(col_widths):
			worksheet.col(i).width = 256 * width

		worksheet.write_merge(0, 2, 2, 5, "General Ledger", title_style)
		today = datetime.now().strftime("%d-%m-%Y")

		headers = ["", "Journal", "Date", "Communication", "Partner", "Currency", "Debit", "Credit", "Balance"]
		row = 5
		for col, header in enumerate(headers):
			worksheet.write(row, col, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		accounts = data.get('accounts', [])
		expanded_accounts = data.get('expanded_accounts', {})
		generaltotalDebit = data.get('generaltotalDebit', 0.00)
		generaltotalCredit = data.get('generaltotalCredit', 0.00)
		generaltotalBalance = data.get('generaltotalBalance', 0.00)

		for account in accounts:
			worksheet.write(row, 0, account['name'], account_header_style)
			worksheet.write(row, 1, "", account_header_style)
			worksheet.write(row, 2, "", account_header_style)
			worksheet.write(row, 3, "", account_header_style)
			worksheet.write(row, 4, "", account_header_style)
			worksheet.write(row, 5, "", account_header_style)
			worksheet.write(row, 6, account['debit'], account_header_style)
			worksheet.write(row, 7, account['credit'], account_header_style)
			worksheet.write(row, 8, account['balance'], account_header_style)

			worksheet.row(row).height = 360
			row += 1

			if account['name'] in expanded_accounts:
				for item in account.get('journal_items', []):
					worksheet.write(row, 0, item.get('move_name', ''), line_style)
					worksheet.write(row, 1, item.get('journal_id', ''), line_style)
					worksheet.write(row, 2, item.get('date', ''), line_style)
					worksheet.write(row, 3, item.get('name', ''), line_style)
					worksheet.write(row, 4, item.get('partner_id', ''), line_style)
					worksheet.write(row, 5, item.get('currency_id', ''), line_style)
					worksheet.write(row, 6, item.get('debit', ''), line_style)
					worksheet.write(row, 7, item.get('credit', ''), line_style)
					worksheet.write(row, 8, item.get('balance', ''), line_style)
					worksheet.row(row).height = 360
					row += 1

		worksheet.write(row, 0, "Total", total_style)
		worksheet.write(row, 1, "", total_style)
		worksheet.write(row, 2, "", total_style)
		worksheet.write(row, 3, "", total_style)
		worksheet.write(row, 4, "", total_style)
		worksheet.write(row, 5, "", total_style)
		worksheet.write(row, 6, generaltotalDebit, total_style)
		worksheet.write(row, 7, generaltotalCredit, total_style)
		worksheet.write(row, 8, generaltotalBalance, total_style)

		worksheet.row(row).height = 400

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'General Ledger.xls',
		}