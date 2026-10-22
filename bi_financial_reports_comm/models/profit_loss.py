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

class ProfitLossReport(models.Model):
	_name = 'profit.loss.report'
	_description = 'Estado de Resultados'
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


	def action_apply_filters_profitloss(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'date_from':self.date_from if self.date_from else None,
			'date_to':self.date_to if self.date_to else None,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'date_range':self.date_range if self.date_range else None,
		}
		
		records = self.with_context(context).get_data_profit_loss()
		return {
			'type': 'ir.actions.client',
			'tag': 'profit_loss_report_tag',
			'name': "Estado de Resultados",
			'params': {
				'filtered_records': records if records else [],
			},
			'target':'current',
		}
		
	def _get_account_by_type(self, account_types):
		return self.env['account.account'].search([
			('account_type', 'in', account_types),
		])

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
		balance = move_lines[0][1] if move_lines else 0.0
		if account.account_type in ['income', 'income_other']:
			return -balance
		return balance

	def account_balance_calculate(self,accounts_dict, date_from,date_to):
		result = {}
		for key, accounts in accounts_dict.items():
			account_data = []
			total = 0.0
			for account in accounts:
				balance = self.get_account_balance(account, date_from, date_to)
				if balance:
					account_data.append({
						'id': account.id,
						'name': account.name,
						'code': account.code,
						'balance': balance,
					})
					total += balance
			result[key] = {
				'accounts': account_data,
				'total': total
			}
		return result

	def _get_comparison_period_dates(self, date_from, date_to, comparison_filter, number_period, date_filter_type):
		"""Compute comparison period dates (Enterprise-style)."""
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
			else:  # year
				cmp_to = date_to - relativedelta(years=number_period)
				cmp_from, cmp_to = get_fiscal_year(cmp_to)
			return {
				"date_from": cmp_from.strftime("%Y-%m-%d"),
				"date_to": cmp_to.strftime("%Y-%m-%d"),
				"string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y"),
			}
		if comparison_filter == "same_last_year":
			cmp_from = date_from - relativedelta(years=number_period)
			cmp_to = date_to - relativedelta(years=number_period)
			return {
				"date_from": cmp_from.strftime("%Y-%m-%d"),
				"date_to": cmp_to.strftime("%Y-%m-%d"),
				"string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y"),
			}
		if comparison_filter == "specific_date":
			cmp_date_to = self.env.context.get("comparison_date_to")
			if cmp_date_to:
				cmp_to = fields.Date.from_string(cmp_date_to)
				pt = date_filter_type or "month"
				if pt == "month":
					cmp_from, cmp_to = get_month(cmp_to)
				elif pt == "quarter":
					cmp_from, cmp_to = get_quarter(cmp_to)
				else:
					cmp_from, cmp_to = get_fiscal_year(cmp_to)
				return {
					"date_from": cmp_from.strftime("%Y-%m-%d"),
					"date_to": cmp_to.strftime("%Y-%m-%d"),
					"string": cmp_from.strftime("%d/%m/%Y") + " - " + cmp_to.strftime("%d/%m/%Y"),
				}
		return None

	@api.model
	def _get_report_company_options(self):
		return {
			"totals_below_sections": bool(self.env.company.bi_totals_below_sections),
		}

	@api.model
	def get_data_profit_loss(self, date_range=None):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		date_from = context.get("date_from") or (existing_record.date_from if existing_record else False)
		date_to = context.get("date_to") or (existing_record.date_to if existing_record else False)
		journal_ids = context.get("journal_ids", existing_record.journal_ids.ids if existing_record and existing_record.journal_ids else [])

		if not (date_from and date_to):
			fiscal_year = get_fiscal_year(fields.Date.today())
			date_from = fiscal_year[0]
			date_to = fields.Date.today()

		use_hierarchy = bool(context.get("hierarchy", True))
		periods = self._pl_get_report_periods(date_from, date_to, context)

		income_accounts = {
			'income': self._get_account_by_type(['income']),
			'income_other': self._get_account_by_type(['income_other']),
		}
		expense_accounts = {
			'expense': self._get_account_by_type(['expense']),
			'expense_depreciation': self._get_account_by_type(['expense_depreciation']),
			'expense_direct_cost': self._get_account_by_type(['expense_direct_cost']),
		}

		income = {
			key: self._pl_build_section_payload(accounts, periods, use_hierarchy)
			for key, accounts in income_accounts.items()
		}
		expense = {
			key: self._pl_build_section_payload(accounts, periods, use_hierarchy)
			for key, accounts in expense_accounts.items()
		}

		comparison = None
		comparison_periods = [p for p in periods if not p.get("is_current")]
		if comparison_periods:
			first_cmp = comparison_periods[0]
			comparison = {
				"date_from": first_cmp["date_from"],
				"date_to": first_cmp["date_to"],
				"string": first_cmp["label"],
				"income": {
					key: {
						"total": block.get("total_by_period", {}).get(first_cmp["key"], 0.0),
						"accounts": [
							{
								"id": acc["id"],
								"code": acc["code"],
								"name": acc["name"],
								"balance": (acc.get("balances") or {}).get(first_cmp["key"], 0.0),
							}
							for acc in (block.get("accounts") or [])
						],
					}
					for key, block in income.items()
				},
				"expense": {
					key: {
						"total": block.get("total_by_period", {}).get(first_cmp["key"], 0.0),
						"accounts": [
							{
								"id": acc["id"],
								"code": acc["code"],
								"name": acc["name"],
								"balance": (acc.get("balances") or {}).get(first_cmp["key"], 0.0),
							}
							for acc in (block.get("accounts") or [])
						],
					}
					for key, block in expense.items()
				},
			}

		target_move = context.get("target_move", "all")
		has_draft_warning = False
		if target_move == "posted":
			draft_domain = [
				("display_type", "=", False),
				("parent_state", "=", "draft"),
				("date", ">=", date_from or "1900-01-01"),
				("date", "<=", date_to or "2100-12-31"),
			]
			if journal_ids:
				draft_domain.append(("journal_id", "in", journal_ids))
			has_draft_warning = bool(self.env["account.move.line"].search(draft_domain, limit=1))

		currency = self.env.company.currency_id
		currency_data = {
			'id': currency.id,
			'symbol': currency.symbol,
			'position': currency.position,
			'decimal_places': currency.decimal_places,
		}

		result = {
			'date_from': date_from if date_from else None,
			'date_to': date_to if date_to else None,
			'company': self.env.company.name,
			'currency_data': currency_data,
			'periods': periods,
			'income': income,
			'expense': expense,
			'has_draft_warning': has_draft_warning,
			'company_options': self._get_report_company_options(),
		}
		if self._an_columns_enabled():
			columns = self._an_build_columns()
			result['columns'] = columns
			result['column_mode'] = 'analytic'
			result['analytic_matrix'] = self._an_profit_loss_matrix(income, expense, columns)
		elif comparison:
			result['comparison'] = comparison
		report_cur = context.get('report_currency_id')
		if report_cur:
			self.env['bi.report.currency.helper'].apply_profit_loss(result, report_cur)
		return result

	@api.model
	def _an_profit_loss_matrix(self, income, expense, columns):
		"""Build the analytic-columns matrix (accounts/sections x analytic columns).

		Section totals come from the per-column balances already computed by the
		mixin; subtotals (gross profit, operating income, net profit) are derived
		per column so every column stays internally consistent.
		"""
		column_keys = [c["key"] for c in columns]

		def sec_total(bucket, key, col):
			return ((bucket.get(key) or {}).get("total_by_period") or {}).get(col, 0.0)

		def acc_rows(bucket, key):
			rows = []
			for acc in (bucket.get(key) or {}).get("accounts") or []:
				rows.append({
					"type": "account",
					"key": "%s_acc_%s" % (key, acc["id"]),
					"parent": key,
					"account_id": acc["id"],
					"label": ("%s %s" % (acc.get("code") or "", acc.get("name") or "")).strip(),
					"level": 1,
					"values": {ck: (acc.get("balances") or {}).get(ck, 0.0) for ck in column_keys},
				})
			return rows

		def section(key, label, bucket, bkey):
			children = acc_rows(bucket, bkey)
			return {
				"type": "section",
				"key": key,
				"label": label,
				"level": 0,
				"expandable": bool(children),
				"values": {ck: sec_total(bucket, bkey, ck) for ck in column_keys},
				"children": children,
			}

		def subtotal(key, label, calc):
			return {
				"type": "subtotal",
				"key": key,
				"label": label,
				"level": 0,
				"values": {ck: calc(ck) for ck in column_keys},
			}

		gross = lambda ck: sec_total(income, "income", ck) - sec_total(expense, "expense_direct_cost", ck)
		operating = lambda ck: gross(ck) - sec_total(expense, "expense", ck)
		net = lambda ck: operating(ck) + sec_total(income, "income_other", ck) - sec_total(expense, "expense_depreciation", ck)

		rows = [
			section("income", _("Ingreso"), income, "income"),
			section("expense_direct_cost", _("Menos costo de ingresos"), expense, "expense_direct_cost"),
			subtotal("gross_profit", _("Ganancia bruta"), gross),
			section("expense", _("Menos gasto de operación"), expense, "expense"),
			subtotal("operating_income", _("Ingreso de operación (o pérdida)"), operating),
			section("income_other", _("Más otros ingresos"), income, "income_other"),
			section("expense_depreciation", _("Menos gastos de otro tipo"), expense, "expense_depreciation"),
			subtotal("net_profit", _("Ganancias netas"), net),
		]
		return {"columns": columns, "rows": rows}

	@api.model
	def profit_loss_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Estado de Resultados")

		account_currency = self.env.company.currency_id

		def _fmt(amount):
			return formatLang(self.env, amount, currency_obj=account_currency)

		title_style = xlwt.easyxf(
			'font: bold True, name Arial, height 300; '
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)
		
		header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 240; '
			'align: vertical center, horizontal center;'
		)

		line_style = xlwt.easyxf(
			'font: name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)
		
		section_header_style = xlwt.easyxf(
			'font: bold True, height 220; '
			'align: vertical center, horizontal left;'
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

		ProfitLossData = data.get('ProfitLossData', {})
		income = ProfitLossData.get('income', {})
		expense = ProfitLossData.get('expense', {})
		grossProfitTotal = data.get('grossProfitTotal', 0)
		operatingIncomeTotal = data.get('operatingIncomeTotal', 0)
		expandedType = data.get('expandedType', {})
		date_from=''
		date_to=''
		if ProfitLossData['date_from']:
			date_from = f'From {ProfitLossData["date_from"]}'
		if ProfitLossData['date_to']:
			date_to = f'To {ProfitLossData["date_to"]}'

		worksheet.write_merge(0, 1, 1, 2, "ESTADO DE RESULTADOS", title_style)
		worksheet.write_merge(3, 3, 1, 2, f"{date_from} {date_to} ", header_style)
		
		row = 5
		
		worksheet.write(row, 1, "Revenue", line_style)
		worksheet.write(row, 2, _fmt(income.get('income', {}).get('total', 0)), amount_style)
		row += 1
		
		if 'income' in expandedType and 'accounts' in income.get('income', {}):
			for account in income['income']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, _fmt(account.get('balance', 0)), amount_style)
				row += 1
		
		worksheet.write(row, 1, "Less Cost of Revenue", line_style)
		worksheet.write(row, 2, _fmt(expense.get('expense_direct_cost', {}).get('total', 0)), amount_style)
		row += 1
		
		if 'expense_direct_cost' in expandedType and 'accounts' in expense.get('expense_direct_cost', {}):
			for account in expense['expense_direct_cost']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, _fmt(account.get('balance', 0)), amount_style)
				row += 1
		
		worksheet.write(row, 1, "Gross Profit", section_header_style)
		worksheet.write(row, 2, _fmt(grossProfitTotal), section_header_style)
		row += 1
		
		worksheet.write(row, 1, "Less Operating Expenses", line_style)
		worksheet.write(row, 2, _fmt(expense.get('expense', {}).get('total', 0)), amount_style)
		row += 1
		
		if 'expense' in expandedType and 'accounts' in expense.get('expense', {}):
			for account in expense['expense']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, _fmt(account.get('balance', 0)), amount_style)
				row += 1
		
		worksheet.write(row, 1, "Operating Income (or Loss)", section_header_style)
		worksheet.write(row, 2, _fmt(operatingIncomeTotal), section_header_style)
		row += 1
		
		worksheet.write(row, 1, "Plus: Other Income", line_style)
		worksheet.write(row, 2, _fmt(income.get('income_other', {}).get('total', 0)), amount_style)
		row += 1
		
		if 'income_other' in expandedType and 'accounts' in income.get('income_other', {}):
			for account in income['income_other']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, _fmt(account.get('balance', 0)), amount_style)
				row += 1
		
		worksheet.write(row, 1, "Less: Other Expenses", line_style)
		worksheet.write(row, 2, _fmt(expense.get('expense_depreciation', {}).get('total', 0)), amount_style)
		row += 1
		
		if 'expense_depreciation' in expandedType and 'accounts' in expense.get('expense_depreciation', {}):
			for account in expense['expense_depreciation']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, _fmt(account.get('balance', 0)), amount_style)
				row += 1
		
		net_profit = operatingIncomeTotal + income.get('income_other', {}).get('total', 0) - expense.get('expense_depreciation', {}).get('total', 0)
		worksheet.write(row, 1, "Net Profit", section_header_style)
		worksheet.write(row, 2, _fmt(net_profit), section_header_style)

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		today = datetime.now().strftime("%Y-%m-%d")
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'Estado_de_Resultados.xls',
		}

	@api.model
	def profit_loss_owl_xlsx(self, data):
		"""Export XLSX desde la vista OWL."""
		if (data or {}).get('column_mode') == 'analytic':
			return self._an_matrix_xlsx(data, _('Estado de resultados'))
		output = io.BytesIO()
		workbook = xlsxwriter.Workbook(output, {'in_memory': True})
		sheet = workbook.add_worksheet(_('Estado de resultados'))
		bold = workbook.add_format({'bold': True})
		money = workbook.add_format({'num_format': '#,##0.00'})
		row = 0
		sheet.write(row, 0, data.get('company') or '', bold)
		row += 1
		sheet.write(row, 0, str(data.get('date_from') or ''))
		sheet.write(row, 1, str(data.get('date_to') or ''))
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

		dump_bucket(_('INGRESOS'), data.get('income'))
		dump_bucket(_('GASTOS'), data.get('expense'))
		workbook.close()
		output.seek(0)
		return {
			'excel_file': base64.b64encode(output.read()).decode('utf-8'),
			'file_name': 'Estado_de_Resultados.xlsx',
		}

	@api.model
	def action_open_aml(self, options, account_id):
		opts = dict(options or {})
		helper = self.env['bi.report.drilldown.helper']
		domain = helper.aml_domain(opts, account_id=int(account_id))
		return helper.action_aml_window(domain)
