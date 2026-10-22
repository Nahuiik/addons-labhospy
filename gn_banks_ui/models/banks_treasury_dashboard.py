# -*- coding: utf-8 -*-
from datetime import date

from odoo import _, api, fields, models


class BanksTreasuryDashboard(models.AbstractModel):
    _name = 'banks.treasury.dashboard'
    _description = 'KPIs y datos de gráficos del dashboard de tesorería'

    @api.model
    def _month_bounds(self, company, ref_date=None):
        ref = ref_date or fields.Date.context_today(self)
        start = ref.replace(day=1)
        if ref.month == 12:
            end = ref.replace(day=31)
        else:
            end = (ref.replace(month=ref.month + 1, day=1)) - __import__('datetime').timedelta(days=1)
        return start, end

    @api.model
    def _base_company(self, company_id=None):
        return self.env['res.company'].browse(company_id) if company_id else self.env.company

    @api.model
    def get_filter_options(self):
        company = self._base_company()
        journals = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', company.id),
        ], order='name')
        return {
            'company_id': company.id,
            'company_name': company.name,
            'journals': [{'id': j.id, 'name': j.display_name} for j in journals],
        }

    @api.model
    def _sum_operations(self, model, domain):
        data = self.env[model]._read_group(domain=domain, aggregates=['total:sum'])
        return float(data[0][0] or 0.0) if data else 0.0

    @api.model
    def _count_operations(self, model, domain):
        return self.env[model].search_count(domain)

    @api.model
    def get_dashboard_data(self, company_id=None, journal_ids=None):
        company = self._base_company(company_id)
        month_start, month_end = self._month_bounds(company)
        today = fields.Date.context_today(self)

        journal_domain = [('company_id', '=', company.id)]
        if journal_ids:
            journal_domain.append(('journal_id', 'in', journal_ids))

        debit_domain = journal_domain + [
            ('move_type', '=', 'debit'),
            ('date', '>=', month_start),
            ('date', '<=', month_end),
            ('state', '=', 'validated'),
        ]
        credit_domain = journal_domain + [
            ('move_type', '=', 'credit'),
            ('date', '>=', month_start),
            ('date', '<=', month_end),
            ('state', '=', 'validated'),
        ]

        kpis = [
            {
                'key': 'month_debits',
                'label': _('Débitos del mes'),
                'value': self._sum_operations('debit.credit', debit_domain),
                'icon': 'fa-arrow-circle-up',
                'tone': 'danger',
            },
            {
                'key': 'month_credits',
                'label': _('Créditos del mes'),
                'value': self._sum_operations('debit.credit', credit_domain),
                'icon': 'fa-arrow-circle-down',
                'tone': 'success',
            },
            {
                'key': 'pending_transfers',
                'label': _('Transferencias pendientes'),
                'value': self._count_operations('bank.transfer', [
                    ('company_id', '=', company.id),
                    ('state', '=', 'draft'),
                ]),
                'icon': 'fa-exchange',
                'tone': 'info',
            },
            {
                'key': 'pending_checks',
                'label': _('Cheques pendientes'),
                'value': self._count_operations('bank.check', [
                    ('company_id', '=', company.id),
                    ('move_type', '=', 'check'),
                    ('state', '=', 'draft'),
                ]),
                'icon': 'fa-money',
                'tone': 'warning',
            },
            {
                'key': 'pending_pos',
                'label': _('Liquidaciones POS pendientes'),
                'value': self._count_operations('debit.credit', [
                    ('company_id', '=', company.id),
                    ('move_type', '=', 'credit_card'),
                    ('state', '=', 'draft'),
                ]),
                'icon': 'fa-credit-card',
                'tone': 'purple',
            },
            {
                'key': 'deposits_today',
                'label': _('Depósitos de hoy'),
                'value': self._sum_operations('debit.credit', journal_domain + [
                    ('move_type', '=', 'deposit'),
                    ('date', '=', today),
                    ('state', '=', 'validated'),
                ]),
                'icon': 'fa-university',
                'tone': 'success',
            },
            {
                'key': 'pending_reconciliation',
                'label': _('Conciliación pendiente'),
                'value': self._count_operations('debit.credit', [
                    ('company_id', '=', company.id),
                    ('state', '=', 'validated'),
                    ('reconciliation_status', 'in', ('none', 'partial')),
                ]) + self._count_operations('bank.check', [
                    ('company_id', '=', company.id),
                    ('state', '=', 'validated'),
                    ('reconciliation_status', 'in', ('none', 'partial')),
                ]) + self._count_operations('bank.transfer', [
                    ('company_id', '=', company.id),
                    ('state', '=', 'validated'),
                    ('reconciliation_status', 'in', ('none', 'partial')),
                ]),
                'icon': 'fa-link',
                'tone': 'warning',
            },
        ]

        net_flow = kpis[1]['value'] - kpis[0]['value']
        kpis.append({
            'key': 'net_flow',
            'label': _('Flujo neto del mes'),
            'value': net_flow,
            'icon': 'fa-line-chart',
            'tone': 'success' if net_flow >= 0 else 'danger',
        })

        bank_balances = self._get_bank_balances(company, journal_ids)
        charts = self._get_chart_data(company, journal_ids, month_start, month_end)

        return {
            'kpis': kpis,
            'bank_balances': bank_balances,
            'charts': charts,
            'currency': company.currency_id.name,
            'currency_symbol': company.currency_id.symbol,
        }

    @api.model
    def _get_bank_balances(self, company, journal_ids=None):
        common = self.env['banks.weekly.balance.common']
        journals = common.search_balance_journals(company.id, journal_ids)
        today = fields.Date.context_today(self)
        result = []
        for journal in journals:
            account = journal.default_account_id
            if not account:
                continue
            balance = common._sums_through_date(company, {account.id}, today).get(account.id, 0.0)
            result.append({
                'journal_id': journal.id,
                'name': journal.display_name,
                'balance': balance,
            })
        return result

    @api.model
    def _get_chart_data(self, company, journal_ids, month_start, month_end):
        """Weekly cashflow + inflow/outflow for current month."""
        labels = []
        inflows = []
        outflows = []
        week_start = month_start
        while week_start <= month_end:
            week_end = min(week_start + __import__('datetime').timedelta(days=6), month_end)
            labels.append(week_start.strftime('%d/%m'))
            in_domain = [
                ('company_id', '=', company.id),
                ('state', '=', 'validated'),
                ('date', '>=', week_start),
                ('date', '<=', week_end),
                ('move_type', 'in', ('credit', 'deposit')),
            ]
            out_domain = [
                ('company_id', '=', company.id),
                ('state', '=', 'validated'),
                ('date', '>=', week_start),
                ('date', '<=', week_end),
                ('move_type', 'in', ('debit',)),
            ]
            if journal_ids:
                in_domain.append(('journal_id', 'in', journal_ids))
                out_domain.append(('journal_id', 'in', journal_ids))
            inflows.append(self._sum_operations('debit.credit', in_domain))
            outflows.append(self._sum_operations('debit.credit', out_domain))
            week_start = week_end + __import__('datetime').timedelta(days=1)

        check_states = self.env['bank.check']._read_group(
            domain=[('company_id', '=', company.id), ('move_type', '=', 'check')],
            groupby=['state'],
            aggregates=['__count'],
        )
        state_labels = {
            'draft': _('Borrador'),
            'validated': _('Validado'),
            'cancel': _('Cancelado'),
        }
        checks_by_state = {
            state_labels.get(state, state or _('Desconocido')): count
            for state, count in check_states
        }

        pos_by_date = self.env['debit.credit']._read_group(
            domain=[
                ('company_id', '=', company.id),
                ('move_type', '=', 'credit_card'),
                ('state', '=', 'validated'),
                ('date', '>=', month_start),
                ('date', '<=', month_end),
            ],
            groupby=['date:day'],
            aggregates=['total:sum'],
            order='date:day',
        )

        return {
            'weekly_cashflow': {
                'labels': labels,
                'inflows': inflows,
                'outflows': outflows,
            },
            'checks_by_state': {
                'labels': list(checks_by_state.keys()),
                'values': list(checks_by_state.values()),
            },
            'pos_by_date': {
                'labels': [str(d) for d, _ in pos_by_date],
                'values': [float(v or 0) for _, v in pos_by_date],
            },
            'bank_balances': self._get_bank_balances(company, journal_ids),
        }

    @api.model
    def get_weekly_balance_action(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_banks_balance_weekly_dashboard',
            'name': _('Balance semanal'),
        }

    @api.model
    def get_reports_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reportes bancarios'),
            'res_model': 'banks.reports',
            'view_mode': 'form',
            'target': 'new',
        }
