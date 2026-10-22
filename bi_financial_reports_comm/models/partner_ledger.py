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

class PartnerLedgerReport(models.Model):
	_name = 'partner.ledger.report'
	_description = 'Partner Ledger Report'

	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string = 'Date To')
	partner_ids = fields.Many2many('res.partner', string="Partner")
	journal_ids = fields.Many2many('account.journal',string='Journal')
	account_ids = fields.Many2many('account.account',string='Account')
	target_move = fields.Selection([('posted', 'All Posted Entries'),
									('all', 'All Entries'),
									], string='Target Moves', required=True, default='all')
	
	initial_balance = fields.Boolean(string='Include Initial Balances')

	account_tag_ids = fields.Many2many('account.account.tag', string="Account Tags")
	partner_tag_ids = fields.Many2many('res.partner.category', string="Partner Tags")
	include_initial_balance = fields.Boolean(string = 'Include Initial Balance')

	def action_apply_filters_partner(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'target_move':self.target_move,
			'date_from':self.date_from,
			'date_to':self.date_to,
			'initial_balance':self.initial_balance,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'account_ids':self.account_ids.ids if self.account_ids else None,
			'partner_ids':self.partner_ids.ids if self.partner_ids else None,
			'account_tag_ids':self.account_tag_ids.ids if self.account_tag_ids else None,
			'partner_tag_ids':self.partner_tag_ids.ids if self.partner_tag_ids else None,
		}
		records = self.with_context(context).get_data_partner_ledger()
		return {
			"type": "ir.actions.client",
			"tag": "bi_account_report",
			"name": "Partner Ledger",
			"context": {"report_type": "partner_ledger"},
			"params": {
				"filtered_records": records if records else [],
			},
			"target": "current",
		}


	@api.model
	def get_data_partner_ledger(self):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		target_move = context.get("target_move") or (existing_record.target_move if existing_record else "all")
		date_from = context.get("date_from") or existing_record.date_from
		date_to = context.get("date_to") or existing_record.date_to
		journal_ids = context.get("journal_ids") or (existing_record.journal_ids.ids if existing_record.journal_ids else [])
		account_ids = context.get("account_ids") or (existing_record.account_ids.ids if existing_record.account_ids else [])
		partner_ids = context.get("partner_ids") or (existing_record.partner_ids.ids if existing_record.partner_ids else [])
		account_tag_ids = context.get("account_tag_ids") or (existing_record.account_tag_ids.ids if existing_record.account_tag_ids else [])
		partner_tag_ids = context.get("partner_tag_ids") or (existing_record.partner_tag_ids.ids if existing_record.partner_tag_ids else [])
		account_type_ids = context.get("account_type_ids") or ["trade_receivable", "trade_payable"]
		if isinstance(account_type_ids, str):
			account_type_ids = [account_type_ids] if account_type_ids in ("trade_receivable", "non_trade_receivable", "trade_payable", "non_trade_payable") else ["trade_receivable", "trade_payable"]
		partner_name_filter = (context.get("partner_name_filter") or "").strip()
		unreconciled = context.get("unreconciled", False)

		# Fallback when context has no dates (e.g. direct open from menu)
		if not date_from:
			from datetime import date
			date_from = date(datetime.now().year, datetime.now().month, 1).isoformat()
		if not date_to:
			from datetime import date
			from calendar import monthrange
			_, last = monthrange(datetime.now().year, datetime.now().month)
			date_to = date(datetime.now().year, datetime.now().month, last).isoformat()
		if hasattr(date_from, 'isoformat'):
			date_from = date_from.isoformat()
		if hasattr(date_to, 'isoformat'):
			date_to = date_to.isoformat()

		# Exclude only section/subsection/note (like Enterprise account_reports)
		# Lines with display_type='product', 'payment_term', 'tax' have real amounts
		domain = [
			("company_id", "child_of", self.env.company.id),
			("display_type", "not in", ("line_section", "line_subsection", "line_note")),
		]
		if target_move == "posted":
			domain.append(("parent_state", "=", "posted"))
		elif target_move == "all":
			domain.append(("parent_state", "in", ["draft", "posted"]))

		if date_from:
			domain.append(("date", ">=", date_from))
		if date_to:
			domain.append(("date", "<=", date_to))
		if journal_ids:
			domain.append(("journal_id", "in", journal_ids))
		if account_tag_ids:
			domain.append(("account_id.tag_ids", "in", account_tag_ids))
		if partner_tag_ids:
			domain.append(("partner_id.category_id", "in", partner_tag_ids))

		if account_ids:
			domain.append(("account_id", "in", account_ids))
		else:
			# Multi-select: trade/non-trade receivables and payables (Enterprise-style)
			acc_type_domains = {
				"trade_receivable": [
					("account_id.non_trade", "=", False),
					("account_id.account_type", "=", "asset_receivable"),
				],
				"non_trade_receivable": [
					("account_id.non_trade", "=", True),
					("account_id.account_type", "=", "asset_receivable"),
				],
				"trade_payable": [
					("account_id.non_trade", "=", False),
					("account_id.account_type", "=", "liability_payable"),
				],
				"non_trade_payable": [
					("account_id.non_trade", "=", True),
					("account_id.account_type", "=", "liability_payable"),
				],
			}
			selected = [acc_type_domains[k] for k in account_type_ids if k in acc_type_domains]
			if not selected:
				selected = [acc_type_domains["trade_receivable"], acc_type_domains["trade_payable"]]
			if len(selected) == 1:
				domain.extend(selected[0])
			else:
				# Build flat domain: ["|", "|", "&", c1a, c1b, "&", c2a, c2b, ...]
				or_parts = ["|"] * (len(selected) - 1)
				for conds in selected:
					or_parts.extend(["&", conds[0], conds[1]])
				domain.extend(or_parts)
		if partner_ids:
			domain.append(("partner_id", "in", partner_ids))
		if partner_name_filter:
			domain.append(("partner_id.name", "ilike", partner_name_filter))
		if unreconciled:
			domain.append(("reconciled", "=", False))

		aml = self.env["account.move.line"].search(domain)
		company_currency = self.env.company.currency_id

		# Aggregate per partner; skip only section/subsection/note (like Enterprise)
		# Lines with display_type='product', 'payment_term', 'tax', etc. have real amounts
		partner_sums = {}
		for line in aml:
			if line.display_type in ('line_section', 'line_subsection', 'line_note'):
				continue
			pid = line.partner_id.id
			if pid not in partner_sums:
				partner_sums[pid] = {"debit": 0.0, "credit": 0.0, "balance": 0.0, "lines": []}
			partner_sums[pid]["debit"] += line.debit
			partner_sums[pid]["credit"] += line.credit
			partner_sums[pid]["balance"] += line.balance
			partner_sums[pid]["lines"].append(line)

		partner_data = []
		total_debit = 0.0
		total_credit = 0.0
		total_balance = 0.0
		has_draft_warning = False

		for partner_id, sums in partner_sums.items():
			balance = sums["balance"]
			debit = sums["debit"]
			credit = sums["credit"]
			# Exclude only partners with absolutely no activity
			if company_currency.is_zero(balance) and company_currency.is_zero(debit) and company_currency.is_zero(credit):
				continue
			partner = self.env["res.partner"].browse(partner_id)

			def fmt(amount, curr=None):
				c = curr or company_currency
				return formatLang(self.env, amount, currency_obj=c)

			journal_item_data = []
			cumulative = 0.0
			for item in sums["lines"]:
				if item.parent_state == "draft":
					has_draft_warning = True
				cumulative += item.balance
				no_follow = getattr(item, "no_followup", False)
				amount_val = item.balance
				ccy_co = company_currency
				show_fx = bool(item.currency_id and item.currency_id != ccy_co and item.amount_currency)
				orig_fmt = ""
				if show_fx:
					orig_fmt = fmt(item.amount_currency, item.currency_id)
				journal_item_data.append({
					"id": item.id,
					"partner_id": item.partner_id.id if item.partner_id else None,
					"currency_id": item.currency_id.name if item.currency_id else "",
					"debit": fmt(item.debit),
					"credit": fmt(item.credit),
					"balance": fmt(item.balance),
					"amount": fmt(amount_val),
					"amount_negative": amount_val < 0,
					"cumulative_balance": fmt(cumulative),
					"cumulative_negative": cumulative < 0,
					"no_followup": no_follow,
					"debit_negative": item.debit < 0,
					"credit_negative": item.credit < 0,
					"balance_negative": item.balance < 0,
					"move_name": item.move_name or "Draft",
					"name": item.name or "",
					"invoice_date": str(item.invoice_date or item.date) if (item.invoice_date or item.date) else "",
					"due_date": str(item.date_maturity) if item.date_maturity else "",
					"journal_id": item.journal_id.code if item.journal_id else "",
					"account_code": item.account_id.code if item.account_id else "",
					"matching": item.matching_number or "",
					"amount_currency": fmt(item.amount_currency or 0.0, item.currency_id),
					"amount_original_formatted": orig_fmt,
					"has_fx_line": show_fx,
				})

			partner_data.append({
				"id": partner.id,
				"name": partner.name,
				"debit": fmt(debit),
				"credit": fmt(credit),
				"balance": fmt(balance),
				"debit_negative": debit < 0,
				"credit_negative": credit < 0,
				"balance_negative": balance < 0,
				"journal_items": journal_item_data,
			})
			total_debit += debit
			total_credit += credit
			total_balance += balance

		if not has_draft_warning and target_move == "posted":
			draft_in_period = self.env["account.move.line"].search_count([
				("display_type", "=", False),
				("parent_state", "=", "draft"),
				("date", ">=", date_from or "1900-01-01"),
				("date", "<=", date_to or "2100-12-31"),
				("account_type", "in", ["liability_payable", "asset_receivable"]),
				("partner_id", "!=", False),
			])
			has_draft_warning = draft_in_period > 0

		fmt_total = (
			formatLang(self.env, total_balance, currency_obj=company_currency),
			formatLang(self.env, total_credit, currency_obj=company_currency),
			formatLang(self.env, total_debit, currency_obj=company_currency),
		)
		total_balance_negative = total_balance < 0
		total_debit_negative = total_debit < 0
		total_credit_negative = total_credit < 0
		return partner_data, fmt_total[0], fmt_total[1], fmt_total[2], total_balance_negative, total_debit_negative, total_credit_negative, has_draft_warning


	@api.model
	def partner_ledger_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Partner Ledger")

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

		col_widths = [30, 25, 20, 20, 20, 20, 20, 20, 30, 20]
		for i, width in enumerate(col_widths):
			worksheet.col(i).width = 256 * width

		worksheet.write_merge(0, 2, 2, 5, "Partner Ledger", title_style)
		today = datetime.now().strftime("%d-%m-%Y")

		headers = ["", "Journal", "Invoice Date", "Due Date", "Account", "Matching", "Debit", "Credit", "Amount Currency", "Adeudado"]
		row = 5
		for col, header in enumerate(headers):
			worksheet.write(row, col, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		partners = data.get('partners', [])
		expanded_partners = data.get('expanded_partners', {})
		partnertotalDebit = data.get('partnertotalDebit', 0.00)
		partnertotalCredit = data.get('partnertotalCredit', 0.00)
		partnertotalBalance = data.get('partnertotalBalance', 0.00)

		for partner in partners:
			worksheet.write(row, 0, partner['name'], account_header_style)
			worksheet.write(row, 1, "", account_header_style)
			worksheet.write(row, 2, "", account_header_style)
			worksheet.write(row, 3, "", account_header_style)
			worksheet.write(row, 4, "", account_header_style)
			worksheet.write(row, 5, "", account_header_style)
			worksheet.write(row, 6, partner['debit'], account_header_style)
			worksheet.write(row, 7, partner['credit'], account_header_style)
			worksheet.write(row, 8, "", account_header_style)
			worksheet.write(row, 9, partner['balance'], account_header_style)

			worksheet.row(row).height = 360
			row += 1

			if partner['name'] in expanded_partners:
				for item in partner.get('journal_items', []):
					worksheet.write(row, 0, item.get('move_name', ''), line_style)
					worksheet.write(row, 1, item.get('journal_id', ''), line_style)
					worksheet.write(row, 2, item.get('invoice_date', ''), line_style)
					worksheet.write(row, 3, item.get('due_date', ''), line_style)
					worksheet.write(row, 4, item.get('account_code', ''), line_style)
					worksheet.write(row, 5, item.get('matching', ''), line_style)
					worksheet.write(row, 6, item.get('debit', ''), line_style)
					worksheet.write(row, 7, item.get('credit', ''), line_style)
					worksheet.write(row, 8, item.get('amount_currency', ''), line_style)
					worksheet.write(row, 9, item.get('balance', ''), line_style)
					worksheet.row(row).height = 360
					row += 1

		worksheet.write(row, 0, "Total", total_style)
		worksheet.write(row, 1, "", total_style)
		worksheet.write(row, 2, "", total_style)
		worksheet.write(row, 3, "", total_style)
		worksheet.write(row, 4, "", total_style)
		worksheet.write(row, 5, "", total_style)
		worksheet.write(row, 6, partnertotalDebit, total_style)
		worksheet.write(row, 7, partnertotalCredit, total_style)
		worksheet.write(row, 8, "", total_style)
		worksheet.write(row, 9, partnertotalBalance, total_style)

		worksheet.row(row).height = 400

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'Partner Ledger.xls',
		}
