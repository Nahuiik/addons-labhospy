# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import formatLang
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter
from odoo import fields, models, api, _
from dateutil.relativedelta import relativedelta

class BalanceSheetReport(models.Model):
	_name = 'balance.sheet.report'
	_description = 'Balance Sheet Report'
	_inherit = ['bi.pl.hierarchy.mixin']

	DATE_SELECTION = [
		('today', 'Today'),
		('this_week', 'This Week'),
		('this_month', 'This Month'),
		('this_quarter', 'This Quarter'),
		('this_financialyear', 'This Financial Year'),
		('yesterday', 'Yesterday'),
		('last_week', 'Last Week'),
		('last_month', 'Last Month'),
		('last_quarter', 'Last Quarter'),
		('last_financialyear', 'Last Financial Year'),
	]

	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string = 'Date To')
	date_range = fields.Selection(DATE_SELECTION,string="Compare Date Range", default='this_financialyear')
	journal_ids = fields.Many2many('account.journal',string='Journal')

	@api.onchange('date_range')
	def _onchange_date_range(self):
		today =fields.Date.today()
		if self.date_range == 'today':
			self.date_from = today
			self.date_to = today
		elif self.date_range == 'this_week':
			self.date_from = today - timedelta(days=today.weekday())
			self.date_to = today
		elif self.date_range == 'this_month':
			self.date_from = get_month(today)[0]
			self.date_to = today
		elif self.date_range == 'this_quarter':
			quarter = get_quarter(today)
			self.date_from = quarter[0]
			self.date_to = today
		elif self.date_range == 'this_financialyear':
			fiscal_year = get_fiscal_year(today)
			self.date_from = fiscal_year[0]
			self.date_to = today
		elif self.date_range == 'yesterday':
			yesterday = today - timedelta(days=1)
			self.date_from = yesterday
			self.date_to = yesterday
		elif self.date_range == 'last_week':
			last_week = today - timedelta(weeks=1)
			self.date_from = last_week - timedelta(days=last_week.weekday())
			self.date_to = self.date_from + timedelta(days=6)
		elif self.date_range == 'last_month':
			first_day_this_month = get_month(today)[0]
			self.date_to = first_day_this_month - timedelta(days=1)
			self.date_from = self.date_to.replace(day=1)
		elif self.date_range == 'last_quarter':
			current_quarter_start = get_quarter(today)[0]
			last_quarter_end = current_quarter_start - timedelta(days=1)
			last_quarter_start = last_quarter_end.replace(day=1) - relativedelta(months=2)
			self.date_from = last_quarter_start
			self.date_to = last_quarter_end
		elif self.date_range == 'last_financialyear':
			current_fiscal_start = get_fiscal_year(today)[0]
			last_fiscal_end = current_fiscal_start - timedelta(days=1)
			last_fiscal_start = get_fiscal_year(last_fiscal_end)[0]
			self.date_from = last_fiscal_start
			self.date_to = last_fiscal_end

	def action_apply_filters_balancesheet(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'date_from':self.date_from if self.date_from else None,
			'date_to':self.date_to if self.date_to else None,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'date_range':self.date_range if self.date_range else None,
		}
		records = self.with_context(context).get_data_balance_sheet()
		return {
			'type': 'ir.actions.client',
			'tag': 'balance_sheet_report_tag',
			'name': "Balance Sheet",
			'params': {
				'filtered_records': records if records else [],
			},
			'target':'current',
		}
		
	def _get_account_by_type(self, account_types):
		return self.env['account.account'].search([
			('account_type', 'in', account_types)])

	def get_account_balance(self, account, date_from, date_to):
		target_move = self.env.context.get('target_move', 'all')
		domain = [
			('account_id', '=', account.id),
		]
		if target_move == 'posted':
			domain.append(('parent_state', '=', 'posted'))
		if date_from:
			domain.append(('date', '>=', date_from))
		if date_to:
			domain.append(('date', '<=', date_to))
		if self.env.context.get('journal_ids'):
			domain.append(('journal_id', 'in', self.env.context['journal_ids']))
		move_lines = self.env['account.move.line']._read_group(
			domain,
			groupby=['account_id'],
			aggregates=['balance:sum']
		)
		return move_lines[0][1] if move_lines else 0.0

	def _sum_amount_currency(self, account, date_from, date_to):
		target_move = self.env.context.get('target_move', 'all')
		domain = [
			('account_id', '=', account.id),
			('display_type', '=', False),
		]
		if target_move == 'posted':
			domain.append(('parent_state', '=', 'posted'))
		else:
			domain.append(('parent_state', 'in', ('draft', 'posted')))
		if date_from:
			domain.append(('date', '>=', date_from))
		if date_to:
			domain.append(('date', '<=', date_to))
		if self.env.context.get('journal_ids'):
			domain.append(('journal_id', 'in', self.env.context['journal_ids']))
		lines = self.env['account.move.line'].search(domain)
		return sum(lines.mapped('amount_currency'))

	def account_balance_calculate(self,accounts_dict, date_from,date_to):
		show_fx = self.env.context.get('show_fx_balance')
		ccy = self.env.company.currency_id
		result = {}
		for key, accounts in accounts_dict.items():
			account_data = []
			total = 0.0
			for account in accounts:
				balance = self.get_account_balance(account, date_from, date_to)
				if balance:
					row = {
						'id': account.id,
						'name': account.name,
						'code': account.code,
						'balance': balance,
					}
					if show_fx and account.currency_id and account.currency_id != ccy:
						row['fx_balance'] = self._sum_amount_currency(account, date_from, date_to)
						row['fx_symbol'] = account.currency_id.symbol or account.currency_id.name
					else:
						row['fx_balance'] = None
						row['fx_symbol'] = ''
					account_data.append(row)
					total += balance
			result[key] = {
				'accounts': account_data,
				'total': total
			}
		return result

	def _get_comparison_period_dates(self, date_from, date_to, comparison_filter, number_period, date_filter_type):
		"""Compute comparison period dates (Balance Sheet uses date_to as 'as of' date)."""
		if comparison_filter in ("no_comparison", None):
			return None
		if comparison_filter != "specific_date" and not number_period:
			return None
		date_from = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
		date_to = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
		if comparison_filter == "previous_period":
			pt = date_filter_type or "month"
			if pt == "month":
				cmp_to = date_to - relativedelta(months=number_period)
				cmp_from, cmp_to = get_month(cmp_to)
			elif pt == "quarter":
				cmp_to = date_to - relativedelta(months=3 * number_period)
				cmp_from, cmp_to = get_quarter(cmp_to)
			else:
				cmp_to = date_to - relativedelta(years=number_period)
				cmp_from, cmp_to = get_fiscal_year(cmp_to)
			return {
				"date_from": cmp_from.strftime("%Y-%m-%d"),
				"date_to": cmp_to.strftime("%Y-%m-%d"),
				"string": cmp_to.strftime("%d/%m/%Y"),
			}
		if comparison_filter == "same_last_year":
			cmp_from = date_from - relativedelta(years=number_period)
			cmp_to = date_to - relativedelta(years=number_period)
			return {
				"date_from": cmp_from.strftime("%Y-%m-%d"),
				"date_to": cmp_to.strftime("%Y-%m-%d"),
				"string": cmp_to.strftime("%d/%m/%Y"),
			}
		if comparison_filter == "specific_date":
			cmp_date_to = self.env.context.get("comparison_date_to")
			if cmp_date_to:
				cmp_to = fields.Date.from_string(cmp_date_to)
				return {
					"date_from": cmp_to.strftime("%Y-%m-%d"),
					"date_to": cmp_to.strftime("%Y-%m-%d"),
					"string": cmp_to.strftime("%d/%m/%Y"),
				}
		return None

	@api.model
	def _get_report_company_options(self):
		return {
			"totals_below_sections": bool(self.env.company.bi_totals_below_sections),
		}

	@api.model
	def get_data_balance_sheet(self, date_range=None):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		date_from = context.get("date_from") or (existing_record.date_from if existing_record else False)
		date_to = context.get("date_to") or (existing_record.date_to if existing_record else False)
		journal_ids = context.get("journal_ids", existing_record.journal_ids.ids if existing_record and existing_record.journal_ids else [])
		if not date_to:
			fiscal_year = get_fiscal_year(fields.Date.today())
			date_from = fiscal_year[0]
			date_to = fields.Date.today()

		use_hierarchy = bool(context.get("hierarchy", True))
		periods = self._pl_get_report_periods(date_from, date_to, context)
		analytic_mode = self._an_columns_enabled()
		analytic_columns = self._an_build_columns() if analytic_mode else []
		primary_key = self._an_primary_key()
		period_keys = [c["key"] for c in analytic_columns] if analytic_mode else [p["key"] for p in periods]

		asset_accounts = {
			'bank_cash': self._get_account_by_type(['asset_cash']),
			'receivables': self._get_account_by_type(['asset_receivable']),
			'current_assets': self._get_account_by_type(['asset_current']),
			'prepayments': self._get_account_by_type(['asset_prepayments']),
			'fixed_assets': self._get_account_by_type(['asset_fixed']),
			'non_current': self._get_account_by_type(['asset_non_current']),
		}
		liability_accounts = {
			'payables': self._get_account_by_type(['liability_payable']),
			'credit_card': self._get_account_by_type(['liability_credit_card']),
			'current_liabilities': self._get_account_by_type(['liability_current']),
			'non_current_liabilities': self._get_account_by_type(['liability_non_current']),
		}
		equity_accounts = {
			'equity': self._get_account_by_type(['equity']),
			'current_year_earnings': self._get_account_by_type(['equity_unaffected']),
		}

		assets = {
			key: self._bs_build_section_payload(accounts, periods, use_hierarchy)
			for key, accounts in asset_accounts.items()
		}
		liabilities = {
			key: self._bs_build_section_payload(accounts, periods, use_hierarchy)
			for key, accounts in liability_accounts.items()
		}
		equity = {
			key: self._bs_build_section_payload(accounts, periods, use_hierarchy)
			for key, accounts in equity_accounts.items()
		}

		def _sum_blocks(blocks, pk):
			return sum((blocks.get(k) or {}).get('total_by_period', {}).get(pk, 0.0) for k in blocks)

		totals_by_period = {
			'assets': {pk: _sum_blocks(assets, pk) for pk in period_keys},
			'liabilities': {pk: _sum_blocks(liabilities, pk) for pk in period_keys},
			'equity': {pk: _sum_blocks(equity, pk) for pk in period_keys},
		}
		totals_by_period['liabilities_equity'] = {
			pk: totals_by_period['liabilities'][pk] + totals_by_period['equity'][pk]
			for pk in period_keys
		}

		comparison = None
		comparison_periods = [] if analytic_mode else [p for p in periods if not p.get("is_current")]
		if comparison_periods:
			first_cmp = comparison_periods[0]
			cmp_key = first_cmp["key"]
			comparison = {
				"date_from": first_cmp["date_from"],
				"date_to": first_cmp["date_to"],
				"string": first_cmp["label"],
				"assets": {k: {"total": v.get("total_by_period", {}).get(cmp_key, 0.0)} for k, v in assets.items()},
				"liabilities": {k: {"total": v.get("total_by_period", {}).get(cmp_key, 0.0)} for k, v in liabilities.items()},
				"equity": {k: {"total": v.get("total_by_period", {}).get(cmp_key, 0.0)} for k, v in equity.items()},
				"totals": {k: v.get(cmp_key, 0.0) for k, v in totals_by_period.items()},
			}

		target_move = context.get('target_move', 'all')
		has_draft_warning = False
		if target_move == 'posted':
			helper = self.env['bi.report.drilldown.helper']
			draft_domain = [
				*helper.aml_display_type_domain(),
				('parent_state', '=', 'draft'),
				('date', '>=', date_from or '1900-01-01'),
				('date', '<=', date_to or '2100-12-31'),
			]
			if journal_ids:
				draft_domain.append(('journal_id', 'in', journal_ids))
			has_draft_warning = bool(self.env['account.move.line'].search(draft_domain, limit=1))

		currency = self.env.company.currency_id
		currency_data = {
			'id': currency.id,
			'symbol': currency.symbol,
			'position': currency.position,
			'decimal_places': currency.decimal_places,
		}

		result = {
			'date_from': date_from,
			'date_to': date_to,
			'company': self.env.company.name,
			'currency_data': currency_data,
			'periods': periods,
			'assets': assets,
			'liabilities': liabilities,
			'equity': equity,
			'totals': {
				'assets': totals_by_period['assets'].get(primary_key, 0.0),
				'liabilities': totals_by_period['liabilities'].get(primary_key, 0.0),
				'equity': totals_by_period['equity'].get(primary_key, 0.0),
				'liabilities_equity': totals_by_period['liabilities_equity'].get(primary_key, 0.0),
				'by_period': totals_by_period,
			},
			'has_draft_warning': has_draft_warning,
			'company_options': self._get_report_company_options(),
		}
		if analytic_mode:
			result['columns'] = analytic_columns
			result['column_mode'] = 'analytic'
			result['analytic_matrix'] = self._an_balance_sheet_matrix(
				assets, liabilities, equity, totals_by_period, analytic_columns
			)
		elif comparison:
			result['comparison'] = comparison
		report_cur = context.get('report_currency_id')
		if report_cur:
			self.env['bi.report.currency.helper'].apply_balance_sheet(result, report_cur)
		return result

	def _bs_build_section_payload(self, accounts, periods, use_hierarchy=False):
		payload = self._pl_build_section_payload(
			accounts, periods, use_hierarchy=use_hierarchy, balance_as_of=True
		)
		if self.env.context.get('show_fx_balance'):
			ccy = self.env.company.currency_id
			date_to = self.env.context.get('date_to') or fields.Date.today()
			for acc_row in payload.get('accounts') or []:
				account = accounts.browse(acc_row['id'])
				if account.currency_id and account.currency_id != ccy:
					acc_row['fx_balance'] = self._sum_amount_currency(account, None, date_to)
					acc_row['fx_symbol'] = account.currency_id.symbol or account.currency_id.name
				else:
					acc_row['fx_balance'] = None
					acc_row['fx_symbol'] = ''
		return payload

	@api.model
	def _an_balance_sheet_matrix(self, assets, liabilities, equity, totals_by_period, columns):
		"""Build the analytic-columns matrix for the Balance Sheet."""
		column_keys = [c["key"] for c in columns]
		section_labels = {
			'bank_cash': _("Cuentas bancarias y de efectivo"),
			'receivables': _("Cuentas por cobrar"),
			'current_assets': _("Activos corrientes"),
			'prepayments': _("Anticipos"),
			'fixed_assets': _("Activos fijos"),
			'non_current': _("Activos no corrientes"),
			'payables': _("Cuentas por pagar"),
			'credit_card': _("Tarjetas de crédito"),
			'current_liabilities': _("Pasivos corrientes"),
			'non_current_liabilities': _("Pasivos no corrientes"),
			'equity': _("Capital"),
			'current_year_earnings': _("Ganancias del ejercicio"),
		}

		def acc_rows(block, bkey):
			rows = []
			for acc in (block or {}).get("accounts") or []:
				rows.append({
					"type": "account",
					"key": "%s_acc_%s" % (bkey, acc["id"]),
					"parent": bkey,
					"account_id": acc["id"],
					"label": ("%s %s" % (acc.get("code") or "", acc.get("name") or "")).strip(),
					"level": 1,
					"values": {ck: (acc.get("balances") or {}).get(ck, 0.0) for ck in column_keys},
				})
			return rows

		def section(bkey, bucket):
			block = bucket.get(bkey) or {}
			children = acc_rows(block, bkey)
			tbp = block.get("total_by_period") or {}
			return {
				"type": "section",
				"key": bkey,
				"label": section_labels.get(bkey, bkey),
				"level": 0,
				"expandable": bool(children),
				"values": {ck: tbp.get(ck, 0.0) for ck in column_keys},
				"children": children,
			}

		def group_row(rtype, key, label, totals):
			return {
				"type": rtype,
				"key": key,
				"label": label,
				"level": 0,
				"values": {ck: totals.get(ck, 0.0) for ck in column_keys},
			}

		rows = []
		rows.append(group_row("main_header", "h_assets", _("ACTIVOS"), totals_by_period["assets"]))
		for bkey in ["bank_cash", "receivables", "current_assets", "prepayments", "fixed_assets", "non_current"]:
			if bkey in assets:
				rows.append(section(bkey, assets))
		rows.append(group_row("main_total", "t_assets", _("Total ACTIVOS"), totals_by_period["assets"]))
		rows.append(group_row("main_header", "h_liabilities", _("PASIVOS"), totals_by_period["liabilities"]))
		for bkey in ["payables", "credit_card", "current_liabilities", "non_current_liabilities"]:
			if bkey in liabilities:
				rows.append(section(bkey, liabilities))
		rows.append(group_row("main_total", "t_liabilities", _("Total PASIVOS"), totals_by_period["liabilities"]))
		rows.append(group_row("main_header", "h_equity", _("PATRIMONIO"), totals_by_period["equity"]))
		for bkey in ["equity", "current_year_earnings"]:
			if bkey in equity:
				rows.append(section(bkey, equity))
		rows.append(group_row("main_total", "t_le", _("Total PASIVOS + PATRIMONIO"), totals_by_period["liabilities_equity"]))
		return {"columns": columns, "rows": rows}

	@api.model
	def balance_sheet_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Balance Sheet Report")

		title_style = xlwt.easyxf(
			'font: bold True, name Arial, height 300; '
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)
		
		header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 240; '
			'align: vertical center, horizontal center;'
		)
		
		section_header_style = xlwt.easyxf(
			'font: bold True, height 220; '
			'align: vertical center, horizontal left;'
			'pattern: pattern solid, fore_colour gray25;'
		)

		section_amount_style = xlwt.easyxf(
			'font: bold True, height 220; '
			'align: vertical center, horizontal center;'
			'pattern: pattern solid, fore_colour gray25;'
		)
		
		line_style = xlwt.easyxf(
			'font: name Arial, height 220; '
			'align: vertical center, horizontal left;'
		)
		
		amount_style = xlwt.easyxf(
			'font: name Arial, height 200; '
			'align: vertical center, horizontal center;'
		)
		
		total_style = xlwt.easyxf(
			'font: bold True, name Arial, height 220; '
			'align: vertical center, horizontal right;'
		)

		worksheet.col(1).width = 12000
		worksheet.col(2).width = 5000

		balanceSheetData = data.get('balanceSheetData', {})
		currentAssetsTotal = data.get('currentAssetsTotal', 0)
		AssetsTotalBalance = data.get('AssetsTotalBalance', 0)
		currentLiabilitiesTotal = data.get('currentLiabilitiesTotal', 0)
		totals = data.get('totals', 0)
		assets = balanceSheetData['assets']
		liabilities = balanceSheetData['liabilities']
		equity = balanceSheetData['equity']
		totals = data.get('totals', 0)
		expandedType = data.get('expandedType', {})

		date_from=''
		date_to=''

		account_currency = self.env.company.currency_id

		def format_amount(amount):
			return formatLang(self.env, amount, currency_obj=account_currency)

		if balanceSheetData['date_from']:
			date_from = f'From {balanceSheetData["date_from"]}'
		if balanceSheetData['date_to']:
			date_to = f'To {balanceSheetData["date_to"]}'

		worksheet.write_merge(0, 1, 1, 2, "Balance Sheet Report", title_style)
		worksheet.write_merge(3, 3, 1, 2, f"{date_from} {date_to} ", header_style)
		
		row = 5
		
		worksheet.write(row, 1, "Assets", section_header_style)
		worksheet.write(row, 2, format_amount(totals['assets']), section_amount_style)
		row += 1

		worksheet.write(row, 1, "   Current Assets	", line_style)
		worksheet.write(row, 2, format_amount(currentAssetsTotal), amount_style)
		row += 1

		worksheet.write(row, 1, "     Bank and Cash Accounts", line_style)
		worksheet.write(row, 2, format_amount(assets['bank_cash']['total']), amount_style)
		row += 1
		
		if 'bank_cash' in expandedType and 'accounts' in assets['bank_cash']:
			for account in assets['bank_cash']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Receivables", line_style)
		worksheet.write(row, 2, format_amount(assets['receivables']['total']), amount_style)
		row += 1
		
		if 'receivables' in expandedType and 'accounts' in assets['receivables']:
			for account in assets['receivables']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}",line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Current Assets", line_style)
		worksheet.write(row, 2, format_amount(assets['bank_cash']['total']), amount_style)
		row += 1

		if 'current_assets' in expandedType and 'accounts' in assets['current_assets']:
			for account in assets['current_assets']['accounts']:
				worksheet.write(rowx, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Prepayments", line_style)
		worksheet.write(row, 2, format_amount(assets['prepayments']['total']), amount_style)
		row += 1
		
		if 'prepayments' in expandedType and 'accounts' in assets['prepayments']:
			for account in assets['prepayments']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "   Plus Fixed Assets", line_style)
		worksheet.write(row, 2, format_amount(assets['fixed_assets']['total']), amount_style)
		row += 1
		
		if 'fixed_assets' in expandedType and 'accounts' in assets['fixed_assets']:
			for account in assets['fixed_assets']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "   Plus Non-current Assets", line_style)
		worksheet.write(row, 2, format_amount(assets['non_current']['total']), amount_style)
		row += 1
		
		if 'non_current' in expandedType and 'accounts' in assets['non_current']:
			for account in assets['non_current']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "LIABILITIES", section_header_style)
		worksheet.write(row, 2, format_amount(totals['liabilities']), section_amount_style)
		row += 1
		
		worksheet.write(row, 1, "   Current Liabilities", line_style)
		worksheet.write(row, 2, format_amount(liabilities['current_liabilities']['total']), amount_style)
		row += 1
		
		if 'current_liabilities' in expandedType and 'accounts' in liabilities['current_liabilities']:
			for account in liabilities['current_liabilities']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Payables", line_style)
		worksheet.write(row, 2, format_amount(liabilities['payables']['total']), amount_style)
		row += 1
		
		if 'payables' in expandedType and 'accounts' in liabilities['payables']:
			for account in liabilities['payables']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "     Credit Card", line_style)
		worksheet.write(row, 2, format_amount(liabilities['credit_card']['total']), amount_style)
		row += 1
		
		if 'credit_card' in expandedType and 'accounts' in liabilities['credit_card']:
			for account in liabilities['credit_card']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "   Plus Non-current Liabilities", line_style)
		worksheet.write(row, 2, format_amount(liabilities['non_current_liabilities']['total']), amount_style)
		row += 1
		
		if 'non_current_liabilities' in expandedType and 'accounts' in liabilities['non_current_liabilities']:
			for account in liabilities['non_current_liabilities']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "EQUITY", section_header_style)
		worksheet.write(row, 2, format_amount(totals['equity']), section_amount_style)
		row += 1
		
		worksheet.write(row, 1, "    Equity", line_style)
		worksheet.write(row, 2, format_amount(equity['equity']['total']), amount_style)
		row += 1
		
		if 'equity' in expandedType and 'accounts' in equity['equity']:
			for account in equity['equity']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "    Current Year Earnings", line_style)
		worksheet.write(row, 2, format_amount(equity['current_year_earnings']['total']), amount_style)
		row += 1
		
		if 'current_year_earnings' in expandedType and 'accounts' in equity['current_year_earnings']:
			for account in equity['current_year_earnings']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "LIABILITIES + EQUITY", section_header_style)
		worksheet.write(row, 2, format_amount(totals['liabilities_equity']), section_amount_style)
		row += 1
		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		today = datetime.now().strftime("%Y-%m-%d")
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': f'Balance_Sheet.xls',
		}

	@api.model
	def balance_sheet_owl_xlsx(self, data):
		"""Export XLSX desde la vista OWL (dict de get_data_balance_sheet)."""
		if (data or {}).get('column_mode') == 'analytic':
			return self._an_matrix_xlsx(data, _('Balance general'))
		output = io.BytesIO()
		workbook = xlsxwriter.Workbook(output, {'in_memory': True})
		sheet = workbook.add_worksheet(_('Balance general'))
		bold = workbook.add_format({'bold': True})
		money = workbook.add_format({'num_format': '#,##0.00'})
		row = 0
		sheet.write(row, 0, data.get('company') or '', bold)
		row += 1
		sheet.write(row, 0, _('Periodo'), bold)
		sheet.write(row, 1, str(data.get('date_from') or ''))
		sheet.write(row, 2, str(data.get('date_to') or ''))
		row += 2

		def dump_bucket(title, bucket):
			nonlocal row
			if not isinstance(bucket, dict):
				return
			for sec_key, sec in bucket.items():
				if not isinstance(sec, dict):
					continue
				sheet.write(row, 0, '%s — %s' % (title, sec_key))
				sheet.write_number(row, 1, float(sec.get('total') or 0.0), money)
				row += 1
				for acc in sec.get('accounts') or []:
					if not isinstance(acc, dict):
						continue
					sheet.write(row, 0, '  %s %s' % (acc.get('code') or '', acc.get('name') or ''))
					sheet.write_number(row, 1, float(acc.get('balance') or 0.0), money)
					row += 1

		dump_bucket(_('ACTIVOS'), data.get('assets'))
		dump_bucket(_('PASIVOS'), data.get('liabilities'))
		dump_bucket(_('PATRIMONIO'), data.get('equity'))
		sheet.write(row, 0, _('Totales (activo / pasivo / patrimonio / pasivo+patrimonio)'), bold)
		row += 1
		for k, v in (data.get('totals') or {}).items():
			sheet.write(row, 0, k)
			sheet.write_number(row, 1, float(v or 0.0), money)
			row += 1
		workbook.close()
		output.seek(0)
		return {
			'excel_file': base64.b64encode(output.read()).decode('utf-8'),
			'file_name': 'Balance_sheet.xlsx',
		}

	@api.model
	def action_open_aml(self, options, account_id):
		"""Drill-down del Balance General → libro mayor acumulado de la cuenta.

		El Balance es acumulado a la fecha (saldo histórico hasta date_to), por lo
		que ignoramos `date_from` para mostrar todos los apuntes que componen el
		saldo. Si hay comparativa, mostramos hasta la fecha de cierre comparada.
		"""
		opts = dict(options or {})
		opts.pop('date_from', None)
		opts.pop('comparison_date_from', None)
		helper = self.env['bi.report.drilldown.helper']
		domain = helper.aml_domain(opts, account_id=int(account_id))
		account = self.env['account.account'].browse(int(account_id))
		name = _("Libro mayor: %(code)s %(name)s", code=account.code or '', name=account.name or '')
		return helper.action_aml_window(domain, name=name)
