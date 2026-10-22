# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import formatLang
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter
from odoo import fields, models, api, _, SUPERUSER_ID

class TrialBalanceReport(models.Model):
	_name = 'trial.balance.report'
	_description = 'Trial Balance Report'
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
	date_to = fields.Date(string="Date To")
	journal_ids = fields.Many2many('account.journal', string='Journals')
	account_ids = fields.Many2many('account.account', string='Accounts')
	account_tag_ids = fields.Many2many('account.account.tag', string="Account Tags")
	partner_ids = fields.Many2many('res.partner', string="Partners")
	target_move = fields.Selection([('posted', 'All Posted Entries'), ('all', 'All Entries')], 
								   string='Target Moves', default='all')
	date_range = fields.Selection(DATE_SELECTION,string="Compare Date Range", default='this_financialyear')

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


	def action_apply_filters_trial_balance(self):
		self.ensure_one()
		context = {
			'date_from': self.date_from,
			'date_to': self.date_to,
			'date_range': self.date_range,
			'target_move': self.target_move,
			'journal_ids': self.journal_ids.ids if self.journal_ids else None,
			'account_ids': self.account_ids.ids if self.account_ids else None,
			'partner_ids': self.partner_ids.ids if self.partner_ids else None,
			'account_tag_ids': self.account_tag_ids.ids if self.account_tag_ids else None,
		}
		records = self.with_context(context).get_data_trial_balance()
		return {
			'type': 'ir.actions.client',
			'tag': 'trial_balance_report_tag',
			'name': "Trial Balance",
			'params': {
				'filtered_records': records if records else [],
			},
			'target': 'current',
		}

	@api.model
	def get_data_trial_balance(self,date_range=None):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		date_from = context.get("date_from") or (existing_record.date_from if existing_record else False) or self.date_from
		date_to = context.get("date_to") or (existing_record.date_to if existing_record else False) or self.date_to
		date_range = context.get("date_range") or (existing_record.date_range if existing_record else False) or self.date_range
		journal_ids = context.get("journal_ids", existing_record.journal_ids.ids if existing_record and existing_record.journal_ids else [])
		account_ids = context.get("account_ids", existing_record.account_ids.ids if existing_record.account_ids else [])
		partner_ids = context.get("partner_ids", existing_record.partner_ids.ids if existing_record.partner_ids else [])
		account_tag_ids = context.get("account_tag_ids", existing_record.account_tag_ids.ids if existing_record.account_tag_ids else [])
		target_move = context.get("target_move", existing_record.target_move if existing_record else 'all')
		display_account = context.get("display_account", "movement")
		def format_amount(amount):
			return formatLang(self.env, amount, currency_obj=self.env.company.currency_id)
		
		if not (date_from and date_to):
			fiscal_year = get_fiscal_year(fields.Date.today())
			date_from = fiscal_year[0]
			date_to = fields.Date.today()

		domain = []
		if journal_ids:
			domain.append(('journal_id', 'in', journal_ids))
		if target_move == 'posted':
			domain.append(('parent_state', '=', 'posted'))
		elif target_move == 'all':
			domain.append(('parent_state', 'in', ['draft', 'posted']))

		if partner_ids:
			domain.append(('partner_id', 'in', partner_ids))
		
		account_filter = (context.get("account_filter") or "").strip()
		account_domain = []
		if account_ids:
			account_domain.append(('id', 'in', account_ids))
		if account_tag_ids:
			account_domain.append(('tag_ids', 'in', account_tag_ids))
		if account_filter:
			account_domain.extend([
				'|',
				('code', 'ilike', account_filter),
				('name', 'ilike', account_filter),
			])

		accounts = self.env['account.account'].search(account_domain)

		GROUP_ORDER = [
			('asset', 1, _('Activo')),
			('liability', 2, _('Pasivo')),
			('equity', 3, _('Patrimonio')),
			('income', 4, _('Ingresos')),
			('expense', 5, _('Gastos')),
			('off', 6, _('Fuera de balance')),
		]
		group_map = {g[0]: {'order': g[1], 'label': g[2]} for g in GROUP_ORDER}

		account_data = []
		total_initial_debit = 0.0
		total_initial_credit = 0.0
		total_period_debit = 0.0
		total_period_credit = 0.0
		total_ending_debit = 0.0
		total_ending_credit = 0.0
		
		for account in accounts:
			period_domain = domain + [('account_id', '=', account.id)]
			if date_from:
				period_domain.append(('date', '>=', date_from))
			if date_to:
				period_domain.append(('date', '<=', date_to))
			period_lines = self.env['account.move.line'].search(period_domain)

			initial_credit = 0.0
			initial_debit = 0.0
			if date_from:
				initial_account_domain = domain + [('account_id', '=', account.id), ('date', '<', date_from)]
				initial_lines = self.env['account.move.line'].search(initial_account_domain)
				initial_debit = sum(line.debit for line in initial_lines)
				initial_credit = sum(line.credit for line in initial_lines)

			period_credit = 0.0
			period_debit = 0.0
			if period_lines:
				period_debit = sum(line.debit for line in period_lines)
				period_credit = sum(line.credit for line in period_lines)

			if display_account == "movement" and not period_lines and not (initial_debit or initial_credit):
				continue
			if display_account == "not_zero" and not (
				abs(initial_debit - initial_credit) >= 0.005
				or abs(period_debit - period_credit) >= 0.005
				or abs((initial_debit + period_debit) - (initial_credit + period_credit)) >= 0.005
			):
				continue

			total_debit = initial_debit + period_debit
			total_credit = initial_credit + period_credit
			debit_credit_diff = total_debit - total_credit
			if debit_credit_diff > 0:
				ending_debit = debit_credit_diff
				ending_credit = 0.0
			else:
				ending_debit = 0.0
				ending_credit = abs(debit_credit_diff)

			balance_inicial = initial_debit - initial_credit
			balance_final = ending_debit - ending_credit

			internal_group = account.internal_group or 'asset'
			group_info = group_map.get(internal_group, {'order': 99, 'label': internal_group})

			account_data.append({
				'id': account.id,
				'code': account.code,
				'name': account.name,
				'internal_group': internal_group,
				'group_order': group_info['order'],
				'group_label': group_info['label'],
				'group_id': account.group_id.id if account.group_id else None,
				'initial_debit': format_amount(initial_debit),
				'initial_credit': format_amount(initial_credit),
				'period_debit': format_amount(period_debit),
				'period_credit': format_amount(period_credit),
				'ending_debit': format_amount(ending_debit),
				'ending_credit': format_amount(ending_credit),
				'balance_inicial': format_amount(balance_inicial),
				'balance_inicial_negative': balance_inicial < 0,
				'balance_final': format_amount(balance_final),
				'balance_final_negative': balance_final < 0,
				'balance_inicial_raw': balance_inicial,
				'balance_final_raw': balance_final,
				'period_debit_raw': period_debit,
				'period_credit_raw': period_credit,
				'initial_debit_raw': initial_debit,
				'initial_credit_raw': initial_credit,
				'ending_debit_raw': ending_debit,
				'ending_credit_raw': ending_credit,
			})
			
			total_initial_debit += initial_debit
			total_initial_credit += initial_credit
			total_period_debit += period_debit
			total_period_credit += period_credit
			total_ending_debit += ending_debit
			total_ending_credit += ending_credit
		account_data.sort(key=lambda x: (x['group_order'], x['code']))

		# Build id->account_data map for hierarchy
		account_by_id = {a['id']: a for a in account_data}

		total_balance_inicial = total_initial_debit - total_initial_credit
		total_balance_final = total_ending_debit - total_ending_credit

		has_draft_warning = False
		if target_move == "posted":
			draft_count = self.env["account.move.line"].search_count([
				("display_type", "=", False),
				("parent_state", "=", "draft"),
				("date", ">=", date_from or "1900-01-01"),
				("date", "<=", date_to or "2100-12-31"),
			])
			has_draft_warning = draft_count > 0

		# Build hierarchy: prefer account.group; fallback to code-prefix tree when
		# account codes don't align with catalog (e.g. 1010101 vs 110101)
		hierarchy = self._build_account_group_hierarchy(
			account_by_id, accounts, format_amount
		)
		if hierarchy and self._hierarchy_too_flat(hierarchy):
			hierarchy = self._build_code_prefix_hierarchy(
				account_by_id, format_amount
			)

		balance_dict = {
			'accounts': account_data,
			'hierarchy': hierarchy,
			'use_hierarchy': bool(hierarchy) and context.get('hierarchy', True),
			'journal_ids': journal_ids,
			'date_from': date_from,
			'date_to': date_to,
			'total_initial_debit': format_amount(total_initial_debit),
			'total_initial_credit': format_amount(total_initial_credit),
			'total_period_debit': format_amount(total_period_debit),
			'total_period_credit': format_amount(total_period_credit),
			'total_ending_debit': format_amount(total_ending_debit),
			'total_ending_credit': format_amount(total_ending_credit),
			'total_balance_inicial': format_amount(total_balance_inicial),
			'total_balance_inicial_negative': total_balance_inicial < 0,
			'total_balance_final': format_amount(total_balance_final),
			'total_balance_final_negative': total_balance_final < 0,
			'has_draft_warning': has_draft_warning,
			'currency': {
				'id': self.env.company.currency_id.id,
				'symbol': self.env.company.currency_id.symbol,
				'position': self.env.company.currency_id.position,
				'decimal_places': self.env.company.currency_id.decimal_places,
			}
		}

		if self._an_columns_enabled():
			columns = self._an_build_columns()
			balance_dict['columns'] = columns
			balance_dict['column_mode'] = 'analytic'
			balance_dict['analytic_matrix'] = self._an_trial_balance_matrix(
				accounts, account_by_id, date_from, date_to, columns
			)

		report_cur = context.get('report_currency_id')
		if report_cur:
			account_data, balance_dict = self.env['bi.report.currency.helper'].apply_trial_balance(
				account_data, balance_dict, report_cur, date_to)
		return account_data, balance_dict

	@api.model
	def _an_trial_balance_matrix(self, accounts, account_by_id, date_from, date_to, columns):
		"""Analytic-columns matrix for the Trial Balance (period balance per analytic)."""
		column_keys = [c["key"] for c in columns]
		analytic_ids = [c["analytic_id"] for c in columns if c.get("analytic_id")]
		# Period balance per analytic account (no income sign flip in a trial balance).
		by_analytic = self._an_analytic_balance_map(
			accounts, analytic_ids, date_from, date_to, flip_income=False
		)

		GROUP_ORDER = [
			('asset', _('Activo')),
			('liability', _('Pasivo')),
			('equity', _('Patrimonio')),
			('income', _('Ingresos')),
			('expense', _('Gastos')),
			('off', _('Fuera de balance')),
		]

		def account_values(account_id):
			data = account_by_id.get(account_id, {})
			total = (data.get("period_debit_raw", 0.0) or 0.0) - (data.get("period_credit_raw", 0.0) or 0.0)
			values = {}
			for col in columns:
				if col.get("analytic_id"):
					values[col["key"]] = by_analytic.get(col["analytic_id"], {}).get(account_id, 0.0)
				else:
					values[col["key"]] = total
			return values

		grouped = defaultdict(list)
		for data in account_by_id.values():
			grouped[data.get("internal_group", "asset")].append(data)

		rows = []
		for ig, label in GROUP_ORDER:
			accs = sorted(grouped.get(ig, []), key=lambda a: a.get("code") or "")
			if not accs:
				continue
			children = []
			group_totals = {ck: 0.0 for ck in column_keys}
			for data in accs:
				values = account_values(data["id"])
				for ck in column_keys:
					group_totals[ck] += values.get(ck, 0.0)
				children.append({
					"type": "account",
					"key": "tb_acc_%s" % data["id"],
					"parent": "tb_grp_%s" % ig,
					"account_id": data["id"],
					"label": ("%s %s" % (data.get("code") or "", data.get("name") or "")).strip(),
					"level": 1,
					"values": values,
				})
			rows.append({
				"type": "section",
				"key": "tb_grp_%s" % ig,
				"label": label,
				"level": 0,
				"expandable": bool(children),
				"values": group_totals,
				"children": children,
			})
		return {"columns": columns, "rows": rows}

	def _build_account_group_hierarchy(self, account_by_id, accounts_searched, format_amount):
		"""Build hierarchical structure from account.group (parent_id tree).
		Returns list of root nodes. Each node: type, key, code, name, level, children, totals.
		"""
		AccountGroup = self.env['account.group'].with_user(SUPERUSER_ID)
		company = self.env.company
		company_ids = [company.id]
		if hasattr(company, 'root_id') and company.root_id and company.root_id.id != company.id:
			company_ids.append(company.root_id.id)

		groups = AccountGroup.search([
			('company_id', 'in', company_ids),
		], order='code_prefix_start')
		if not groups:
			return []

		# Map group_id -> list of account ids (direct: account.group_id = group)
		direct_account_ids = defaultdict(list)
		for acc in accounts_searched:
			group_id = acc.group_id.id if acc.group_id else None
			if group_id and acc.id in account_by_id:
				direct_account_ids[group_id].append(acc.id)

		def build_node(group, level):
			gid = group.id
			code = group.code_prefix_start or ''
			name = group.name or ''
			key = f"ag_{gid}"
			# Direct accounts in this group
			acc_ids = direct_account_ids.get(gid, [])
			child_accounts = [account_by_id[aid] for aid in acc_ids]
			# Child groups
			child_groups = groups.filtered(lambda g: g.parent_id and g.parent_id.id == gid)
			child_groups = child_groups.sorted(
				key=lambda g: (len(g.code_prefix_start or ''), g.code_prefix_start or '')
			)

			children = []
			for cg in child_groups:
				children.append(build_node(cg, level + 1))
			for acc_data in sorted(child_accounts, key=lambda a: a['code']):
				children.append({
					'type': 'account',
					'key': f"acc_{acc_data['id']}",
					'id': acc_data['id'],
					'code': acc_data['code'],
					'name': acc_data['name'],
					'level': level + 1,
					'children': [],
					'balance_inicial': acc_data['balance_inicial'],
					'balance_inicial_negative': acc_data.get('balance_inicial_negative', False),
					'period_debit': acc_data['period_debit'],
					'period_credit': acc_data['period_credit'],
					'balance_final': acc_data['balance_final'],
					'balance_final_negative': acc_data.get('balance_final_negative', False),
				})

			# Aggregate totals from children
			bi_raw = 0.0
			bf_raw = 0.0
			pd_raw = 0.0
			pc_raw = 0.0
			for c in children:
				if c['type'] == 'account':
					acc_raw = account_by_id.get(c['id'], {})
					bi_raw += acc_raw.get('balance_inicial_raw', 0)
					bf_raw += acc_raw.get('balance_final_raw', 0)
					pd_raw += acc_raw.get('period_debit_raw', 0)
					pc_raw += acc_raw.get('period_credit_raw', 0)
				else:
					bi_raw += c.get('total_balance_inicial_raw', 0)
					bf_raw += c.get('total_balance_final_raw', 0)
					pd_raw += c.get('total_period_debit_raw', 0)
					pc_raw += c.get('total_period_credit_raw', 0)

			return {
				'type': 'group',
				'id': gid,
				'key': key,
				'code': code,
				'name': name,
				'label': f"{code} {name}".strip() if code else name,
				'level': level,
				'children': children,
				'total_balance_inicial': format_amount(bi_raw),
				'total_balance_inicial_negative': bi_raw < 0,
				'total_balance_final': format_amount(bf_raw),
				'total_balance_final_negative': bf_raw < 0,
				'total_period_debit': format_amount(pd_raw),
				'total_period_credit': format_amount(pc_raw),
				'total_balance_inicial_raw': bi_raw,
				'total_balance_final_raw': bf_raw,
				'total_period_debit_raw': pd_raw,
				'total_period_credit_raw': pc_raw,
			}

		root_groups = groups.filtered(lambda g: not g.parent_id).sorted(
			key=lambda g: (len(g.code_prefix_start or ''), g.code_prefix_start or '')
		)
		result = []
		for rg in root_groups:
			result.append(build_node(rg, 0))

		# Accounts without group_id: add under internal_group sections
		ungrouped = [a for a in account_by_id.values() if not a.get('group_id')]
		if ungrouped:
			GROUP_FALLBACK = [
				('asset', _('Activo')),
				('liability', _('Pasivo')),
				('equity', _('Patrimonio')),
				('income', _('Ingresos')),
				('expense', _('Gastos')),
				('off', _('Fuera de balance')),
			]
			by_internal = defaultdict(list)
			for d in ungrouped:
				ig = d.get('internal_group', 'asset')
				by_internal[ig].append(d)
			for ig, label in GROUP_FALLBACK:
				accs = sorted(by_internal.get(ig, []), key=lambda a: a['code'])
				if not accs:
					continue
				bi_raw = sum(a.get('balance_inicial_raw', 0) for a in accs)
				bf_raw = sum(a.get('balance_final_raw', 0) for a in accs)
				pd_raw = sum(a.get('period_debit_raw', 0) for a in accs)
				pc_raw = sum(a.get('period_credit_raw', 0) for a in accs)
				children = [{
					'type': 'account',
					'key': f"acc_{a['id']}",
					'id': a['id'],
					'code': a['code'],
					'name': a['name'],
					'level': 1,
					'children': [],
					'balance_inicial': a['balance_inicial'],
					'balance_inicial_negative': a.get('balance_inicial_negative', False),
					'period_debit': a['period_debit'],
					'period_credit': a['period_credit'],
					'balance_final': a['balance_final'],
					'balance_final_negative': a.get('balance_final_negative', False),
				} for a in accs]
				result.append({
					'type': 'group',
					'id': None,
					'key': f"ig_{ig}",
					'code': '',
					'name': label,
					'label': label,
					'level': 0,
					'children': children,
					'total_balance_inicial': format_amount(bi_raw),
					'total_balance_inicial_negative': bi_raw < 0,
					'total_balance_final': format_amount(bf_raw),
					'total_balance_final_negative': bf_raw < 0,
					'total_period_debit': format_amount(pd_raw),
					'total_period_credit': format_amount(pc_raw),
					'total_balance_inicial_raw': bi_raw,
					'total_balance_final_raw': bf_raw,
					'total_period_debit_raw': pd_raw,
					'total_period_credit_raw': pc_raw,
				})

		return result

	def _hierarchy_too_flat(self, hierarchy):
		"""True when accounts pile up under roots instead of catalog sub-groups (e.g. 101 vs 11)."""
		for node in hierarchy:
			if node.get('type') != 'group':
				continue
			acc_count = sum(1 for c in (node.get('children') or []) if c.get('type') == 'account')
			group_count = sum(1 for c in (node.get('children') or []) if c.get('type') == 'group')
			# Root has both sub-groups and many direct accounts → codes don't match catalog
			if acc_count >= 3 and group_count > 0:
				return True
		return False

	def _build_code_prefix_hierarchy(self, account_by_id, format_amount):
		"""Build hierarchy from account code prefixes when catalog structure doesn't match."""
		# Extract code without suffix (e.g. "1010101.01" -> "1010101")
		def code_base(code):
			if not code:
				return ""
			return str(code).split(".")[0].rstrip("0") or str(code).split(".")[0]

		# Build prefix path for an account. Use natural breakpoints: 1, 2, 4, 6 digits
		# e.g. 1010101 -> [1, 10, 1010, 101010]; 1010102 -> [1, 10, 1010, 101010]
		def prefix_path(code):
			base = code_base(code)
			if not base:
				return []
			digits = ''.join(c for c in base if c.isdigit())
			if not digits:
				return [base] if base else []
			# Breakpoints: 1, 2, 3, 4, 5, 6, 7... (standard) or 1,2,4,6
			breakpoints = [1, 2, 4, 6, 8]
			path = []
			for bp in breakpoints:
				if bp <= len(digits):
					prefix = digits[:bp]
					if prefix and (not path or path[-1] != prefix):
						path.append(prefix)
			if path and (not path or path[-1] != digits):
				path.append(digits)
			return path

		# Tree: prefix -> {name, children_prefixes, account_ids}
		tree = {}
		prefix_to_accounts = defaultdict(list)
		prefix_to_info = {}  # prefix -> (name from account.group if exists)

		AccountGroup = self.env['account.group'].with_user(SUPERUSER_ID)
		company_ids = [self.env.company.id]
		if hasattr(self.env.company, 'root_id') and self.env.company.root_id and self.env.company.root_id.id != self.env.company.id:
			company_ids.append(self.env.company.root_id.id)
		groups = AccountGroup.search([('company_id', 'in', company_ids)], order='code_prefix_start')
		group_by_prefix = {g.code_prefix_start: g for g in groups}

		for acc_data in account_by_id.values():
			code = acc_data.get('code') or ''
			path = prefix_path(code)
			if len(path) < 2:
				prefix_to_accounts[path[0] if path else 'other'].append(acc_data['id'])
				continue
			leaf_prefix = path[-1]
			prefix_to_accounts[leaf_prefix].append(acc_data['id'])
			for p in path:
				tree[p] = tree.get(p, {'prefix': p, 'parent': path[path.index(p) - 1] if path.index(p) > 0 else None})

		# Build nodes recursively
		def make_node(prefix, level, parent_prefix=None):
			acc_ids = prefix_to_accounts.get(prefix, [])
			group = group_by_prefix.get(prefix)
			name = group.name if group else _("Cuentas %s") % prefix
			key = f"cp_{prefix}"
			children = []
			for child_prefix, data in tree.items():
				if data.get('parent') == prefix:
					children.append(make_node(child_prefix, level + 1, prefix))
			for aid in sorted(acc_ids):
				acc = account_by_id.get(aid, {})
				children.append({
					'type': 'account',
					'key': f"acc_{acc.get('id')}",
					'id': acc.get('id'),
					'code': acc.get('code'),
					'name': acc.get('name'),
					'level': level + 1,
					'children': [],
					'balance_inicial': acc.get('balance_inicial'),
					'balance_inicial_negative': acc.get('balance_inicial_negative', False),
					'period_debit': acc.get('period_debit'),
					'period_credit': acc.get('period_credit'),
					'balance_final': acc.get('balance_final'),
					'balance_final_negative': acc.get('balance_final_negative', False),
				})
			children.sort(key=lambda c: (c.get('type') != 'group', c.get('code', '') if c.get('type') == 'account' else c.get('prefix', '')))

			bi_raw = 0.0
			bf_raw = 0.0
			pd_raw = 0.0
			pc_raw = 0.0
			for c in children:
				if c.get('type') == 'account':
					acc = account_by_id.get(c['id'], {})
					bi_raw += acc.get('balance_inicial_raw', 0)
					bf_raw += acc.get('balance_final_raw', 0)
					pd_raw += acc.get('period_debit_raw', 0)
					pc_raw += acc.get('period_credit_raw', 0)
				else:
					bi_raw += c.get('total_balance_inicial_raw', 0)
					bf_raw += c.get('total_balance_final_raw', 0)
					pd_raw += c.get('total_period_debit_raw', 0)
					pc_raw += c.get('total_period_credit_raw', 0)

			node = {
				'type': 'group',
				'id': group.id if group else None,
				'key': key,
				'code': prefix,
				'name': name,
				'label': f"{prefix} {name}".strip(),
				'level': level,
				'prefix': prefix,
				'children': children,
				'total_balance_inicial': format_amount(bi_raw),
				'total_balance_inicial_negative': bi_raw < 0,
				'total_balance_final': format_amount(bf_raw),
				'total_balance_final_negative': bf_raw < 0,
				'total_period_debit': format_amount(pd_raw),
				'total_period_credit': format_amount(pc_raw),
				'total_balance_inicial_raw': bi_raw,
				'total_balance_final_raw': bf_raw,
				'total_period_debit_raw': pd_raw,
				'total_period_credit_raw': pc_raw,
			}
			return node

		result = []
		root_prefixes = sorted([p for p, d in tree.items() if d.get('parent') is None], key=lambda x: (len(x), x))
		for rp in root_prefixes:
			result.append(make_node(rp, 0))

		# Handle accounts with no valid path (empty/malformed code)
		other_ids = prefix_to_accounts.get('other', [])
		for p, aids in prefix_to_accounts.items():
			if p not in tree and p != 'other':
				other_ids.extend(aids)
		if other_ids:
			GROUP_FALLBACK = [('asset', _('Activo')), ('liability', _('Pasivo')), ('equity', _('Patrimonio')), ('income', _('Ingresos')), ('expense', _('Gastos')), ('off', _('Fuera de balance'))]
			by_internal = defaultdict(list)
			for aid in other_ids:
				d = account_by_id.get(aid, {})
				if d:
					by_internal[d.get('internal_group', 'asset')].append(d)
			for ig, label in GROUP_FALLBACK:
				accs = sorted(by_internal.get(ig, []), key=lambda a: a['code'])
				if accs:
					children = [{'type': 'account', 'key': f"acc_{a['id']}", 'id': a['id'], 'code': a['code'], 'name': a['name'], 'level': 1, 'children': [], **{k: a.get(k) for k in ['balance_inicial', 'balance_inicial_negative', 'period_debit', 'period_credit', 'balance_final', 'balance_final_negative']}} for a in accs]
					bi_raw = sum(a.get('balance_inicial_raw', 0) for a in accs)
					bf_raw = sum(a.get('balance_final_raw', 0) for a in accs)
					result.append({'type': 'group', 'key': f"ig_{ig}", 'code': '', 'name': label, 'label': label, 'level': 0, 'children': children, 'total_balance_inicial': format_amount(bi_raw), 'total_balance_inicial_negative': bi_raw < 0, 'total_balance_final': format_amount(bf_raw), 'total_balance_final_negative': bf_raw < 0, 'total_period_debit': format_amount(sum(a.get('period_debit_raw', 0) for a in accs)), 'total_period_credit': format_amount(sum(a.get('period_credit_raw', 0) for a in accs)), 'total_balance_inicial_raw': bi_raw, 'total_balance_final_raw': bf_raw, 'total_period_debit_raw': sum(a.get('period_debit_raw', 0) for a in accs), 'total_period_credit_raw': sum(a.get('period_credit_raw', 0) for a in accs)})

		return result

	@api.model
	def trial_balance_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Trial Balance")

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
			'pattern: pattern solid,fore_colour gray25;'
		)

		col_widths = [45, 20, 20, 20, 20, 20, 20]
		for i, width in enumerate(col_widths):
			worksheet.col(i+1).width = 256 * width

		balanceData = data.get('balanceData', [])
		accountData = data.get('accountData', {})
		
		date_from=''
		date_to=''
		if balanceData['date_from']:
			date_from = f'From {balanceData["date_from"]}'
		if balanceData['date_to']:
			date_to = f'To {balanceData["date_to"]}'

		worksheet.write_merge(1, 3, 2, 5, "Trial Balance", title_style)
		today = datetime.now().strftime("%d-%m-%Y")
		worksheet.write_merge(6, 6, 2, 5, f"{date_from} {date_to} ", sub_header_style)

		worksheet.write_merge(8, 8, 2, 3, "Initial Balance", header_style)
		worksheet.write_merge(8, 8, 4, 5, "Trial Balance", header_style)
		worksheet.write_merge(8, 8, 6, 7, "End Balance", header_style)

		headers = ["Account", "Debit", "Credit", "Debit", "Credit", "Debit", "Credit"]
		row = 9
		for col, header in enumerate(headers):
			worksheet.write(row, col+1, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		for account in accountData:
			worksheet.write(row, 1, f"{account['code'] + ' ' + account['name']}", account_header_style)
			worksheet.write(row, 2, account['initial_debit'], line_style)
			worksheet.write(row, 3, account['initial_credit'], line_style)
			worksheet.write(row, 4, account['period_debit'], line_style)
			worksheet.write(row, 5, account['period_credit'], line_style)
			worksheet.write(row, 6, account['ending_debit'], line_style)
			worksheet.write(row, 7, account['ending_credit'], line_style)

			worksheet.row(row).height = 360
			row += 1

		worksheet.write(row, 1, "Total", total_style)
		worksheet.write(row, 2, balanceData['total_initial_debit'], total_style)
		worksheet.write(row, 3, balanceData['total_initial_credit'], total_style)
		worksheet.write(row, 4, balanceData['total_period_debit'], total_style)
		worksheet.write(row, 5, balanceData['total_period_credit'], total_style)
		worksheet.write(row, 6, balanceData['total_ending_debit'], total_style)
		worksheet.write(row, 7, balanceData['total_ending_credit'], total_style)
		worksheet.row(row).height = 400

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'Trial Balance.xls',
		}

	@api.model
	def trial_balance_owl_xlsx(self, data):
		"""Export XLSX desde la vista OWL (lista accounts + totales en data)."""
		if (data or {}).get('column_mode') == 'analytic':
			return self._an_matrix_xlsx(data, _('Balance de comprobación'))
		output = io.BytesIO()
		workbook = xlsxwriter.Workbook(output, {'in_memory': True})
		sheet = workbook.add_worksheet(_('Balance de comprobación'))
		bold = workbook.add_format({'bold': True})
		money = workbook.add_format({'num_format': '#,##0.00'})
		row = 0
		sheet.write(row, 0, _('Balance de comprobación'), bold)
		row += 1
		sheet.write(row, 0, str(data.get('date_from') or ''))
		sheet.write(row, 1, str(data.get('date_to') or ''))
		row += 1
		headers = [_('Código'), _('Cuenta'), _('Saldo inicial'), _('Debe período'), _('Haber período'), _('Saldo final')]
		for c, h in enumerate(headers):
			sheet.write(row, c, h, bold)
		row += 1
		for acc in data.get('accounts') or []:
			if not isinstance(acc, dict):
				continue
			sheet.write(row, 0, acc.get('code') or '')
			sheet.write(row, 1, acc.get('name') or '')
			sheet.write(row, 2, acc.get('balance_inicial') or '')
			sheet.write(row, 3, acc.get('period_debit') or '')
			sheet.write(row, 4, acc.get('period_credit') or '')
			sheet.write(row, 5, acc.get('balance_final') or '')
			row += 1
		sheet.write(row, 0, _('Totales'), bold)
		sheet.write(row, 2, data.get('total_balance_inicial') or '')
		sheet.write(row, 3, data.get('total_period_debit') or '')
		sheet.write(row, 4, data.get('total_period_credit') or '')
		sheet.write(row, 5, data.get('total_balance_final') or '')
		workbook.close()
		output.seek(0)
		return {
			'excel_file': base64.b64encode(output.read()).decode('utf-8'),
			'file_name': 'Trial_balance.xlsx',
		}

	@api.model
	def action_open_aml(self, options, account_id):
		"""Drill-down a apuntes de la cuenta en el periodo del informe (o comparativa)."""
		opts = dict(options or {})
		helper = self.env['bi.report.drilldown.helper']
		domain = helper.aml_domain(opts, account_id=int(account_id))
		return helper.action_aml_window(domain)