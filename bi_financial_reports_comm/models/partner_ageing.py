# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from odoo.tools.misc import formatLang
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class PartnerAgeing(models.Model):
	_name = 'partner.ageing'
	_description = 'Partner Ageing'

	on_date = fields.Date(string="As On Date", default=fields.Date.today)
	account_type = fields.Selection(
		string='Account Types',
		selection=[
			('both', "Payable and receivable"),
			('payable', "Payable"),
			('receivable', "Receivable")
		],
		default="both"
	)
	based_on = fields.Selection(
		string='Based On',
		selection=[
			('due', "Due Date"),
			('invoice', "Invoice Date")
		],
		default="due"
	)
	account_ids = fields.Many2many('account.account', string='Account')
	partner_tag_ids = fields.Many2many('res.partner.category', string="Partner Tags")
	partner_ids = fields.Many2many('res.partner', string="Partners")
	period_length = fields.Integer(string="Period Length (days)", default=30)
	bucket_1 = fields.Integer(compute='_compute_update_bucket')
	bucket_2 = fields.Integer(compute='_compute_update_bucket')
	bucket_3 = fields.Integer(compute='_compute_update_bucket')
	bucket_4 = fields.Integer(compute='_compute_update_bucket')
	bucket_5 = fields.Integer(compute='_compute_update_bucket')

	@api.onchange('period_length')
	def _onchange_period_length(self):
		if self.period_length < 1:
			self.period_length = 1
			raise ValidationError(_('Days Period cannot be smaller than 1'))

	def action_apply_filters_ageing(self):
		self.ensure_one()
		context = {
			'on_date': self.on_date,
			'period_length': self.period_length,
			'account_type': self.account_type,
			'account_ids': self.account_ids.ids,
			'partner_ids': self.partner_ids.ids,
			'partner_tag_ids': self.partner_tag_ids.ids,
			'based_on': self.based_on,
		}
		records = self.with_context(context).get_data_ageing_report()
		return {
			'type': 'ir.actions.client',
			'tag': 'bi_account_report',
			'name': _("Partner Ageing"),
			'context': {
				'report_type': 'partner_ageing',
				'report': 'partner_ageing',
				'filter_options': {
					'date_to': str(self.on_date),
					'period_length': self.period_length,
					'account_type': self.account_type,
					'partner_ids': self.partner_ids.ids,
					'partner_tag_ids': self.partner_tag_ids.ids,
					'account_ids': self.account_ids.ids,
					'based_on': self.based_on,
				},
			},
			'params': {
				'filtered_records': records or {},
			},
			'target': 'current',
		}

	@api.model
	def _ageing_context_id_list(self, key, existing_record=None, m2m_field=None):
		"""Lista de IDs desde contexto; lista vacía = sin filtro."""
		if key in self.env.context:
			return list(self.env.context.get(key) or [])
		if existing_record and m2m_field:
			return existing_record[m2m_field].ids
		return []

	@api.model
	def _ageing_move_state_domain(self, target_move):
		"""Excluye asientos cancelados; respeta filtro registrados/todos."""
		if target_move == "posted":
			return [("parent_state", "=", "posted")]
		return [("parent_state", "in", ("draft", "posted"))]

	@api.model
	def _ageing_line_date_domain(self, on_date):
		"""Fecha contable del apunte <= fecha del reporte (Odoo estándar)."""
		if not on_date:
			return []
		return [("date", "<=", fields.Date.to_date(on_date))]

	@api.model
	def _ageing_reconciliation_domain(self, on_date):
		"""No conciliados + conciliados después de la fecha del reporte."""
		on_date = fields.Date.to_date(on_date)
		partials = self.env["account.partial.reconcile"].search([("max_date", ">", on_date)])
		line_ids = list({
			*partials.mapped("debit_move_id").ids,
			*partials.mapped("credit_move_id").ids,
		})
		if line_ids:
			return ["|", ("reconciled", "=", False), ("id", "in", line_ids)]
		return [("reconciled", "=", False)]

	@api.model
	def _compute_residual_at_date(self, line, on_date):
		"""Saldo pendiente del apunte a la fecha del reporte."""
		on_date = fields.Date.to_date(on_date)
		amount = line.balance
		for partial in line.matched_debit_ids:
			if partial.max_date <= on_date:
				amount += partial.amount
		for partial in line.matched_credit_ids:
			if partial.max_date <= on_date:
				amount -= partial.amount
		return amount

	@api.model
	def _get_aging_date(self, line, based_on):
		if based_on == "invoice":
			return line.invoice_date or line.date
		return line.date_maturity or line.date

	@api.model
	def _get_period_key(self, aging_date, on_date, period_length):
		dt_use = fields.Date.to_date(aging_date)
		on_date = fields.Date.to_date(on_date)
		if not dt_use or not on_date:
			return None
		days_diff = (on_date - dt_use).days
		if days_diff <= 0:
			return "period0"
		if days_diff <= period_length:
			return "period1"
		if days_diff <= 2 * period_length:
			return "period2"
		if days_diff <= 3 * period_length:
			return "period3"
		if days_diff <= 4 * period_length:
			return "period4"
		return "period5"

	@api.model
	def get_data_ageing_report(self):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		raw_on_date = context.get("on_date") or existing_record.on_date or fields.Date.today()
		on_date = fields.Date.to_date(raw_on_date)
		period_length = context.get("period_length") or existing_record.period_length or 30
		account_type = context.get("account_type", existing_record.account_type if existing_record else "both")
		account_ids = self._ageing_context_id_list("account_ids", existing_record, "account_ids")
		partner_ids = self._ageing_context_id_list("partner_ids", existing_record, "partner_ids")
		partner_tag_ids = self._ageing_context_id_list("partner_tag_ids", existing_record, "partner_tag_ids")
		partner_name_filter = context.get("partner_name_filter") or ""
		partner_tag_name_filter = context.get("partner_tag_name_filter") or ""
		based_on = context.get("based_on", existing_record.based_on if existing_record else "due")
		target_move = context.get("target_move", "posted")

		periods = {
			"0": {"name": "At Date", "days": "Current"},
			"1": {"name": f"1-{period_length}", "days": f"1-{period_length}"},
			"2": {"name": f"{period_length+1}-{2*period_length}", "days": f"{period_length+1}-{2*period_length}"},
			"3": {"name": f"{2*period_length+1}-{3*period_length}", "days": f"{2*period_length+1}-{3*period_length}"},
			"4": {"name": f"{3*period_length+1}-{4*period_length}", "days": f"{3*period_length+1}-{4*period_length}"},
			"5": {"name": f"{4*period_length}+", "days": f"{4*period_length}+"},
		}
		currency = self.env.company.currency_id
		currency_data = {
			"id": currency.id,
			"symbol": currency.symbol,
			"position": currency.position,
			"decimal_places": currency.decimal_places,
		}

		def format_amount(amount):
			return formatLang(self.env, amount or 0.0, currency_obj=currency)

		result = {
			"periods": periods,
			"currency_data": currency_data,
			"report_year": str(on_date.year) if on_date else "",
			"receivable": {"partners": [], "period_total": {}, "section_label": _("Vencidas por cobrar")},
			"payable": {"partners": [], "period_total": {}, "section_label": _("Vencidas por pagar")},
		}

		types_to_process = []
		if account_type == "both":
			types_to_process = [
				("receivable", "asset_receivable", _("Vencidas por cobrar")),
				("payable", "liability_payable", _("Vencidas por pagar")),
			]
		elif account_type == "receivable":
			types_to_process = [("receivable", "asset_receivable", _("Vencidas por cobrar"))]
		else:
			types_to_process = [("payable", "liability_payable", _("Vencidas por pagar"))]

		empty_total = {
			"period0": format_amount(0), "period1": format_amount(0), "period2": format_amount(0),
			"period3": format_amount(0), "period4": format_amount(0), "period5": format_amount(0), "total": format_amount(0),
		}
		for section_key, acc_type_filter, section_label in types_to_process:
			partner_data, formatted_total = self._build_ageing_section(
				on_date=on_date,
				period_length=period_length,
				account_type_filter=acc_type_filter,
				account_ids=account_ids,
				partner_ids=partner_ids,
				partner_tag_ids=partner_tag_ids,
				partner_name_filter=partner_name_filter,
				partner_tag_name_filter=partner_tag_name_filter,
				based_on=based_on,
				target_move=target_move,
				periods=periods,
				format_amount=format_amount,
			)
			result[section_key] = {
				"partners": partner_data,
				"period_total": formatted_total or empty_total,
				"section_label": section_label,
			}

		has_draft_warning = False
		if target_move == "posted":
			acc_types = ["asset_receivable", "liability_payable"]
			if account_type == "receivable":
				acc_types = ["asset_receivable"]
			elif account_type == "payable":
				acc_types = ["liability_payable"]
			draft_domain = [
				("display_type", "=", False),
				("parent_state", "=", "draft"),
				("account_id.account_type", "in", acc_types),
				("partner_id", "!=", False),
			]
			if on_date:
				draft_domain.extend(self._ageing_line_date_domain(on_date))
			if account_ids:
				draft_domain.append(("account_id", "in", account_ids))
			has_draft_warning = bool(
				self.env["account.move.line"].search(draft_domain, limit=1)
			)
		result["has_draft_warning"] = has_draft_warning

		return result

	def _build_ageing_section(
		self,
		on_date,
		period_length,
		account_type_filter,
		account_ids,
		partner_ids,
		partner_tag_ids,
		partner_name_filter,
		partner_tag_name_filter,
		based_on,
		target_move,
		periods,
		format_amount,
	):
		currency = self.env.company.currency_id
		multiplier = -1 if account_type_filter == "liability_payable" else 1

		domain = [
			("account_id.account_type", "=", account_type_filter),
			("partner_id", "!=", False),
			("display_type", "not in", ("line_section", "line_note")),
		]
		domain.extend(self._ageing_move_state_domain(target_move))
		domain.extend(self._ageing_reconciliation_domain(on_date))
		if partner_tag_name_filter:
			tag_ids = self.env["res.partner.category"].search([
				("name", "ilike", partner_tag_name_filter)
			]).ids
			domain.append(("partner_id.category_id", "in", tag_ids))
		elif partner_tag_ids:
			domain.append(("partner_id.category_id", "in", partner_tag_ids))
		if account_ids:
			domain.append(("account_id", "in", account_ids))
		if on_date:
			domain.extend(self._ageing_line_date_domain(on_date))
		if partner_ids:
			domain.append(("partner_id", "in", partner_ids))

		candidate_lines = self.env["account.move.line"].search(domain, order="partner_id, date, id")
		candidate_lines.matched_debit_ids
		candidate_lines.matched_credit_ids

		lines_by_partner = {}
		for item in candidate_lines:
			residual = multiplier * self._compute_residual_at_date(item, on_date)
			if currency.is_zero(residual):
				continue
			aging_date = self._get_aging_date(item, based_on)
			period_key = self._get_period_key(aging_date, on_date, period_length)
			if not period_key:
				continue
			partner = item.partner_id
			bucket = lines_by_partner.setdefault(partner.id, {
				"partner": partner,
				"period_amounts": {
					"period0": 0.0, "period1": 0.0, "period2": 0.0,
					"period3": 0.0, "period4": 0.0, "period5": 0.0, "total": 0.0,
				},
				"journal_items": [],
			})
			bucket["period_amounts"][period_key] += residual
			bucket["period_amounts"]["total"] += residual
			inv_date = item.invoice_date or item.date
			due_date = item.date_maturity or item.date
			bucket["journal_items"].append({
				"id": item.id,
				"move_id": item.move_id.id,
				"move_name": item.move_id.name,
				"name": item.name,
				"account_code": item.account_id.code,
				"due_date": due_date.strftime("%Y-%m-%d") if due_date else None,
				"invoice_date": inv_date.strftime("%Y-%m-%d") if inv_date else None,
				"journal_id": item.journal_id.code,
				"amount": format_amount(residual),
				"amount_negative": residual < 0,
				"amount_original_formatted": (
					formatLang(self.env, item.amount_currency, currency_obj=item.currency_id)
					if item.currency_id and item.currency_id != currency and item.amount_currency
					else ""
				),
				"no_followup": getattr(item, "no_followup", False),
				"period_key": period_key,
				"raw_amount": residual,
			})

		partners = self.env["res.partner"].browse(lines_by_partner)
		if partner_name_filter:
			partners = partners.filtered(
				lambda p: partner_name_filter.lower() in (p.name or "").lower()
			)

		partner_data = []
		totals = {
			"period0": 0.0, "period1": 0.0, "period2": 0.0,
			"period3": 0.0, "period4": 0.0, "period5": 0.0, "total": 0.0,
		}

		for partner in partners.sorted(key=lambda p: (p.name or "").upper()):
			bucket = lines_by_partner[partner.id]
			period_amounts = bucket["period_amounts"]
			journal_item_data = bucket["journal_items"]
			for k in totals:
				totals[k] += period_amounts[k]
			partner_data.append({
				"id": partner.id,
				"name": partner.name,
				"period0": format_amount(period_amounts["period0"]),
				"period1": format_amount(period_amounts["period1"]),
				"period2": format_amount(period_amounts["period2"]),
				"period3": format_amount(period_amounts["period3"]),
				"period4": format_amount(period_amounts["period4"]),
				"period5": format_amount(period_amounts["period5"]),
				"total": format_amount(period_amounts["total"]),
				"period0_negative": period_amounts["period0"] < 0,
				"period1_negative": period_amounts["period1"] < 0,
				"period2_negative": period_amounts["period2"] < 0,
				"period3_negative": period_amounts["period3"] < 0,
				"period4_negative": period_amounts["period4"] < 0,
				"period5_negative": period_amounts["period5"] < 0,
				"total_negative": period_amounts["total"] < 0,
				"raw_amounts": period_amounts,
				"journal_items": journal_item_data,
			})

		formatted_total = {
			"period0": format_amount(totals["period0"]),
			"period1": format_amount(totals["period1"]),
			"period2": format_amount(totals["period2"]),
			"period3": format_amount(totals["period3"]),
			"period4": format_amount(totals["period4"]),
			"period5": format_amount(totals["period5"]),
			"total": format_amount(totals["total"]),
			"period0_negative": totals["period0"] < 0,
			"period1_negative": totals["period1"] < 0,
			"period2_negative": totals["period2"] < 0,
			"period3_negative": totals["period3"] < 0,
			"period4_negative": totals["period4"] < 0,
			"period5_negative": totals["period5"] < 0,
			"total_negative": totals["total"] < 0,
		}
		return partner_data, formatted_total

	def _compute_update_bucket(self):
		for record in self:
			day_period = record.period_length
			record.bucket_1 = day_period
			record.bucket_2 = day_period * 2
			record.bucket_3 = day_period * 3
			record.bucket_4 = day_period * 4
			record.bucket_5 = day_period * 5

	def _write_ageing_section_excel(
		self, worksheet, row, partners, periods, period_total, expanded_partners,
		currency_symbol, header_style, account_header_style, line_style, total_style
	):
		headers = [
			"Move", "Invoice Date", "Due Date", "Journal", "Account",
			periods.get("0", {}).get("name", "At Date"),
			periods.get("1", {}).get("name", "1-30"),
			periods.get("2", {}).get("name", "31-60"),
			periods.get("3", {}).get("name", "61-90"),
			periods.get("4", {}).get("name", "91-120"),
			periods.get("5", {}).get("name", "120+"),
			"Total",
		]
		for col, header in enumerate(headers):
			worksheet.write(row, col, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		for partner in partners:
			worksheet.write(row, 0, partner.get("name", ""), account_header_style)
			for c in range(1, 5):
				worksheet.write(row, c, "", account_header_style)
			worksheet.write(row, 5, partner.get("period0", ""), account_header_style)
			worksheet.write(row, 6, partner.get("period1", ""), account_header_style)
			worksheet.write(row, 7, partner.get("period2", ""), account_header_style)
			worksheet.write(row, 8, partner.get("period3", ""), account_header_style)
			worksheet.write(row, 9, partner.get("period4", ""), account_header_style)
			worksheet.write(row, 10, partner.get("period5", ""), account_header_style)
			worksheet.write(row, 11, partner.get("total", ""), account_header_style)
			worksheet.row(row).height = 360
			row += 1

			if partner.get("name") in expanded_partners:
				for item in partner.get("journal_items", []):
					worksheet.write(row, 0, item.get("move_name", ""), line_style)
					worksheet.write(row, 1, item.get("invoice_date", ""), line_style)
					worksheet.write(row, 2, item.get("due_date", ""), line_style)
					worksheet.write(row, 3, item.get("journal_id", ""), line_style)
					worksheet.write(row, 4, item.get("account_code", ""), line_style)
					for c, pk in enumerate(["period0", "period1", "period2", "period3", "period4", "period5"]):
						worksheet.write(row, 5 + c, item.get("amount", f"{currency_symbol} 0.00") if item.get("period_key") == pk else f"{currency_symbol} 0.00", line_style)
					worksheet.write(row, 11, item.get("amount", ""), line_style)
					worksheet.row(row).height = 360
					row += 1

		worksheet.write(row, 0, "Total", total_style)
		for c in range(1, 5):
			worksheet.write(row, c, "", total_style)
		worksheet.write(row, 5, period_total.get("period0", ""), total_style)
		worksheet.write(row, 6, period_total.get("period1", ""), total_style)
		worksheet.write(row, 7, period_total.get("period2", ""), total_style)
		worksheet.write(row, 8, period_total.get("period3", ""), total_style)
		worksheet.write(row, 9, period_total.get("period4", ""), total_style)
		worksheet.write(row, 10, period_total.get("period5", ""), total_style)
		worksheet.write(row, 11, period_total.get("total", ""), total_style)
		worksheet.row(row).height = 400
		return row + 2

	@api.model
	def partner_ageing_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Partner Ageing")

		header_style = xlwt.easyxf(
			"font: bold True, name Arial, height 250;"
			"align: vertical center, horizontal center; "
			"pattern: pattern solid, fore_colour gray25;"
		)
		title_style = xlwt.easyxf(
			"font: bold True, name Arial, height 320; "
			"align: vertical center, horizontal center; "
			"pattern: pattern solid, fore_colour gray25;"
		)
		account_header_style = xlwt.easyxf(
			"font: bold True, name Arial, height 230; "
			"align: vertical center, horizontal center; "
		)
		line_style = xlwt.easyxf(
			"font: name Arial, height 230; "
			"align: vertical center, horizontal center; "
		)
		total_style = xlwt.easyxf(
			"font: bold True, name Arial, height 230; "
			"align: horizontal center; "
		)

		col_widths = [30, 20, 20, 15, 15, 15, 15, 15, 15, 15, 15, 15]
		for i, width in enumerate(col_widths):
			worksheet.col(i).width = 256 * width

		worksheet.write_merge(0, 2, 3, 7, "Partner Ageing / Vencidas Socios", title_style)

		periods = data.get("periods", data.get("periods", {}))
		currency_data = data.get("currency_data", data.get("currency", {}))
		currency_symbol = currency_data.get("symbol", "$") if isinstance(currency_data, dict) else ""
		expanded = data.get("expandedPartners", data.get("expanded_partners", {}))

		row = 5
		section_label_style = xlwt.easyxf("font: bold True, name Arial, height 260;")
		for section_key, section_label in [("receivable", _("Vencidas por cobrar")), ("payable", _("Vencidas por pagar"))]:
			section = data.get(section_key, {})
			if not isinstance(section, dict):
				continue
			partners = section.get("partners", [])
			period_total = section.get("period_total", {})
			if partners or any(period_total.get(k) and str(period_total.get(k)) != "0.00" for k in ["period0", "period1", "period2", "period3", "period4", "period5", "total"]):
				worksheet.write(row, 0, section.get("section_label", section_label), section_label_style)
				row += 2
				row = self._write_ageing_section_excel(
					worksheet, row, partners, periods, period_total, expanded,
					currency_symbol, header_style, account_header_style, line_style, total_style
				)

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode("utf-8")
		return {"excel_file": excel_file, "file_name": "Partner Ageing.xls"}