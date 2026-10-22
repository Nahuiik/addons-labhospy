# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from datetime import datetime
from odoo.tools.misc import formatLang
from odoo import fields, models, api, _, SUPERUSER_ID

class AnalyticReport(models.Model):
	_name = 'analytic.report'
	_description = 'Analytic Report'

	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string = 'Date To')
	journal_ids = fields.Many2many('account.journal',string='Journal')
	account_ids = fields.Many2many('account.account',string='Account')
	analytic_account_ids = fields.Many2many('account.analytic.account', string="Analytic Accounts")
	plan_ids = fields.Many2many('account.analytic.plan',string='Plan')
	account_tag_ids = fields.Many2many('account.account.tag', string="Account Tags")
	partner_ids = fields.Many2many('res.partner', string="Partner")

	def action_apply_filters_analytic(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'date_from':self.date_from,
			'date_to':self.date_to,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'account_ids':self.account_ids.ids if self.account_ids else None,
			'partner_ids':self.partner_ids.ids if self.partner_ids else None,
			'account_tag_ids':self.account_tag_ids.ids if self.account_tag_ids else None,
			'plan_ids':self.plan_ids.ids if self.plan_ids else None,
			'analytic_account_ids':self.analytic_account_ids.ids if self.analytic_account_ids else None,
		}
		records = self.with_context(context).get_data_analytic_report()
		return {
			'type': 'ir.actions.client',
			'tag': 'bi_account_report',
			'name': _("Analytic Account Report"),
			'context': {'report_type': 'analytic_report', 'filter_options': context},
			'params': {
				'filtered_records': records if records else [],
			},
			'target': 'current',
		}

	@api.model
	def get_data_analytic_report(self,date_range=None):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		domain = []
		total_amount=0.0
		date_from =context.get("date_from") or existing_record.date_from
		date_to = context.get("date_to") or existing_record.date_to
		journal_ids = context.get("journal_ids", existing_record.journal_ids.ids if existing_record.journal_ids else [])
		account_ids = context.get("account_ids", existing_record.account_ids.ids if existing_record.account_ids else [])
		partner_ids = context.get("partner_ids", existing_record.partner_ids.ids if existing_record.partner_ids else [])
		account_tag_ids = context.get("account_tag_ids", existing_record.account_tag_ids.ids if existing_record.account_tag_ids else [])
		plan_ids = context.get("plan_ids", existing_record.plan_ids.ids if existing_record.plan_ids else [])
		analytic_account_ids = context.get("analytic_account_ids", existing_record.analytic_account_ids.ids if existing_record.analytic_account_ids else [])
		analytic_filter = (context.get("analytic_filter") or "").strip()
		if analytic_filter and not analytic_account_ids:
			analytic_account_ids = self.env["account.analytic.account"].search([
				"|", ("name", "ilike", analytic_filter), ("code", "ilike", analytic_filter)
			]).ids

		if date_from:
			domain.append(('date', '>=', date_from))
		if date_to:
			domain.append(('date', '<=', date_to))

		if journal_ids:
			domain.append(('journal_id', 'in', journal_ids))
		if account_tag_ids:
			domain.append(('general_account_id.tag_ids', 'in', account_tag_ids))
		if partner_ids:
			domain.append(('partner_id', 'in', partner_ids))

		analytic_domain = []
		if analytic_account_ids:
			analytic_domain.append(('id', 'in', analytic_account_ids))
		if plan_ids:
			analytic_domain.append(('plan_id', 'in', plan_ids))

		company_currency = self.env.company.currency_id

		def format_amount(amount):
			return formatLang(self.env, amount, currency_obj=company_currency)

		analytic_account_id = self.env["account.analytic.account"].with_user(SUPERUSER_ID).search(analytic_domain)

		analytic_account_line_domain = [('account_id', 'in', analytic_account_id.ids)]
		if account_ids:
			analytic_account_line_domain.append(('general_account_id', 'in', account_ids))
		analytic_account_line = self.env["account.analytic.line"].with_user(SUPERUSER_ID).search(analytic_account_line_domain)
		get_analytic_accounts = analytic_account_id.filtered(lambda a:a.id in analytic_account_line.mapped('account_id').ids)

		total_amount=0.0
		analytic_account_data = []

		for account in get_analytic_accounts:
			account_currency = account.currency_id or self.env.company.currency_id
			currency_symbol = account_currency.symbol if account_currency else ""
			line_domain = domain + [("account_id", "=", account.id)]
			analytic_items = self.env["account.analytic.line"].search_read(line_domain)
			account_amount= 0.0

			analytic_item_data=[]
			for item in analytic_items:
				account_record = self.env["account.account"].browse(item["general_account_id"][0]) if item.get("general_account_id") else None
				account_code = account_record.code if account_record else ""

				analytic_record = self.env["account.analytic.account"].browse(item["account_id"][0]) if item.get("account_id") else None
				plan = analytic_record.plan_id.name if analytic_record else ""
				
				item_amount = item['amount']
				analytic_item_data.append({
					'id': item['id'],
					'partner_id': item['partner_id'],
					'account': account_code,
					'plan': plan,
					'amount': format_amount(item_amount),
					'amount_negative': item_amount < 0,
					'product': item['product_id'],
					'date': item['date'].strftime("%m/%d/%Y"),
					'journal_id': item['journal_id'],
				})
				account_amount+=item['amount']
			if analytic_item_data:
				analytic_account_data.append({
					'id': account.id,
					'name': account.name,
					'amount': format_amount(account_amount),
					'amount_negative': account_amount < 0,
					'analytic_items': analytic_item_data,
				})
			total_amount += account_amount
		extra = {'total_amount_negative': total_amount < 0}
		return analytic_account_data, format_amount(total_amount), date_from, date_to, extra

	@api.model
	def analytic_report_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Analytic Report")

		header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 250; '
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
			'font: bold True, name Arial, height 200; '
			'align: vertical center, horizontal left; '
		)

		line_style = xlwt.easyxf(
			'font: name Arial, height 180; '
			'align: vertical center, horizontal center; '
		)

		amount_style = xlwt.easyxf(
			'font: name Arial, height 180; '
			'align: vertical center, horizontal center; '
		)

		total_style = xlwt.easyxf(
			'font: bold True, name Arial, height 200; '
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)

		col_widths = [10, 25, 20, 20, 20, 20, 35, 15]
		for i, width in enumerate(col_widths):
			worksheet.col(i).width = 256 * width

		worksheet.write_merge(0, 2, 2, 5, "Analytic Report", title_style)
		today = datetime.now().strftime("%d-%m-%Y")

		headers = ["Date", "Partner", "Journal", "Account", "Plan", "Product", "Amount"]
		row = 5
		for col, header in enumerate(headers):
			worksheet.write(row, col+1, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		accounts = data.get('accounts', [])
		expanded_accounts = data.get('expanded_accounts', {})

		for account in accounts:
			worksheet.write(row, 1, account['name'], account_header_style)
			worksheet.write(row, 2, "", line_style)
			worksheet.write(row, 3, "", line_style)
			worksheet.write(row, 4, "", line_style)
			worksheet.write(row, 5, "", line_style)
			worksheet.write(row, 6, "", line_style)

			worksheet.write(row, 7, account.get('amount', ''), amount_style)
			worksheet.row(row).height = 360
			row += 1

			if account['name'] in expanded_accounts:
				for item in account.get('analytic_items', []):
					worksheet.write(row, 0, "", line_style)
					worksheet.write(row, 1, item.get('date', ''), line_style)

					partner = item.get('partner_id', ['', ''])[1] if item.get('partner_id') else ''
					worksheet.write(row, 2, partner, line_style)

					journal = item.get('journal_id', ['', ''])[1] if item.get('journal_id') else ''
					worksheet.write(row, 3, journal, line_style)

					worksheet.write(row, 4, item.get('account', ''), line_style)
					worksheet.write(row, 5, item.get('plan', ''), line_style)

					product = item.get('product', ['', ''])[1] if item.get('product') else ''
					worksheet.write(row, 6, product, line_style)

					worksheet.write(row, 7, item.get('amount', ''), amount_style)

					worksheet.row(row).height = 360
					row += 1

		worksheet.write(row, 1, "Total", total_style)
		worksheet.write(row, 2, "", total_style)
		worksheet.write(row, 3, "", total_style)
		worksheet.write(row, 4, "", total_style)
		worksheet.write(row, 5, "", total_style)
		worksheet.write(row, 6, "", total_style)

		worksheet.write(row, 7, data.get('total_amount', ''), total_style)
		worksheet.row(row).height = 400

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'Analytic_Report.xls',
		}