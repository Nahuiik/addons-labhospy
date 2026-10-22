# -*- coding: utf-8 -*-
"""RPC backend for gn_banks treasury dashboard (OWL)."""

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Operation types exposed in filters / charts
DC_MOVE_TYPES = ('debit', 'credit', 'deposit', 'credit_card')
CHECK_MOVE_TYPES = ('check', 'transference')
DC_INFLOW_TYPES = ('credit', 'deposit', 'credit_card')
DC_OUTFLOW_TYPES = ('debit',)
# Outflow operation types across all treasury models (debit.credit, bank.check,
# bank.transfer). Used to split amounts into debit/credit columns in the
# breakdown/detail aggregations.
OUTFLOW_MOVE_TYPES = ('debit', 'check', 'transference', 'transference_banks')
# Internal movements (money between own accounts). They are NOT real cash
# inflows/outflows, so they are excluded from the net flow and the cashflow
# series; they remain visible as informational KPIs/breakdowns.
INTERNAL_MOVE_TYPES = ('transference', 'transference_banks')
HIGH_AMOUNT_THRESHOLD = 100000.0
FLOW_SOURCES = ('treasury', 'ledger')


class GnBanksDashboardService(models.AbstractModel):
    _name = 'gn.banks.dashboard.service'
    _description = 'Treasury dashboard data service (gn_banks)'

    # -------------------------------------------------------------------------
    # Public RPC
    # -------------------------------------------------------------------------

    @api.model
    def get_filter_options(self, company_id=None):
        company = self._company(company_id)
        Journal = self.env['account.journal']
        j_domain = [
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', company.id),
        ]
        journals = Journal.search(j_domain, order='name')
        branches = (
            self.env['res.branch'].search(
                [('company_id', '=', company.id)], order='name',
            )
            if 'res.branch' in self.env
            else self.env['res.branch']
        )
        currencies = self.env['res.currency'].search([('active', '=', True)], order='name')
        partners = []  # loaded on demand in UI via many2one
        users = self.env['res.users'].search(
            [('company_ids', 'in', company.id)], order='name', limit=200,
        )
        acc_domain = [('company_ids', 'in', company.id)]
        if 'deprecated' in self.env['account.account']._fields:
            acc_domain.append(('deprecated', '=', False))
        accounts = self.env['account.account'].search(acc_domain, order='code', limit=500)
        analytics = self.env['account.analytic.account'].search([
            ('company_id', '=', company.id),
        ], order='name', limit=200) if 'account.analytic.account' in self.env else []

        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        return {
            'company_id': company.id,
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
            'multi_company': len(self.env.companies) > 1,
            'currency_id': company.currency_id.id,
            'currency_name': company.currency_id.name,
            'currency_symbol': company.currency_id.symbol or company.currency_id.name,
            'date_from': fields.Date.to_string(month_start),
            'date_to': fields.Date.to_string(today),
            'journals': [
                {
                    'id': j.id,
                    'name': j.name,
                    'bank_name': j.bank_id.name if j.bank_id else _('No bank'),
                }
                for j in journals
            ],
            'all_journal_ids': journals.ids,
            'branches': [{'id': b.id, 'name': b.name} for b in branches],
            'currencies': [{'id': c.id, 'name': c.name} for c in currencies],
            'move_types': self._move_type_options(),
            'states': self._state_options(),
            'users': [{'id': u.id, 'name': u.name} for u in users],
            'permissions': self._user_permissions(),
        }

    @api.model
    def get_dashboard_data(self, filters):
        """Full payload for initial load (sections can be refreshed separately).

        ``_compute_kpi_values`` (current + previous period) is computed once and
        threaded into KPIs, insights and gauges to avoid recomputing the same
        heavy aggregations several times per request.
        """
        parsed = self._parse_filters(filters)
        prev_parsed = self._previous_parsed(parsed)
        current = self._compute_kpi_values(parsed)
        previous = self._compute_kpi_values(prev_parsed)

        return {
            'filters': self._filters_payload(parsed),
            'kpis': self._kpi_items(parsed, current, previous),
            'cashflow': self._build_cashflow_series(parsed),
            'charts': self._get_all_charts(parsed),
            'alerts': self._build_alerts(parsed),
            'summary_tables': self._summary_tables(parsed),
            'insights': self._build_insights(parsed, current, previous),
            'risk': self._build_risk(parsed),
            'indicator_gauges': self._build_indicator_gauges(parsed, current),
            'has_data': True,
        }

    @api.model
    def get_kpis(self, filters):
        parsed = self._parse_filters(filters)
        prev_parsed = self._previous_parsed(parsed)
        current = self._compute_kpi_values(parsed)
        previous = self._compute_kpi_values(prev_parsed)
        return self._kpi_items(parsed, current, previous)

    @api.model
    def _kpi_items(self, parsed, current, previous):
        return [
            self._kpi_item(key, current, previous, parsed)
            for key in self._kpi_keys(parsed)
        ]

    @api.model
    def get_cashflow(self, filters):
        parsed = self._parse_filters(filters)
        return self._build_cashflow_series(parsed)

    @api.model
    def get_distribution_by_type(self, filters):
        parsed = self._parse_filters(filters)
        return self._distribution(parsed, 'operation_type')

    @api.model
    def get_distribution_by_bank(self, filters):
        parsed = self._parse_filters(filters)
        return self._distribution(parsed, 'bank')

    @api.model
    def get_distribution_by_branch(self, filters):
        parsed = self._parse_filters(filters)
        return self._distribution(parsed, 'branch')

    @api.model
    def get_alerts(self, filters):
        parsed = self._parse_filters(filters)
        return self._build_alerts(parsed)

    @api.model
    def get_summary_tables(self, filters):
        return self._summary_tables(self._parse_filters(filters))

    @api.model
    def _summary_tables(self, parsed):
        dimensions = (
            'bank', 'branch', 'operation_type', 'state',
            'user', 'partner', 'account', 'analytic',
        )
        return {
            dim: self._summary_table(parsed, dim)
            for dim in dimensions
        }

    @api.model
    def get_insights(self, filters):
        parsed = self._parse_filters(filters)
        return self._build_insights(parsed)

    @api.model
    def get_risk_block(self, filters):
        parsed = self._parse_filters(filters)
        return self._build_risk(parsed)

    @api.model
    def get_indicator_gauges(self, filters):
        """Return gauge-ready indicators for the treasury dashboard."""
        parsed = self._parse_filters(filters)
        return self._build_indicator_gauges(parsed)

    @api.model
    def get_drilldown_action(self, metric, filters, extra_domain=None):
        parsed = self._parse_filters(filters)
        extra = extra_domain or []
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except (json.JSONDecodeError, TypeError):
                extra = []
        return self._action_for_metric(metric, parsed, extra)

    # -------------------------------------------------------------------------
    # Filters & permissions
    # -------------------------------------------------------------------------

    @api.model
    def _company(self, company_id=None):
        company = self.env['res.company'].browse(company_id or self.env.company.id)
        if not company.exists():
            raise UserError(_('Invalid company.'))
        if company not in self.env.companies:
            raise AccessError(_('You do not have access to this company.'))
        company.check_access('read')
        return company

    @api.model
    def _parse_filters(self, filters):
        filters = filters or {}
        company = self._company(filters.get('company_id'))
        today = fields.Date.context_today(self)
        date_from = filters.get('date_from') or fields.Date.to_string(today.replace(day=1))
        date_to = filters.get('date_to') or fields.Date.to_string(today)
        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)
        if date_from > date_to:
            raise UserError(_('Start date must be before end date.'))

        journal_ids = filters.get('journal_ids') or []
        branch_ids = filters.get('branch_ids') or []
        if filters.get('branch_id'):
            branch_ids = list(set(branch_ids + [filters['branch_id']]))

        flow_source = filters.get('flow_source') or 'treasury'
        if flow_source not in FLOW_SOURCES:
            flow_source = 'treasury'

        return {
            'company': company,
            'date_from': date_from,
            'date_to': date_to,
            'journal_ids': journal_ids,
            'branch_ids': branch_ids,
            'currency_id': filters.get('currency_id'),
            'move_types': filters.get('move_types') or [],
            'states': filters.get('states') or [],
            'partner_id': filters.get('partner_id'),
            'user_id': filters.get('user_id'),
            'account_id': filters.get('account_id'),
            'analytic_account_id': filters.get('analytic_account_id'),
            'flow_source': flow_source,
        }

    @api.model
    def _previous_parsed(self, parsed):
        prev = self._previous_period(parsed['date_from'], parsed['date_to'])
        return {**parsed, 'date_from': prev[0], 'date_to': prev[1]}

    @api.model
    def _filters_payload(self, parsed):
        return {
            'date_from': fields.Date.to_string(parsed['date_from']),
            'date_to': fields.Date.to_string(parsed['date_to']),
            'company_id': parsed['company'].id,
            'currency_symbol': parsed['company'].currency_id.symbol or '$',
            'flow_source': parsed['flow_source'],
        }

    @api.model
    def _user_permissions(self):
        user = self.env.user
        return {
            'debit_credit': user.has_group('gn_banks.banks_debit_credit_user')
                or user.has_group('gn_banks.banks_debit_credit_manager'),
            'checks': user.has_group('gn_banks.banks_check_user')
                or user.has_group('gn_banks.banks_check_manager'),
            'transfers': user.has_group('gn_banks.banks_check_manager'),
            'import': user.has_group('gn_banks.banks_import_credit_card'),
        }

    @api.model
    def _can_read_model(self, model_name):
        try:
            self.env[model_name].check_access('read')
            return True
        except AccessError:
            return False

    @api.model
    def _previous_period(self, date_from, date_to):
        delta = (date_to - date_from).days + 1
        prev_end = date_from - timedelta(days=1)
        prev_start = prev_end - timedelta(days=delta - 1)
        return prev_start, prev_end

    @api.model
    def _move_type_options(self):
        opts = []
        if self._can_read_model('debit.credit'):
            for code, label in [
                ('debit', _('Debit')),
                ('credit', _('Credit')),
                ('deposit', _('Deposit')),
                ('credit_card', _('POS liquidation')),
            ]:
                opts.append({'id': code, 'name': label, 'model': 'debit.credit'})
        if self._can_read_model('bank.check'):
            for code, label in [
                ('check', _('Check')),
                ('transference', _('Transference')),
            ]:
                opts.append({'id': code, 'name': label, 'model': 'bank.check'})
        if self._can_read_model('bank.transfer'):
            opts.append({
                'id': 'transference_banks',
                'name': _('Bank transfer'),
                'model': 'bank.transfer',
            })
        return opts

    @api.model
    def _state_options(self):
        return [
            {'id': 'draft', 'name': _('Draft')},
            {'id': 'validated', 'name': _('Validated')},
            {'id': 'postdated', 'name': _('Post-dated')},
            {'id': 'cancel', 'name': _('Cancelled')},
        ]

    # -------------------------------------------------------------------------
    # Domain builders
    # -------------------------------------------------------------------------

    @api.model
    def _base_dc_domain(self, parsed, extra=None):
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
        ]
        if parsed['journal_ids']:
            domain.append(('journal_id', 'in', parsed['journal_ids']))
        if parsed['branch_ids']:
            domain.append(('branch_id', 'in', parsed['branch_ids']))
        if parsed['currency_id']:
            domain.append(('currency_id', '=', parsed['currency_id']))
        if parsed['states']:
            domain.append(('state', 'in', parsed['states']))
        if parsed['partner_id']:
            domain.append(('partner_id', '=', parsed['partner_id']))
        if parsed['user_id']:
            domain.append(('create_uid', '=', parsed['user_id']))
        if extra:
            domain.extend(extra)
        return domain

    @api.model
    def _base_check_domain(self, parsed, extra=None):
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
        ]
        if parsed['journal_ids']:
            domain.append(('journal_id', 'in', parsed['journal_ids']))
        if parsed['branch_ids']:
            domain.append(('branch_id', 'in', parsed['branch_ids']))
        if parsed['currency_id']:
            domain.append(('currency_id', '=', parsed['currency_id']))
        if parsed['states']:
            domain.append(('state', 'in', parsed['states']))
        if parsed['partner_id']:
            domain.append(('partner_id', '=', parsed['partner_id']))
        if parsed['user_id']:
            domain.append(('create_uid', '=', parsed['user_id']))
        if extra:
            domain.extend(extra)
        return domain

    @api.model
    def _base_transfer_domain(self, parsed, extra=None):
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
        ]
        if parsed['journal_ids']:
            domain.append('|')
            domain.append(('journal_id', 'in', parsed['journal_ids']))
            domain.append(('dest_journal_id', 'in', parsed['journal_ids']))
        if parsed['branch_ids']:
            domain.append(('branch_id', 'in', parsed['branch_ids']))
        if parsed['currency_id']:
            domain.append(('currency_id', '=', parsed['currency_id']))
        if parsed['states']:
            domain.append(('state', 'in', parsed['states']))
        if parsed['user_id']:
            domain.append(('create_uid', '=', parsed['user_id']))
        if extra:
            domain.extend(extra)
        return domain

    @api.model
    def _no_analytic_domain(self):
        return [
            ('analytic_distribution', 'in', [False, '{}', '']),
            ('analytic_account_id', '=', False),
        ]

    @api.model
    def _to_company(self, amount, currency, company):
        """Convert ``amount`` (in ``currency``) to the company currency.

        Multi-currency documents are otherwise summed at face value, mixing
        currencies in the KPIs. Conversion uses the rate effective today.
        """
        amount = float(amount or 0.0)
        if not amount:
            return 0.0
        if currency and currency != company.currency_id:
            return currency._convert(
                amount, company.currency_id, company,
                fields.Date.context_today(self),
            )
        return amount

    @api.model
    def _sum_total_company(self, model, domain, company):
        """Sum ``total`` of ``model`` over ``domain`` in company currency.

        Returns ``(amount, count)``. Groups by currency so foreign-currency
        documents are converted instead of mixed.
        """
        Model = self.env[model]
        if 'currency_id' in Model._fields:
            rows = Model._read_group(
                domain=domain, groupby=['currency_id'],
                aggregates=['total:sum', '__count'],
            )
            amount = 0.0
            count = 0
            for cur, total, cnt in rows:
                amount += self._to_company(total, cur, company)
                count += int(cnt or 0)
            return amount, count
        rows = Model._read_group(domain=domain, groupby=[], aggregates=['total:sum', '__count'])
        if not rows:
            return 0.0, 0
        return float(rows[0][0] or 0.0), int(rows[0][1] or 0)

    @api.model
    def _day_str(self, day):
        """Normalise a ``date:day`` read_group key to an ISO date string."""
        if not day:
            return None
        if isinstance(day, datetime):
            day = day.date()
        return fields.Date.to_string(day)

    @api.model
    def _grouped_total_by_day(self, model, domain, company):
        """``{iso_date: company_amount}`` summing ``total`` per day (1 query)."""
        Model = self.env[model]
        has_cur = 'currency_id' in Model._fields
        groupby = ['date:day', 'currency_id'] if has_cur else ['date:day']
        rows = Model._read_group(
            domain=domain, groupby=groupby, aggregates=['total:sum'],
        )
        out = {}
        for row in rows:
            if has_cur:
                day, cur, total = row
            else:
                day, total = row
                cur = None
            ds = self._day_str(day)
            if not ds:
                continue
            out[ds] = out.get(ds, 0.0) + self._to_company(total, cur, company)
        return out

    @api.model
    def _liquidity_accounts(self, parsed):
        """Bank/cash accounts behind the (optionally filtered) journals."""
        domain = [
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', parsed['company'].id),
        ]
        if parsed['journal_ids']:
            domain.append(('id', 'in', parsed['journal_ids']))
        journals = self.env['account.journal'].search(domain)
        return journals.mapped('default_account_id').filtered('id')

    @api.model
    def _read_group_dc(self, parsed, domain, groupby=None, aggregates=None):
        if not self._can_read_model('debit.credit'):
            return []
        DC = self.env['debit.credit']
        gb = groupby or []
        aggs = aggregates or ['total:sum', '__count']
        return DC._read_group(domain=domain, groupby=gb, aggregates=aggs)

    @api.model
    def _read_group_check(self, parsed, domain, groupby=None, aggregates=None):
        if not self._can_read_model('bank.check'):
            return []
        Check = self.env['bank.check']
        gb = groupby or []
        aggs = aggregates or ['total:sum', '__count']
        return Check._read_group(domain=domain, groupby=gb, aggregates=aggs)

    @api.model
    def _read_group_transfer(self, parsed, domain, groupby=None, aggregates=None):
        if not self._can_read_model('bank.transfer'):
            return []
        BT = self.env['bank.transfer']
        gb = groupby or []
        aggs = aggregates or ['total:sum', '__count']
        return BT._read_group(domain=domain, groupby=gb, aggregates=aggs)

    # -------------------------------------------------------------------------
    # KPI computation
    # -------------------------------------------------------------------------

    @api.model
    def _kpi_keys(self, parsed):
        keys = [
            'available_balance', 'period_inflow', 'period_outflow', 'net_flow',
            'debits', 'credits', 'deposits', 'pos_liquidations',
            'checks_issued', 'checks_pending', 'bank_transfers',
            'cancelled', 'no_analytic', 'no_branch', 'no_partner',
            'pending_validation', 'reconciled_amount', 'unreconciled_amount',
        ]
        return keys

    @api.model
    def _compute_kpi_values(self, parsed):
        company = parsed['company']
        vals = defaultdict(lambda: {'amount': 0.0, 'count': 0})

        # Treasury inflow/outflow built from gn_banks documents.
        treasury_inflow = treasury_inflow_cnt = 0.0
        treasury_outflow = treasury_outflow_cnt = 0.0

        # ---- debit.credit (single grouped query per move_type + currency) ----
        if self._can_read_model('debit.credit'):
            DC = self.env['debit.credit']
            base = self._base_dc_domain(parsed)
            rows = DC._read_group(
                domain=base + [('state', '=', 'validated')],
                groupby=['move_type', 'currency_id'],
                aggregates=['total:sum', '__count'],
            )
            for mt, cur, total, cnt in rows:
                vals[mt]['amount'] += self._to_company(total, cur, company)
                vals[mt]['count'] += int(cnt or 0)

            # POS settlements credit a control account for the *gross* amount;
            # the real cash that reaches the bank is the net deposit line. Use
            # that net for the inflow instead of the gross total.
            pos_net = self._pos_net_data(parsed)

            treasury_inflow = (
                vals['credit']['amount'] + vals['deposit']['amount'] + pos_net['total']
            )
            treasury_inflow_cnt = (
                vals['credit']['count'] + vals['deposit']['count'] + pos_net['count']
            )
            treasury_outflow = vals['debit']['amount']
            treasury_outflow_cnt = vals['debit']['count']

            vals['debits'] = dict(vals['debit'])
            vals['credits'] = dict(vals['credit'])
            vals['deposits'] = dict(vals['deposit'])
            # POS KPI keeps the gross volume (and count) as business metric.
            vals['pos_liquidations'] = dict(vals['credit_card'])

            vals['cancelled']['count'] = DC.search_count(base + [('state', '=', 'cancel')])
            vals['no_analytic']['count'] = DC.search_count(base + self._no_analytic_domain())
            vals['no_branch']['count'] = DC.search_count(base + [('branch_id', '=', False)])
            vals['no_partner']['count'] = DC.search_count(base + [('partner_id', '=', False)])
            vals['pending_validation']['count'] = DC.search_count(base + [('state', '=', 'draft')])
            vals['unbalanced']['count'] = DC.search_count(
                base + [('state', '=', 'draft'), ('amount_residual', '!=', 0)]
            )
            vals['no_move']['count'] = DC.search_count(
                base + [('state', '=', 'validated'), ('move_id', '=', False)]
            )
            vals['pos_no_invoice']['count'] = DC.search_count(
                base + [
                    ('move_type', '=', 'credit_card'),
                    ('state', '=', 'validated'),
                    ('bank_invoice_id', '=', False),
                ]
            )

        # ---- bank.check ----
        if self._can_read_model('bank.check'):
            Check = self.env['bank.check']
            cbase = self._base_check_domain(parsed)
            issued_amt, issued_cnt = self._sum_total_company(
                'bank.check',
                cbase + [('move_type', '=', 'check'), ('state', '=', 'validated')],
                company,
            )
            vals['checks_issued']['amount'] = issued_amt
            vals['checks_issued']['count'] = issued_cnt

            pend_amt, pend_cnt = self._sum_total_company(
                'bank.check',
                cbase + [('move_type', '=', 'check'), ('state', 'in', ('draft', 'postdated'))],
                company,
            )
            vals['checks_pending']['amount'] = pend_amt
            vals['checks_pending']['count'] = pend_cnt

            # Real outflow = issued checks only; internal transferences are
            # money moved between own accounts, not a treasury outflow.
            treasury_outflow += issued_amt
            treasury_outflow_cnt += issued_cnt

            vals['cancelled']['count'] += Check.search_count(cbase + [('state', '=', 'cancel')])
            vals['no_analytic']['count'] += Check.search_count(cbase + self._no_analytic_domain())
            vals['no_branch']['count'] += Check.search_count(cbase + [('branch_id', '=', False)])
            if 'partner_id' in Check._fields:
                vals['no_partner']['count'] += Check.search_count(cbase + [('partner_id', '=', False)])
            vals['pending_validation']['count'] += Check.search_count(cbase + [('state', '=', 'draft')])
            vals['no_move']['count'] += Check.search_count(
                cbase + [('state', '=', 'validated'), ('move_id', '=', False)]
            )

        # ---- bank.transfer (internal movements: informational only) ----
        if self._can_read_model('bank.transfer'):
            BT = self.env['bank.transfer']
            tbase = self._base_transfer_domain(parsed)
            bt_amt, bt_cnt = self._sum_total_company(
                'bank.transfer', tbase + [('state', '=', 'validated')], company,
            )
            vals['bank_transfers']['amount'] = bt_amt
            vals['bank_transfers']['count'] = bt_cnt
            vals['cancelled']['count'] += BT.search_count(tbase + [('state', '=', 'cancel')])
            vals['no_analytic']['count'] += BT.search_count(tbase + self._no_analytic_domain())
            vals['no_branch']['count'] += BT.search_count(tbase + [('branch_id', '=', False)])
            if 'partner_id' in BT._fields:
                vals['no_partner']['count'] += BT.search_count(tbase + [('partner_id', '=', False)])
            vals['pending_validation']['count'] += BT.search_count(tbase + [('state', '=', 'draft')])
            vals['no_move']['count'] += BT.search_count(
                tbase + [('state', '=', 'validated'), ('move_id', '=', False)]
            )

        # ---- flow source selection ----
        if parsed.get('flow_source') == 'ledger':
            ledger = self._ledger_flow(parsed)
            vals['period_inflow']['amount'] = ledger['inflow']
            vals['period_outflow']['amount'] = ledger['outflow']
            vals['period_inflow']['count'] = treasury_inflow_cnt
            vals['period_outflow']['count'] = treasury_outflow_cnt
        else:
            vals['period_inflow']['amount'] = treasury_inflow
            vals['period_inflow']['count'] = treasury_inflow_cnt
            vals['period_outflow']['amount'] = treasury_outflow
            vals['period_outflow']['count'] = treasury_outflow_cnt

        vals['net_flow']['amount'] = (
            vals['period_inflow']['amount'] - vals['period_outflow']['amount']
        )
        vals['available_balance']['amount'] = self._liquidity_balance(parsed)
        rec, unrec = self._reconciliation_amounts(parsed)
        vals['reconciled_amount']['amount'] = rec
        vals['unreconciled_amount']['amount'] = unrec

        return vals

    @api.model
    def _pos_net_data(self, parsed):
        """Net cash from POS settlements that actually reaches liquidity accounts.

        Returns ``{'total', 'count', 'by_day': {iso_date: amount}}`` in company
        currency. POS docs are few per period, so iterating them is cheap and
        avoids fragile per-line/day grouping.
        """
        result = {'total': 0.0, 'count': 0, 'by_day': {}}
        if not self._can_read_model('debit.credit'):
            return result
        liquidity = self._liquidity_accounts(parsed)
        if not liquidity:
            return result
        liq_ids = set(liquidity.ids)
        docs = self.env['debit.credit'].search(
            self._base_dc_domain(parsed)
            + [('move_type', '=', 'credit_card'), ('state', '=', 'validated')]
        )
        for doc in docs:
            net = sum(
                line.amount
                for line in doc.debit_line_ids
                if line.type == 'debit' and line.account_id.id in liq_ids
            )
            net *= (doc.currency_rate or 1.0)
            if not net:
                continue
            result['total'] += net
            result['count'] += 1
            ds = fields.Date.to_string(doc.date)
            result['by_day'][ds] = result['by_day'].get(ds, 0.0) + net
        return result

    @api.model
    def _ledger_flow(self, parsed):
        """Period inflow/outflow from the bank/cash ledger (account.move.line).

        Inflow = posted debits, outflow = posted credits on liquidity accounts.
        This reconciles with the available balance and captures every movement
        (customer payments, bank statements, manual entries), not only
        gn_banks documents. Note: internal transfers between own bank accounts
        inflate both sides while netting to zero.
        """
        accounts = self._liquidity_accounts(parsed)
        if not accounts:
            return {'inflow': 0.0, 'outflow': 0.0}
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('account_id', 'in', accounts.ids),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
        ]
        agg = self.env['account.move.line']._read_group(
            domain=domain, groupby=[], aggregates=['debit:sum', 'credit:sum'],
        )
        if not agg:
            return {'inflow': 0.0, 'outflow': 0.0}
        debit, credit = agg[0]
        return {'inflow': float(debit or 0.0), 'outflow': float(credit or 0.0)}

    @api.model
    def _ledger_flow_by_day(self, parsed):
        """``{iso_date: (inflow, outflow)}`` from the liquidity ledger (1 query)."""
        accounts = self._liquidity_accounts(parsed)
        result = {}
        if not accounts:
            return result
        domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('account_id', 'in', accounts.ids),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
        ]
        rows = self.env['account.move.line']._read_group(
            domain=domain, groupby=['date:day'], aggregates=['debit:sum', 'credit:sum'],
        )
        for day, debit, credit in rows:
            ds = self._day_str(day)
            if not ds:
                continue
            result[ds] = (float(debit or 0.0), float(credit or 0.0))
        return result

    @api.model
    def _liquidity_balance(self, parsed):
        accounts = self._liquidity_accounts(parsed)
        if not accounts:
            return 0.0
        aml_domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('account_id', 'in', accounts.ids),
            ('date', '<=', parsed['date_to']),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
        ]
        agg = self.env['account.move.line']._read_group(
            domain=aml_domain,
            groupby=[],
            aggregates=['balance:sum'],
        )
        return float(agg[0][0] or 0.0) if agg else 0.0

    @api.model
    def _reconciliation_amounts(self, parsed):
        """Reconciled vs unreconciled *gross* movement on liquidity accounts.

        Uses ``debit + credit`` (gross movement) instead of the net balance:
        the net balance of reconciled lines tends to zero, which made the old
        metric misleading.
        """
        accounts = self._liquidity_accounts(parsed)
        if not accounts:
            return 0.0, 0.0
        base = [
            ('company_id', 'child_of', parsed['company'].id),
            ('account_id', 'in', accounts.ids),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
            ('parent_state', '=', 'posted'),
            ('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
        ]
        AML = self.env['account.move.line']

        def gross(extra):
            agg = AML._read_group(
                domain=base + extra, groupby=[], aggregates=['debit:sum', 'credit:sum'],
            )
            if not agg:
                return 0.0
            debit, credit = agg[0]
            return abs(float(debit or 0.0)) + abs(float(credit or 0.0))

        return gross([('reconciled', '=', True)]), gross([('reconciled', '=', False)])

    @api.model
    def _kpi_meta(self):
        return {
            'available_balance': {
                'label': _('Available balance'),
                'icon': 'fa-university',
                'tone': 'primary',
                'format': 'money',
                'metric': 'available_balance',
            },
            'period_inflow': {
                'label': _('Period inflows'),
                'icon': 'fa-arrow-down',
                'tone': 'success',
                'format': 'money',
                'metric': 'period_inflow',
            },
            'period_outflow': {
                'label': _('Period outflows'),
                'icon': 'fa-arrow-up',
                'tone': 'danger',
                'format': 'money',
                'metric': 'period_outflow',
            },
            'net_flow': {
                'label': _('Net flow'),
                'icon': 'fa-exchange',
                'tone': 'info',
                'format': 'money',
                'metric': 'net_flow',
            },
            'debits': {
                'label': _('Debits'),
                'icon': 'fa-minus-circle',
                'tone': 'danger',
                'format': 'both',
                'metric': 'debits',
            },
            'credits': {
                'label': _('Credits'),
                'icon': 'fa-plus-circle',
                'tone': 'success',
                'format': 'both',
                'metric': 'credits',
            },
            'deposits': {
                'label': _('Deposits'),
                'icon': 'fa-download',
                'tone': 'success',
                'format': 'both',
                'metric': 'deposits',
            },
            'pos_liquidations': {
                'label': _('POS liquidations'),
                'icon': 'fa-credit-card',
                'tone': 'primary',
                'format': 'both',
                'metric': 'pos_liquidations',
            },
            'checks_issued': {
                'label': _('Checks issued'),
                'icon': 'fa-money',
                'tone': 'warning',
                'format': 'both',
                'metric': 'checks_issued',
            },
            'checks_pending': {
                'label': _('Pending checks'),
                'icon': 'fa-clock-o',
                'tone': 'warning',
                'format': 'both',
                'metric': 'checks_pending',
            },
            'bank_transfers': {
                'label': _('Inter-bank transfers'),
                'icon': 'fa-random',
                'tone': 'info',
                'format': 'both',
                'metric': 'bank_transfers',
            },
            'cancelled': {
                'label': _('Cancelled operations'),
                'icon': 'fa-ban',
                'tone': 'danger',
                'format': 'count',
                'metric': 'cancelled',
            },
            'no_analytic': {
                'label': _('Without analytics'),
                'icon': 'fa-pie-chart',
                'tone': 'warning',
                'format': 'count',
                'metric': 'no_analytic',
            },
            'no_branch': {
                'label': _('Without branch'),
                'icon': 'fa-map-marker',
                'tone': 'warning',
                'format': 'count',
                'metric': 'no_branch',
            },
            'no_partner': {
                'label': _('Without contact'),
                'icon': 'fa-user-o',
                'tone': 'warning',
                'format': 'count',
                'metric': 'no_partner',
            },
            'pending_validation': {
                'label': _('Pending validation'),
                'icon': 'fa-hourglass-half',
                'tone': 'warning',
                'format': 'count',
                'metric': 'pending_validation',
            },
            'reconciled_amount': {
                'label': _('Reconciled amount'),
                'icon': 'fa-check-circle',
                'tone': 'success',
                'format': 'money',
                'metric': 'reconciled_amount',
            },
            'unreconciled_amount': {
                'label': _('Unreconciled amount'),
                'icon': 'fa-exclamation-circle',
                'tone': 'danger',
                'format': 'money',
                'metric': 'unreconciled_amount',
            },
        }

    @api.model
    def _kpi_item(self, key, current, previous, parsed):
        meta = self._kpi_meta().get(key, {})
        cur = current.get(key, {'amount': 0.0, 'count': 0})
        prev = previous.get(key, {'amount': 0.0, 'count': 0})
        cur_amt = cur.get('amount', 0.0)
        prev_amt = prev.get('amount', 0.0)
        variation = 0.0
        if prev_amt:
            variation = ((cur_amt - prev_amt) / abs(prev_amt)) * 100.0
        elif cur_amt:
            variation = 100.0
        return {
            'key': key,
            'label': meta.get('label', key),
            'icon': meta.get('icon', 'fa-bar-chart'),
            'tone': meta.get('tone', 'neutral'),
            'format': meta.get('format', 'money'),
            'metric': meta.get('metric', key),
            'amount': cur_amt,
            'count': cur.get('count', 0),
            'variation_pct': round(variation, 2),
            'trend': 'up' if variation > 0.5 else ('down' if variation < -0.5 else 'flat'),
        }

    # -------------------------------------------------------------------------
    # Cashflow & charts
    # -------------------------------------------------------------------------

    @api.model
    def _build_cashflow_series(self, parsed):
        """Daily inflow/outflow/cumulative series.

        Aggregations are done with one grouped query per source (instead of a
        per-day loop) and honour the selected ``flow_source``. The treasury
        series matches the inflow/outflow KPIs (POS net, checks issued, no
        internal transfers).
        """
        company = parsed['company']
        labels = []
        d = parsed['date_from']
        while d <= parsed['date_to']:
            labels.append(fields.Date.to_string(d))
            d += timedelta(days=1)
        in_map = dict.fromkeys(labels, 0.0)
        out_map = dict.fromkeys(labels, 0.0)

        if parsed.get('flow_source') == 'ledger':
            for ds, (debit, credit) in self._ledger_flow_by_day(parsed).items():
                if ds in in_map:
                    in_map[ds] += debit
                    out_map[ds] += credit
        else:
            if self._can_read_model('debit.credit'):
                # Inflow: credit + deposit (gross total reaches the bank).
                for ds, amt in self._grouped_total_by_day(
                    'debit.credit',
                    self._base_dc_domain(parsed) + [
                        ('move_type', 'in', ['credit', 'deposit']),
                        ('state', '=', 'validated'),
                    ],
                    company,
                ).items():
                    if ds in in_map:
                        in_map[ds] += amt
                # Inflow: POS net deposit per day.
                for ds, amt in self._pos_net_data(parsed)['by_day'].items():
                    if ds in in_map:
                        in_map[ds] += amt
                # Outflow: debits.
                for ds, amt in self._grouped_total_by_day(
                    'debit.credit',
                    self._base_dc_domain(parsed) + [
                        ('move_type', '=', 'debit'), ('state', '=', 'validated'),
                    ],
                    company,
                ).items():
                    if ds in out_map:
                        out_map[ds] += amt
            if self._can_read_model('bank.check'):
                # Outflow: issued checks only (exclude internal transferences).
                for ds, amt in self._grouped_total_by_day(
                    'bank.check',
                    self._base_check_domain(parsed) + [
                        ('move_type', '=', 'check'), ('state', '=', 'validated'),
                    ],
                    company,
                ).items():
                    if ds in out_map:
                        out_map[ds] += amt

        inflows = [in_map[lbl] for lbl in labels]
        outflows = [out_map[lbl] for lbl in labels]
        cumulative = []
        running = 0.0
        for i in range(len(labels)):
            running += inflows[i] - outflows[i]
            cumulative.append(running)
        return {
            'labels': labels,
            'inflows': inflows,
            'outflows': outflows,
            'cumulative': cumulative,
        }

    @api.model
    def _get_all_charts(self, parsed):
        return {
            'by_operation_type': self._distribution(parsed, 'operation_type'),
            'by_bank': self._distribution(parsed, 'bank'),
            'by_branch': self._distribution(parsed, 'branch'),
            'by_account': self._distribution(parsed, 'account'),
            'pos_by_bank': self._distribution(
                parsed, 'bank', extra_dc=[('move_type', '=', 'credit_card')],
            ),
            'checks_by_state': self._checks_by_state(parsed),
            'by_user': self._distribution(parsed, 'user'),
            'by_currency': self._distribution(parsed, 'currency'),
            'top_partners': self._top_dimension(parsed, 'partner', 10),
            'top_accounts': self._top_dimension(parsed, 'account', 10),
        }

    @api.model
    def _dist_accumulate(self, parsed, field, dimension, validated_only=True):
        """Sum ``total`` per ``field`` across treasury models (validated)."""
        acc = {}
        for model, base_fn in self._treasury_summary_specs():
            Model = self.env[model]
            if field not in Model._fields:
                continue
            domain = base_fn(parsed)
            if validated_only:
                domain = domain + [('state', '=', 'validated')]
            rows = Model._read_group(
                domain=domain, groupby=[field], aggregates=['total:sum', '__count'],
            )
            mt_sel = dict(Model._fields['move_type'].selection)
            for grp, total, cnt in rows:
                if field == 'move_type':
                    rec_id, label = grp, mt_sel.get(grp, grp)
                else:
                    rec_id = grp.id if grp else False
                    if not grp and field == 'journal_id':
                        continue
                    label = grp.display_name if grp else self._empty_dim_label(dimension)
                entry = acc.setdefault(rec_id, {'label': label, 'amount': 0.0, 'count': 0})
                entry['amount'] += float(total or 0)
                entry['count'] += int(cnt or 0)
        ordered = sorted(acc.values(), key=lambda e: abs(e['amount']), reverse=True)
        return {
            'labels': [e['label'] for e in ordered],
            'amounts': [e['amount'] for e in ordered],
            'counts': [e['count'] for e in ordered],
        }

    @api.model
    def _distribution(self, parsed, dimension, extra_dc=None):
        labels, amounts, counts = [], [], []
        extra_dc = extra_dc or []

        # Cuando no hay filtro extra de tipo, agregamos las tres fuentes de
        # tesorería (debit.credit + bank.check + bank.transfer) para que los
        # desgloses no queden vacíos si los movimientos son cheques/transfers.
        if dimension == 'operation_type' and not extra_dc:
            return self._dist_accumulate(parsed, 'move_type', dimension)
        if dimension == 'bank' and not extra_dc:
            return self._dist_accumulate(parsed, 'journal_id', dimension)
        if dimension == 'branch' and not extra_dc:
            return self._dist_accumulate(parsed, 'branch_id', dimension)
        if dimension == 'user' and not extra_dc:
            return self._dist_accumulate(parsed, 'create_uid', dimension, validated_only=False)

        if dimension == 'operation_type' and self._can_read_model('debit.credit'):
            rows = self._read_group_dc(
                parsed,
                self._base_dc_domain(parsed, extra_dc) + [('state', '=', 'validated')],
                groupby=['move_type'],
            )
            for mt, total, cnt in rows:
                labels.append(dict(self.env['debit.credit']._fields['move_type'].selection).get(mt, mt))
                amounts.append(float(total or 0))
                counts.append(int(cnt or 0))

        elif dimension == 'bank':
            if self._can_read_model('debit.credit'):
                rows = self._read_group_dc(
                    parsed,
                    self._base_dc_domain(parsed, extra_dc) + [('state', '=', 'validated')],
                    groupby=['journal_id'],
                )
                for journal, total, cnt in rows:
                    if not journal:
                        continue
                    labels.append(journal.name)
                    amounts.append(float(total or 0))
                    counts.append(int(cnt or 0))

        elif dimension == 'branch' and self._can_read_model('debit.credit'):
            rows = self._read_group_dc(
                parsed,
                self._base_dc_domain(parsed, extra_dc) + [('state', '=', 'validated')],
                groupby=['branch_id'],
            )
            for branch, total, cnt in rows:
                labels.append(branch.name if branch else _('No branch'))
                amounts.append(float(total or 0))
                counts.append(int(cnt or 0))

        elif dimension == 'account':
            Line = self.env['debit.credit.line']
            if self._can_read_model('debit.credit.line'):
                dc_ids = self.env['debit.credit'].search(
                    self._base_dc_domain(parsed, extra_dc)
                ).ids
                if dc_ids:
                    rows = Line._read_group(
                        domain=[('debit_id', 'in', dc_ids)],
                        groupby=['account_id'],
                        aggregates=['amount:sum', '__count'],
                    )
                    for acc, total, cnt in rows[:15]:
                        labels.append(acc.display_name if acc else '-')
                        amounts.append(float(total or 0))
                        counts.append(int(cnt or 0))

        elif dimension == 'user':
            if self._can_read_model('debit.credit'):
                rows = self._read_group_dc(
                    parsed,
                    self._base_dc_domain(parsed, extra_dc),
                    groupby=['create_uid'],
                )
                for user, total, cnt in rows:
                    labels.append(user.name if user else '-')
                    amounts.append(float(total or 0))
                    counts.append(int(cnt or 0))

        elif dimension == 'currency' and self._can_read_model('debit.credit'):
            rows = self._read_group_dc(
                parsed,
                self._base_dc_domain(parsed, extra_dc),
                groupby=['currency_id'],
            )
            for cur, total, cnt in rows:
                labels.append(cur.name if cur else '-')
                amounts.append(float(total or 0))
                counts.append(int(cnt or 0))

        return {'labels': labels, 'amounts': amounts, 'counts': counts}

    @api.model
    def _checks_by_state(self, parsed):
        if not self._can_read_model('bank.check'):
            return {'labels': [], 'amounts': [], 'counts': []}
        rows = self._read_group_check(
            parsed,
            self._base_check_domain(parsed, [('move_type', '=', 'check')]),
            groupby=['state'],
        )
        labels, amounts, counts = [], [], []
        sel = dict(self.env['bank.check']._fields['state'].selection)
        for state, total, cnt in rows:
            labels.append(sel.get(state, state))
            amounts.append(float(total or 0))
            counts.append(int(cnt or 0))
        return {'labels': labels, 'amounts': amounts, 'counts': counts}

    @api.model
    def _validated_dc_ids(self, parsed, extra=None):
        if not self._can_read_model('debit.credit'):
            return []
        return self.env['debit.credit'].search(
            self._base_dc_domain(parsed, extra or []) + [('state', '=', 'validated')]
        ).ids

    @api.model
    def _top_partners_data(self, parsed, limit=10):
        """Top contactos por monto en líneas (partner en debit.credit.line)."""
        if not self._can_read_model('debit.credit.line'):
            return {'labels': [], 'amounts': [], 'ids': []}
        dc_ids = self._validated_dc_ids(parsed)
        if not dc_ids:
            return {'labels': [], 'amounts': [], 'ids': []}
        rows = self.env['debit.credit.line']._read_group(
            domain=[('debit_id', 'in', dc_ids), ('partner_id', '!=', False)],
            groupby=['partner_id'],
            aggregates=['amount:sum'],
        )
        sorted_rows = sorted(rows, key=lambda r: float(r[1] or 0), reverse=True)[:limit]
        return {
            'labels': [p.name if p else '-' for p, _ in sorted_rows],
            'amounts': [float(amt or 0) for _, amt in sorted_rows],
            'ids': [p.id if p else False for p, _ in sorted_rows],
        }

    @api.model
    def _top_dimension(self, parsed, dimension, limit=10):
        if dimension == 'partner':
            return self._top_partners_data(parsed, limit=limit)
        if dimension == 'account' and self._can_read_model('debit.credit.line'):
            dc_ids = self.env['debit.credit'].search(self._base_dc_domain(parsed)).ids
            if not dc_ids:
                return {'labels': [], 'amounts': [], 'ids': []}
            rows = self.env['debit.credit.line']._read_group(
                domain=[('debit_id', 'in', dc_ids)],
                groupby=['account_id'],
                aggregates=['amount:sum'],
            )
            sorted_rows = sorted(rows, key=lambda r: float(r[1] or 0), reverse=True)[:limit]
            return {
                'labels': [acc.display_name if acc else '-' for acc, _ in sorted_rows],
                'amounts': [float(amt or 0) for _, amt in sorted_rows],
                'ids': [acc.id if acc else False for acc, _ in sorted_rows],
            }
        return {'labels': [], 'amounts': [], 'ids': []}

    # -------------------------------------------------------------------------
    # Alerts, insights, risk, summary tables
    # -------------------------------------------------------------------------

    @api.model
    def _build_alerts(self, parsed):
        today = fields.Date.context_today(self)
        week_end = today + timedelta(days=7)
        alerts = []

        def add(level, title, count, metric, description=''):
            if count:
                alerts.append({
                    'level': level,
                    'title': title,
                    'count': count,
                    'metric': metric,
                    'description': description,
                })

        if self._can_read_model('debit.credit'):
            base = self._base_dc_domain(parsed)
            add('warning', _('Documents pending validation'),
                self.env['debit.credit'].search_count(base + [('state', '=', 'draft')]),
                'pending_validation')
            add('danger', _('Operations without analytic'),
                self.env['debit.credit'].search_count(base + self._no_analytic_domain()),
                'no_analytic')
            add('warning', _('Operations without branch'),
                self.env['debit.credit'].search_count(base + [('branch_id', '=', False)]),
                'no_branch')
            add('warning', _('Operations without contact'),
                self.env['debit.credit'].search_count(base + [('partner_id', '=', False)]),
                'no_partner')
            add('info', _('Cancelled in period'),
                self.env['debit.credit'].search_count(base + [('state', '=', 'cancel')]),
                'cancelled')
            add('danger', _('Unbalanced drafts'),
                self.env['debit.credit'].search_count(
                    base + [('state', '=', 'draft'), ('amount_residual', '!=', 0)]
                ),
                'unbalanced')
            add('warning', _('POS without bank invoice'),
                self.env['debit.credit'].search_count(base + [
                    ('move_type', '=', 'credit_card'),
                    ('state', '=', 'validated'),
                    ('bank_invoice_id', '=', False),
                ]),
                'pos_no_invoice')
            add('danger', _('Validated without journal entry'),
                self.env['debit.credit'].search_count(
                    base + [('state', '=', 'validated'), ('move_id', '=', False)]
                ),
                'no_move')

        if self._can_read_model('bank.check'):
            cbase = self._base_check_domain(parsed)
            postdated_soon = self.env['bank.check'].search_count(cbase + [
                ('state', '=', 'postdated'),
                ('date', '>=', today),
                ('date', '<=', week_end),
            ])
            add('warning', _('Post-dated checks due this week'), postdated_soon, 'checks_due_soon')
            overdue = self.env['bank.check'].search_count(cbase + [
                ('state', '=', 'postdated'),
                ('date', '<', today),
            ])
            add('danger', _('Overdue post-dated checks'), overdue, 'checks_overdue')

        # Import batches with errors in period
        for model, label, metric in [
            ('liquidation.json.import.batch', _('JSON import errors'), 'json_import_errors'),
            ('bac.unified.import.batch', _('BAC import errors'), 'bac_import_errors'),
        ]:
            if model in self.env and self._can_read_model(model):
                cnt = self.env[model].search_count([
                    ('company_id', '=', parsed['company'].id),
                    ('create_date', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
                    ('create_date', '<=', fields.Datetime.to_datetime(parsed['date_to']) + timedelta(days=1)),
                    ('error_count', '>', 0),
                ])
                add('danger', label, cnt, metric)

        return alerts

    @api.model
    def _build_insights(self, parsed, cur=None, prev=None):
        insights = []
        if cur is None:
            cur = self._compute_kpi_values(parsed)
        if prev is None:
            prev = self._compute_kpi_values(self._previous_parsed(parsed))

        out_cur = cur['period_outflow']['amount']
        out_prev = prev['period_outflow']['amount'] or 0.0
        if out_prev:
            pct = ((out_cur - out_prev) / abs(out_prev)) * 100
            if pct > 0:
                insights.append(_(
                    'Outflows increased %(pct).2f%% compared to the previous period.',
                    pct=abs(pct),
                ))
            elif pct < 0:
                insights.append(_(
                    'Outflows decreased %(pct).2f%% compared to the previous period.',
                    pct=abs(pct),
                ))

        if cur['checks_pending']['count']:
            insights.append(_(
                '%(n)s pending checks in the selected period.',
                n=cur['checks_pending']['count'],
            ))

        if cur['no_analytic']['count']:
            insights.append(_(
                '%(n)s operations lack analytic distribution.',
                n=cur['no_analytic']['count'],
            ))

        pos_chart = self._distribution(
            parsed, 'bank', extra_dc=[('move_type', '=', 'credit_card')],
        )
        if pos_chart['amounts']:
            total_pos = sum(pos_chart['amounts'])
            if total_pos > 0:
                idx = pos_chart['amounts'].index(max(pos_chart['amounts']))
                pct_bank = (pos_chart['amounts'][idx] / total_pos) * 100
                insights.append(_(
                    '%(bank)s concentrates %(pct).2f%% of POS liquidations.',
                    bank=pos_chart['labels'][idx],
                    pct=pct_bank,
                ))

        branch_chart = self._distribution(parsed, 'branch')
        if branch_chart['amounts'] and len(branch_chart['amounts']) > 1:
            nets = []
            for i, lbl in enumerate(branch_chart['labels']):
                nets.append((lbl, branch_chart['amounts'][i]))
            worst = min(nets, key=lambda x: x[1])
            if worst[1] < 0:
                insights.append(_(
                    'Branch with largest negative flow: %(branch)s.',
                    branch=worst[0],
                ))

        return insights

    @api.model
    def _build_risk(self, parsed):
        risk = []
        if self._can_read_model('debit.credit'):
            base = self._base_dc_domain(parsed)
            risk.append({
                'label': _('Cancelled operations'),
                'count': self.env['debit.credit'].search_count(base + [('state', '=', 'cancel')]),
                'metric': 'cancelled',
            })
            risk.append({
                'label': _('Without journal entry'),
                'count': self.env['debit.credit'].search_count(
                    base + [('state', '=', 'validated'), ('move_id', '=', False)]
                ),
                'metric': 'no_move',
            })
            risk.append({
                'label': _('High amount (manual)'),
                'count': self.env['debit.credit'].search_count(
                    base + [('total', '>=', HIGH_AMOUNT_THRESHOLD)]
                ),
                'metric': 'high_amount',
            })
            # Users with most cancellations
            rows = self._read_group_dc(
                parsed,
                base + [('state', '=', 'cancel')],
                groupby=['create_uid'],
            )
            if rows:
                top = max(rows, key=lambda r: int(r[2] or 0))
                if top[0]:
                    risk.append({
                        'label': _('Top cancelling user'),
                        'count': int(top[2] or 0),
                        'metric': 'cancelled',
                        'extra': {'user_id': top[0].id},
                        'detail': top[0].name,
                    })

        return risk

    # -------------------------------------------------------------------------
    # Indicator gauges (Tigo-style semicircular gauges)
    # -------------------------------------------------------------------------

    @api.model
    def _round2(self, v):
        return round(float(v or 0.0), 2)

    @api.model
    def _gauge(self, key, title, value, unit, available, status, thresholds,
               healthy_range, message='', formula='', extra=None):
        status_labels = {
            'healthy': _('Saludable'),
            'warning': _('Atención'),
            'risk': _('Riesgo'),
            'unavailable': _('No disponible'),
        }
        out = {
            'id': key,
            'title': title,
            'value': value,
            'unit': unit,
            'available': bool(available),
            'status': status,
            'status_label': status_labels.get(status, status),
            'thresholds': thresholds or {},
            'healthy_range': healthy_range,
            'message': message,
            'formula': formula,
        }
        if extra:
            out['extra'] = extra
        return out

    @api.model
    def _status_lower_is_better(self, value, healthy_max, warning_max):
        """Return status label assuming lower is better.

        - value <= healthy_max -> healthy
        - value <= warning_max -> warning
        - value >  warning_max -> risk
        """
        if value is None:
            return 'unavailable'
        if value <= healthy_max:
            return 'healthy'
        if value <= warning_max:
            return 'warning'
        return 'risk'

    @api.model
    def _build_indicator_gauges(self, parsed, kpis=None):
        """Operational quality + risk gauges for the treasury dashboard.

        Reaprovecha ``_compute_kpi_values`` para no duplicar consultas.
        """
        if not self._can_read_model('debit.credit'):
            return {'groups': [], 'gauges': []}

        if kpis is None:
            kpis = self._compute_kpi_values(parsed)
        DC = self.env['debit.credit']
        base = self._base_dc_domain(parsed)

        # ``kpis['no_*']['count']`` consolida debit.credit + bank.check +
        # bank.transfer; el denominador debe usar el mismo universo para que
        # los porcentajes nunca superen 100%.
        total_ops_count = DC.search_count(base)
        validated_count = DC.search_count(base + [('state', '=', 'validated')])
        if self._can_read_model('bank.check'):
            cbase = self._base_check_domain(parsed)
            total_ops_count += self.env['bank.check'].search_count(cbase)
            validated_count += self.env['bank.check'].search_count(
                cbase + [('state', '=', 'validated')]
            )
        if self._can_read_model('bank.transfer'):
            tbase = self._base_transfer_domain(parsed)
            total_ops_count += self.env['bank.transfer'].search_count(tbase)
            validated_count += self.env['bank.transfer'].search_count(
                tbase + [('state', '=', 'validated')]
            )

        def pct(part, total):
            if not total:
                return None
            return self._round2(part / total * 100.0)

        analytic_thresholds = {'warning': 15.0, 'risk': 30.0}
        no_analytic_count = int(kpis.get('no_analytic', {}).get('count') or 0)
        analytic_value = pct(no_analytic_count, total_ops_count)
        analytic_gauge = self._gauge(
            'no_analytic', _('% Sin analítica'), analytic_value, 'percent',
            analytic_value is not None,
            self._status_lower_is_better(analytic_value, 15.0, 30.0),
            analytic_thresholds, _('< 15%'),
            message=_('%(n)s de %(t)s operaciones sin distribución analítica.')
            % {'n': no_analytic_count, 't': total_ops_count}
            if total_ops_count else _('No hay operaciones en el período.'),
            formula=_('Operaciones sin analítica / Total operaciones'),
            extra={'count': no_analytic_count, 'total': total_ops_count},
        )

        branch_thresholds = {'warning': 10.0, 'risk': 25.0}
        no_branch_count = int(kpis.get('no_branch', {}).get('count') or 0)
        branch_value = pct(no_branch_count, total_ops_count)
        branch_gauge = self._gauge(
            'no_branch', _('% Sin sucursal'), branch_value, 'percent',
            branch_value is not None,
            self._status_lower_is_better(branch_value, 10.0, 25.0),
            branch_thresholds, _('< 10%'),
            message=_('%(n)s de %(t)s operaciones sin sucursal asignada.')
            % {'n': no_branch_count, 't': total_ops_count}
            if total_ops_count else _('No hay operaciones en el período.'),
            formula=_('Operaciones sin sucursal / Total operaciones'),
            extra={'count': no_branch_count, 'total': total_ops_count},
        )

        partner_thresholds = {'warning': 15.0, 'risk': 30.0}
        no_partner_count = int(kpis.get('no_partner', {}).get('count') or 0)
        partner_value = pct(no_partner_count, total_ops_count)
        partner_gauge = self._gauge(
            'no_partner', _('% Sin contrapartida'), partner_value, 'percent',
            partner_value is not None,
            self._status_lower_is_better(partner_value, 15.0, 30.0),
            partner_thresholds, _('< 15%'),
            message=_('%(n)s de %(t)s operaciones sin contraparte.')
            % {'n': no_partner_count, 't': total_ops_count}
            if total_ops_count else _('No hay operaciones en el período.'),
            formula=_('Operaciones sin partner / Total operaciones'),
            extra={'count': no_partner_count, 'total': total_ops_count},
        )

        pending_thresholds = {'warning': 10.0, 'risk': 25.0}
        pending_count = int(kpis.get('pending_validation', {}).get('count') or 0)
        pending_value = pct(pending_count, total_ops_count)
        pending_gauge = self._gauge(
            'pending_validation', _('% Pendientes de validación'),
            pending_value, 'percent',
            pending_value is not None,
            self._status_lower_is_better(pending_value, 10.0, 25.0),
            pending_thresholds, _('< 10%'),
            message=_('%(n)s de %(t)s operaciones en borrador.')
            % {'n': pending_count, 't': total_ops_count}
            if total_ops_count else _('No hay operaciones en el período.'),
            formula=_('Operaciones en borrador / Total operaciones'),
            extra={'count': pending_count, 'total': total_ops_count},
        )

        cancel_thresholds = {'warning': 5.0, 'risk': 15.0}
        cancel_count = int(kpis.get('cancelled', {}).get('count') or 0)
        cancel_value = pct(cancel_count, total_ops_count)
        cancel_gauge = self._gauge(
            'cancelled', _('% Operaciones canceladas'), cancel_value, 'percent',
            cancel_value is not None,
            self._status_lower_is_better(cancel_value, 5.0, 15.0),
            cancel_thresholds, _('< 5%'),
            message=_('%(n)s cancelaciones detectadas en el período.')
            % {'n': cancel_count}
            if total_ops_count else _('No hay operaciones en el período.'),
            formula=_('Operaciones canceladas / Total operaciones'),
            extra={'count': cancel_count, 'total': total_ops_count},
        )

        recon_thresholds = {'warning': 10.0, 'risk': 25.0}
        rec_amount = float(kpis.get('reconciled_amount', {}).get('amount') or 0.0)
        unrec_amount = float(kpis.get('unreconciled_amount', {}).get('amount') or 0.0)
        denom = abs(rec_amount) + abs(unrec_amount)
        recon_value = pct(abs(unrec_amount), denom) if denom else None
        recon_gauge = self._gauge(
            'unreconciled', _('% Monto no conciliado'), recon_value, 'percent',
            recon_value is not None,
            self._status_lower_is_better(recon_value, 10.0, 25.0),
            recon_thresholds, _('< 10%'),
            message=_('Monto pendiente de conciliar respecto al total.')
            if recon_value is not None else _('Sin movimientos comparables.'),
            formula=_('Monto no conciliado / (Conciliado + No conciliado)'),
            extra={'reconciled': rec_amount, 'unreconciled': unrec_amount},
        )

        check_thresholds = {'warning': 25.0, 'risk': 50.0}
        checks_pending_count = int(kpis.get('checks_pending', {}).get('count') or 0)
        checks_issued_count = int(kpis.get('checks_issued', {}).get('count') or 0)
        check_total = checks_pending_count + checks_issued_count
        check_value = pct(checks_pending_count, check_total) if check_total else None
        check_gauge = self._gauge(
            'checks_pending', _('% Cheques pendientes'), check_value, 'percent',
            check_value is not None,
            self._status_lower_is_better(check_value, 25.0, 50.0),
            check_thresholds, _('< 25%'),
            message=_('%(n)s pendientes de %(t)s emitidos en el período.')
            % {'n': checks_pending_count, 't': check_total}
            if check_total else _('No hay cheques en el período.'),
            formula=_('Cheques pendientes / Cheques totales'),
            extra={'pending': checks_pending_count, 'total': check_total},
        )

        validated_thresholds = {'risk': 50.0, 'warning': 80.0}  # higher_is_better
        validated_pct = pct(validated_count, total_ops_count) if total_ops_count else None
        validated_status = 'unavailable'
        if validated_pct is not None:
            if validated_pct >= 80.0:
                validated_status = 'healthy'
            elif validated_pct >= 50.0:
                validated_status = 'warning'
            else:
                validated_status = 'risk'
        validated_gauge = self._gauge(
            'validated_pct', _('% Operaciones validadas'), validated_pct, 'percent',
            validated_pct is not None, validated_status,
            validated_thresholds, _('> 80%'),
            message=_('%(n)s validadas de %(t)s totales.')
            % {'n': validated_count, 't': total_ops_count}
            if total_ops_count else _('No hay operaciones en el período.'),
            formula=_('Operaciones validadas / Total operaciones'),
            extra={'validated': validated_count, 'total': total_ops_count},
        )

        groups = [
            {
                'id': 'data_quality',
                'title': _('Calidad de datos'),
                'gauges': [analytic_gauge, branch_gauge, partner_gauge,
                           pending_gauge, validated_gauge],
            },
            {
                'id': 'risk',
                'title': _('Riesgo operativo'),
                'gauges': [cancel_gauge, recon_gauge, check_gauge],
            },
        ]
        flat = [g for grp in groups for g in grp['gauges'] if g]
        return {'groups': groups, 'gauges': flat}

    @api.model
    def _treasury_summary_specs(self):
        """(model, base_domain_fn) for every readable treasury model.

        Las tablas de detalle y los desgloses deben reflejar TODA la tesorería
        (debit.credit + bank.check + bank.transfer); de lo contrario los cortes
        con cheques/transferencias aparecen vacíos aunque haya movimientos.
        """
        specs = []
        if self._can_read_model('debit.credit'):
            specs.append(('debit.credit', self._base_dc_domain))
        if self._can_read_model('bank.check'):
            specs.append(('bank.check', self._base_check_domain))
        if self._can_read_model('bank.transfer'):
            specs.append(('bank.transfer', self._base_transfer_domain))
        return specs

    @api.model
    def _empty_dim_label(self, dimension):
        return {
            'branch': _('No branch'),
            'analytic': _('No analytic'),
        }.get(dimension, '-')

    @api.model
    def _summary_accumulate(self, parsed, field, dimension):
        """Aggregate count/debit/credit per ``field`` across treasury models.

        Outflow move types go to the ``credit`` column, inflows to ``debit``;
        ``net = debit - credit``.
        """
        acc = {}
        for model, base_fn in self._treasury_summary_specs():
            Model = self.env[model]
            if field not in Model._fields:
                continue
            groupby = ['move_type'] if field == 'move_type' else [field, 'move_type']
            rows = Model._read_group(
                domain=base_fn(parsed),
                groupby=groupby,
                aggregates=['total:sum', '__count'],
            )
            mt_sel = dict(Model._fields['move_type'].selection)
            st_sel = dict(Model._fields['state'].selection) if 'state' in Model._fields else {}
            for row in rows:
                if field == 'move_type':
                    grp, total, cnt = row
                    mt = grp
                else:
                    grp, mt, total, cnt = row
                amt = float(total or 0)
                cnt = int(cnt or 0)
                is_out = mt in OUTFLOW_MOVE_TYPES
                if field == 'move_type':
                    rec_id, label = mt, mt_sel.get(mt, mt)
                elif field == 'state':
                    rec_id, label = grp, st_sel.get(grp, grp)
                else:
                    rec_id = grp.id if grp else False
                    label = grp.display_name if grp else self._empty_dim_label(dimension)
                key = (field, rec_id)
                entry = acc.setdefault(key, {
                    'id': rec_id, 'label': label, 'count': 0,
                    'debit': 0.0, 'credit': 0.0,
                })
                entry['count'] += cnt
                if is_out:
                    entry['credit'] += amt
                else:
                    entry['debit'] += amt
        return list(acc.values())

    @api.model
    def _summary_table(self, parsed, dimension):
        rows = []
        grand = 0.0

        def push(label, count, debit, credit, rec_id=False):
            nonlocal grand
            net = debit - credit
            grand += abs(net)
            rows.append({
                'id': rec_id,
                'label': label,
                'count': count,
                'debit': debit,
                'credit': credit,
                'net': net,
            })

        field_map = {
            'bank': 'journal_id',
            'branch': 'branch_id',
            'operation_type': 'move_type',
            'state': 'state',
            'user': 'create_uid',
            'analytic': 'analytic_account_id',
        }

        if dimension in field_map:
            for data in self._summary_accumulate(parsed, field_map[dimension], dimension):
                push(data['label'], data['count'], data['debit'], data['credit'], data['id'])

        elif dimension == 'partner':
            partner_map = defaultdict(lambda: {'label': '-', 'count': 0, 'debit': 0.0, 'credit': 0.0})
            if self._can_read_model('debit.credit.line'):
                dc_ids = self._validated_dc_ids(parsed)
                if dc_ids:
                    lines = self.env['debit.credit.line']._read_group(
                        domain=[('debit_id', 'in', dc_ids), ('partner_id', '!=', False)],
                        groupby=['partner_id', 'type'],
                        aggregates=['amount:sum', '__count'],
                    )
                    for partner, line_type, amount, cnt in lines:
                        key = partner.id if partner else 0
                        partner_map[key]['label'] = partner.name if partner else '-'
                        partner_map[key]['count'] += int(cnt or 0)
                        if line_type == 'debit':
                            partner_map[key]['debit'] += float(amount or 0)
                        else:
                            partner_map[key]['credit'] += float(amount or 0)
            if self._can_read_model('bank.check'):
                crows = self.env['bank.check']._read_group(
                    domain=self._base_check_domain(parsed) + [('partner_id', '!=', False)],
                    groupby=['partner_id'],
                    aggregates=['total:sum', '__count'],
                )
                for partner, total, cnt in crows:
                    key = partner.id if partner else 0
                    partner_map[key]['label'] = partner.name if partner else '-'
                    partner_map[key]['count'] += int(cnt or 0)
                    partner_map[key]['credit'] += float(total or 0)
            for key, data in partner_map.items():
                push(data['label'], data['count'], data['debit'], data['credit'], key)

        elif dimension == 'account' and self._can_read_model('debit.credit.line'):
            dc_ids = self.env['debit.credit'].search(self._base_dc_domain(parsed)).ids
            if dc_ids:
                lines = self.env['debit.credit.line']._read_group(
                    domain=[('debit_id', 'in', dc_ids)],
                    groupby=['account_id', 'type'],
                    aggregates=['amount:sum', '__count'],
                )
                acc_map = defaultdict(lambda: {'count': 0, 'debit': 0.0, 'credit': 0.0})
                for acc, line_type, amount, cnt in lines:
                    key = acc.id if acc else 0
                    acc_map[key]['label'] = acc.display_name if acc else '-'
                    acc_map[key]['count'] += int(cnt or 0)
                    if line_type == 'debit':
                        acc_map[key]['debit'] += float(amount or 0)
                    else:
                        acc_map[key]['credit'] += float(amount or 0)
                for key, data in acc_map.items():
                    push(data['label'], data['count'], data['debit'], data['credit'], key)

        for r in rows:
            r['pct'] = round((abs(r['net']) / grand * 100.0), 2) if grand else 0.0

        return {
            'dimension': dimension,
            'rows': sorted(rows, key=lambda x: abs(x['net']), reverse=True),
            'grand_total': grand,
        }

    # -------------------------------------------------------------------------
    # Drill-down actions
    # -------------------------------------------------------------------------

    @api.model
    def _action_for_metric(self, metric, parsed, extra=None):
        extra = extra or []
        metric = metric or ''

        if metric == 'available_balance':
            return self._aml_action(parsed, _('Bank liquidity'), [])

        # In ledger mode the flow KPIs are computed from account.move.line, so
        # the drill-down must open the ledger (not the gn_banks documents).
        if parsed.get('flow_source') == 'ledger' and metric in (
            'period_inflow', 'period_outflow', 'net_flow',
        ):
            flow_extra = {
                'period_inflow': [('debit', '>', 0)],
                'period_outflow': [('credit', '>', 0)],
                'net_flow': [],
            }[metric]
            names = {
                'period_inflow': _('Ledger inflows'),
                'period_outflow': _('Ledger outflows'),
                'net_flow': _('Net bank movements'),
            }
            return self._aml_action(parsed, names[metric], flow_extra + extra)

        if metric in ('reconciled_amount', 'unreconciled_amount'):
            rec = metric == 'reconciled_amount'
            return self._aml_action(
                parsed,
                _('Reconciled lines') if rec else _('Unreconciled lines'),
                [('reconciled', '=', rec)],
            )

        dc_metrics = {
            'debits': [('move_type', '=', 'debit')],
            'credits': [('move_type', '=', 'credit')],
            'deposits': [('move_type', '=', 'deposit')],
            'pos_liquidations': [('move_type', '=', 'credit_card')],
            'period_inflow': [('move_type', 'in', list(DC_INFLOW_TYPES))],
            'period_outflow': [('move_type', 'in', list(DC_OUTFLOW_TYPES))],
            'cancelled': [('state', '=', 'cancel')],
            'no_analytic': self._no_analytic_domain(),
            'no_branch': [('branch_id', '=', False)],
            'no_partner': [('partner_id', '=', False)],
            'pending_validation': [('state', '=', 'draft')],
            'pos_no_invoice': [
                ('move_type', '=', 'credit_card'),
                ('state', '=', 'validated'),
                ('bank_invoice_id', '=', False),
            ],
            'no_move': [('state', '=', 'validated'), ('move_id', '=', False)],
            'unbalanced': [('state', '=', 'draft'), ('amount_residual', '!=', 0)],
            'high_amount': [('total', '>=', HIGH_AMOUNT_THRESHOLD)],
        }

        if metric in dc_metrics and self._can_read_model('debit.credit'):
            domain = self._base_dc_domain(parsed, dc_metrics[metric] + extra)
            return self._window_action(
                'debit.credit',
                domain,
                _('Treasury operations'),
                'gn_banks.action_debit',
            )

        if metric in ('checks_issued', 'checks_pending', 'checks_due_soon', 'checks_overdue'):
            if not self._can_read_model('bank.check'):
                raise AccessError(_('No access to checks.'))
            domain = self._base_check_domain(parsed)
            if metric == 'checks_issued':
                domain += [('move_type', '=', 'check'), ('state', '=', 'validated')]
            elif metric == 'checks_pending':
                domain += [('move_type', '=', 'check'), ('state', 'in', ('draft', 'postdated'))]
            elif metric == 'checks_due_soon':
                today = fields.Date.context_today(self)
                domain += [
                    ('state', '=', 'postdated'),
                    ('date', '>=', today),
                    ('date', '<=', today + timedelta(days=7)),
                ]
            elif metric == 'checks_overdue':
                today = fields.Date.context_today(self)
                domain += [('state', '=', 'postdated'), ('date', '<', today)]
            domain += extra
            xmlid = 'gn_banks.action_bank_check'
            return self._window_action('bank.check', domain, _('Checks'), xmlid)

        if metric == 'bank_transfers' and self._can_read_model('bank.transfer'):
            domain = self._base_transfer_domain(parsed, extra)
            return self._window_action(
                'bank.transfer',
                domain,
                _('Bank transfers'),
                'gn_banks.action_bank_account_transfer',
            )

        if metric == 'net_flow':
            return self._aml_action(parsed, _('Net bank movements'), extra)

        if extra and extra[0] == 'journal_id':
            jid = extra[0][2] if isinstance(extra[0], (list, tuple)) else extra.get('journal_id')
            domain = self._base_dc_domain(parsed, [('journal_id', '=', jid)])
            return self._window_action('debit.credit', domain, _('Operations'), 'gn_banks.action_debit')

        raise UserError(_('Unknown drill-down metric: %s') % metric)

    @api.model
    def _window_action(self, model, domain, name, xmlid=None):
        action = False
        if xmlid:
            try:
                # SUDO-JUSTIFIED: leer acción de ventana para drill-down sin restricción de menú
                action = self.env.ref(xmlid).sudo().read()[0]
            except ValueError:
                pass
        if not action:
            action = {
                'type': 'ir.actions.act_window',
                'res_model': model,
                'view_mode': 'list,form',
            }
        action['domain'] = domain
        action['name'] = name
        return action

    @api.model
    def _aml_action(self, parsed, name, extra_domain):
        accounts = self._liquidity_accounts(parsed)
        aml_domain = [
            ('company_id', 'child_of', parsed['company'].id),
            ('account_id', 'in', accounts.ids),
            ('date', '>=', parsed['date_from']),
            ('date', '<=', parsed['date_to']),
            ('parent_state', '=', 'posted'),
        ] + (extra_domain or [])
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': aml_domain,
            'context': {'search_default_posted': 1},
        }
