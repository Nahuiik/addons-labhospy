# -*- coding: utf-8 -*-
"""Agregación SQL/read_group para datasets grandes — Facturas y pagos."""

import logging

from odoo import _, api, fields, models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


class InvoicePaymentReportAggregation(models.AbstractModel):
    _name = 'gn.accounting.invoice.payment.aggregation'
    _description = 'Agregación SQL Facturas y pagos'

    @api.model
    def _large_dataset_threshold(self, company):
        return company.inv_pay_large_dataset_threshold or 5000

    @api.model
    def _has_payment_lines(self):
        return 'payment.invoice.line' in self.env

    @api.model
    def _estimate_row_count(self, parsed):
        if not self._has_payment_lines():
            return 0
        count = self.env['payment.invoice.line'].search_count(
            self._line_orm_domain(parsed)
        )
        if parsed.get('show_pending_invoices'):
            count += self.env['account.move'].search_count(
                self._pending_orm_domain(parsed)
            )
        return count

    @api.model
    def should_use_sql_mode(self, parsed):
        return self._estimate_row_count(parsed) > self._large_dataset_threshold(parsed['company'])

    @api.model
    def _line_orm_domain(self, parsed):
        domain = [
            ('payment_id.payment_type', '=', 'inbound'),
            ('payment_id.partner_type', '=', 'customer'),
            ('payment_id.company_id', '=', parsed['company_id']),
            ('payment_id.state', 'not in', ('draft', 'canceled', 'rejected')),
            ('payment_id.date', '>=', parsed['date_from']),
            ('payment_id.date', '<=', parsed['date_to']),
            ('invoice_id.move_type', 'in', ('out_invoice', 'out_refund')),
            ('invoice_id.state', '=', 'posted'),
        ]
        if parsed.get('branch_ids') and 'branch_id' in self.env['account.payment']._fields:
            domain.append(('payment_id.branch_id', 'in', parsed['branch_ids']))
        if parsed.get('partner_ids'):
            domain.append(('invoice_id.partner_id', 'in', parsed['partner_ids']))
        if parsed.get('journal_ids'):
            domain.append(('payment_id.journal_id', 'in', parsed['journal_ids']))
        if parsed.get('user_ids'):
            domain.append(('invoice_id.invoice_user_id', 'in', parsed['user_ids']))
        if parsed.get('payment_state') != 'all':
            domain.append(('invoice_id.payment_state', '=', parsed['payment_state']))
        if parsed.get('invoice_date_from'):
            domain.append(('invoice_id.invoice_date', '>=', parsed['invoice_date_from']))
        if parsed.get('invoice_date_to'):
            domain.append(('invoice_id.invoice_date', '<=', parsed['invoice_date_to']))
        return domain

    @api.model
    def _pending_orm_domain(self, parsed):
        inv_from = parsed.get('invoice_date_from') or parsed['date_from']
        inv_to = parsed.get('invoice_date_to') or parsed['date_to']
        domain = [
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('company_id', '=', parsed['company_id']),
            ('payment_state', 'in', ('not_paid', 'partial', 'in_payment')),
            ('invoice_date', '>=', inv_from),
            ('invoice_date', '<=', inv_to),
        ]
        if parsed.get('branch_ids') and 'branch_id' in self.env['account.move']._fields:
            domain.append(('branch_id', 'in', parsed['branch_ids']))
        if parsed.get('partner_ids'):
            domain.append(('partner_id', 'in', parsed['partner_ids']))
        if parsed.get('user_ids'):
            domain.append(('invoice_user_id', 'in', parsed['user_ids']))
        if parsed.get('payment_state') != 'all':
            domain.append(('payment_state', '=', parsed['payment_state']))
        return domain

    @api.model
    def _sql_where(self, parsed):
        parts = [
            SQL("ap.payment_type = 'inbound'"),
            SQL("ap.partner_type = 'customer'"),
            SQL('ap.company_id = %s', parsed['company_id']),
            SQL("ap.state NOT IN ('draft', 'canceled', 'rejected')"),
            SQL('ap.date >= %s', parsed['date_from']),
            SQL('ap.date <= %s', parsed['date_to']),
            SQL("am.move_type IN ('out_invoice', 'out_refund')"),
            SQL("am.state = 'posted'"),
        ]
        if parsed.get('branch_ids') and 'branch_id' in self.env['account.payment']._fields:
            parts.append(SQL('ap.branch_id IN %s', tuple(parsed['branch_ids'])))
        if parsed.get('partner_ids'):
            parts.append(SQL('am.partner_id IN %s', tuple(parsed['partner_ids'])))
        if parsed.get('journal_ids'):
            parts.append(SQL('ap.journal_id IN %s', tuple(parsed['journal_ids'])))
        if parsed.get('user_ids'):
            parts.append(SQL('am.invoice_user_id IN %s', tuple(parsed['user_ids'])))
        if parsed.get('payment_state') != 'all':
            parts.append(SQL('am.payment_state = %s', parsed['payment_state']))
        if parsed.get('invoice_date_from'):
            parts.append(SQL('am.invoice_date >= %s', parsed['invoice_date_from']))
        if parsed.get('invoice_date_to'):
            parts.append(SQL('am.invoice_date <= %s', parsed['invoice_date_to']))
        result = parts[0]
        for p in parts[1:]:
            result = SQL('%s AND %s', result, p)
        return result

    @api.model
    def _search_sql(self, search):
        if not search:
            return SQL('TRUE')
        like = f'%{search}%'
        return SQL(
            "(rp.name ILIKE %s OR am.name ILIKE %s OR ap.name ILIKE %s "
            "OR COALESCE(ru.name, '') ILIKE %s OR COALESCE(aj.name, '') ILIKE %s)",
            like, like, like, like, like,
        )

    @api.model
    def compute_summary_sql(self, parsed, compare_rows=None):
        service = self.env['gn.accounting.invoice.payment.service']
        if not self._has_payment_lines():
            return service._build_kpis_from_totals(parsed, compare_rows=compare_rows)

        where = self._sql_where(parsed)
        self.env.cr.execute(SQL("""
            SELECT
                COUNT(DISTINCT am.id) AS invoice_count,
                COUNT(pil.id) AS payment_line_count,
                COALESCE(SUM(COALESCE(pil.amount, pil.actual_amount, 0)), 0) AS total_paid,
                COUNT(DISTINCT am.partner_id) AS unique_clients
            FROM payment_invoice_line pil
            JOIN account_payment ap ON ap.id = pil.payment_id
            JOIN account_move am ON am.id = pil.invoice_id
            WHERE %s
        """, where))
        agg = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(SQL("""
            SELECT COALESCE(SUM(sub.amount_total), 0) AS total_invoiced
            FROM (
                SELECT DISTINCT am.id, ABS(am.amount_total) AS amount_total
                FROM payment_invoice_line pil
                JOIN account_payment ap ON ap.id = pil.payment_id
                JOIN account_move am ON am.id = pil.invoice_id
                WHERE %s
            ) sub
        """, where))
        inv_row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(SQL("""
            SELECT COALESCE(SUM(ABS(am.amount_residual)), 0) AS pending
            FROM account_move am
            WHERE am.company_id = %s
              AND am.move_type IN ('out_invoice', 'out_refund')
              AND am.state = 'posted'
              AND am.payment_state IN ('not_paid', 'partial', 'in_payment')
        """, parsed['company_id']))
        pending_row = self.env.cr.dictfetchone() or {}

        total_invoiced = float(inv_row.get('total_invoiced') or 0)
        total_paid = float(agg.get('total_paid') or 0)
        recovery_pct = (total_paid / total_invoiced * 100) if total_invoiced else 0

        return service._build_kpis_from_totals(
            parsed,
            total_invoiced=total_invoiced,
            total_paid=total_paid,
            total_pending=float(pending_row.get('pending') or 0),
            invoice_count=int(agg.get('invoice_count') or 0),
            payment_count=int(agg.get('payment_line_count') or 0),
            unique_clients=int(agg.get('unique_clients') or 0),
            recovery_pct=recovery_pct,
            compare_rows=compare_rows,
        )

    @api.model
    def fetch_table_page_sql(self, parsed, page, page_size, sort_by, sort_dir, search=None):
        if not self._has_payment_lines():
            return self.env['gn.accounting.invoice.payment.service']._paginate_table(
                [], page, page_size, sort_by, sort_dir, None
            )

        where = self._sql_where(parsed)
        search_sql = self._search_sql(search)
        limit = min(500, max(1, int(page_size or 50)))
        offset = (max(1, int(page)) - 1) * limit
        today = fields.Date.context_today(self)

        self.env.cr.execute(SQL("""
            SELECT COUNT(*)
            FROM payment_invoice_line pil
            JOIN account_payment ap ON ap.id = pil.payment_id
            JOIN account_move am ON am.id = pil.invoice_id
            JOIN res_partner rp ON rp.id = am.partner_id
            LEFT JOIN res_users ru ON ru.id = am.invoice_user_id
            LEFT JOIN account_journal aj ON aj.id = ap.journal_id
            WHERE %s AND %s
        """, where, search_sql))
        total = self.env.cr.fetchone()[0]

        order = 'ap.date DESC NULLS LAST, am.name'
        if sort_by == 'invoice_date_raw':
            order = 'am.invoice_date DESC NULLS LAST'
        elif sort_by == 'customer':
            order = 'rp.name ASC NULLS LAST'
        elif sort_by == 'amount_total':
            order = 'ABS(am.amount_total) DESC NULLS LAST'
        if sort_dir == 'asc':
            order = order.replace('DESC', 'ASC')

        self.env.cr.execute(SQL("""
            SELECT
                am.id AS invoice_id, ap.id AS payment_id,
                am.partner_id, am.invoice_user_id AS user_id, ap.journal_id,
                rp.name AS customer, am.name AS invoice_number,
                am.invoice_date, am.invoice_date_due,
                ap.name AS payment_receipt, ap.date AS payment_date,
                COALESCE(pil.amount, pil.actual_amount, 0) AS amount_applied,
                ABS(am.amount_untaxed) AS amount_untaxed,
                ABS(am.amount_tax) AS amount_tax,
                ABS(am.amount_total) AS amount_total,
                ABS(am.amount_residual) AS balance_pending,
                am.payment_state, ru.name AS advisor, aj.name AS bank,
                rcu.name AS payment_user, ap.create_uid AS payment_user_id,
                GREATEST(0, (%s - COALESCE(am.invoice_date_due, am.invoice_date))::integer) AS days_overdue,
                CASE WHEN am.invoice_date_due IS NOT NULL AND %s > am.invoice_date_due
                     AND am.payment_state IN ('not_paid', 'partial', 'in_payment')
                     THEN TRUE ELSE FALSE END AS is_overdue
            FROM payment_invoice_line pil
            JOIN account_payment ap ON ap.id = pil.payment_id
            JOIN account_move am ON am.id = pil.invoice_id
            JOIN res_partner rp ON rp.id = am.partner_id
            LEFT JOIN res_users ru ON ru.id = am.invoice_user_id
            LEFT JOIN res_users rcu ON rcu.id = ap.create_uid
            LEFT JOIN account_journal aj ON aj.id = ap.journal_id
            WHERE %s AND %s
            ORDER BY ap.date DESC NULLS LAST, am.name
            LIMIT %s OFFSET %s
        """, today, today, where, search_sql, limit, offset))

        rows = [self._format_sql_row(r) for r in self.env.cr.dictfetchall()]
        totals = self._compute_totals_sql(where, search_sql, parsed)
        return {
            'rows': rows,
            'page': int(page),
            'page_size': limit,
            'total_rows': total,
            'total_pages': (total + limit - 1) // limit if limit else 1,
            'totals': totals,
            'groups': None,
            'sort_by': sort_by,
            'sort_dir': sort_dir,
            'sql_mode': True,
        }

    @api.model
    def _format_sql_row(self, r):
        wizard = self.env['gn.accounting.invoice.payment.report.wizard']
        inv_date = r.get('invoice_date')
        pay_date = r.get('payment_date')
        days_itp = (pay_date - inv_date).days if inv_date and pay_date else ''
        due = r.get('invoice_date_due')
        within = ''
        if inv_date and pay_date and due:
            within = _('Sí') if pay_date <= due else _('No')
        labels = {
            'not_paid': _('Pendiente'), 'partial': _('Parcial'),
            'paid': _('Pagada'), 'in_payment': _('En proceso de pago'),
        }
        return {
            'invoice_id': r['invoice_id'],
            'payment_id': r['payment_id'],
            'partner_id': r['partner_id'],
            'user_id': r.get('user_id'),
            'journal_id': r.get('journal_id'),
            'customer': r.get('customer') or '',
            'invoice_number': r.get('invoice_number') or '',
            'invoice_date': wizard._fmt_date(inv_date),
            'invoice_date_raw': fields.Date.to_string(inv_date) if inv_date else False,
            'payment_receipt': r.get('payment_receipt') or '',
            'payment_date': wizard._fmt_date(pay_date) if pay_date else '',
            'payment_date_raw': fields.Date.to_string(pay_date) if pay_date else False,
            'days_invoice_to_payment': days_itp,
            'days_overdue': r.get('days_overdue') or 0,
            'is_overdue': bool(r.get('is_overdue')),
            'advisor': r.get('advisor') or '',
            'bank': r.get('bank') or '',
            'amount_untaxed': float(r.get('amount_untaxed') or 0),
            'amount_tax': float(r.get('amount_tax') or 0),
            'amount_total': float(r.get('amount_total') or 0),
            'amount_applied': float(r.get('amount_applied') or 0),
            'balance_pending': float(r.get('balance_pending') or 0),
            'invoice_status': labels.get(r.get('payment_state'), r.get('payment_state') or ''),
            'payment_state': r.get('payment_state') or '',
            'payment_user': r.get('payment_user') or '',
            'within_credit': within,
            'branch': '',
        }

    @api.model
    def _compute_totals_sql(self, where, search_sql, parsed):
        self.env.cr.execute(SQL("""
            SELECT
                COALESCE(SUM(sub.amount_total), 0) AS amount_total,
                COALESCE(SUM(sub.amount_applied), 0) AS amount_applied
            FROM (
                SELECT DISTINCT ON (am.id, ap.id)
                    ABS(am.amount_total) AS amount_total,
                    COALESCE(pil.amount, pil.actual_amount, 0) AS amount_applied
                FROM payment_invoice_line pil
                JOIN account_payment ap ON ap.id = pil.payment_id
                JOIN account_move am ON am.id = pil.invoice_id
                JOIN res_partner rp ON rp.id = am.partner_id
                LEFT JOIN res_users ru ON ru.id = am.invoice_user_id
                LEFT JOIN account_journal aj ON aj.id = ap.journal_id
                WHERE %s AND %s
            ) sub
        """, where, search_sql))
        t = self.env.cr.dictfetchone() or {}
        self.env.cr.execute(SQL("""
            SELECT COALESCE(SUM(ABS(am.amount_residual)), 0) AS balance_pending
            FROM account_move am
            WHERE am.company_id = %s
              AND am.move_type IN ('out_invoice', 'out_refund')
              AND am.state = 'posted'
              AND am.payment_state IN ('not_paid', 'partial', 'in_payment')
        """, parsed['company_id']))
        p = self.env.cr.dictfetchone() or {}
        return {
            'amount_untaxed': 0,
            'amount_tax': 0,
            'amount_total': float(t.get('amount_total') or 0),
            'amount_applied': float(t.get('amount_applied') or 0),
            'balance_pending': float(p.get('balance_pending') or 0),
        }

    @api.model
    def compute_charts_sql(self, parsed):
        where = self._sql_where(parsed)

        self.env.cr.execute(SQL("""
            SELECT ap.date::text AS dt, SUM(COALESCE(pil.amount, pil.actual_amount, 0)) AS paid
            FROM payment_invoice_line pil
            JOIN account_payment ap ON ap.id = pil.payment_id
            JOIN account_move am ON am.id = pil.invoice_id
            WHERE %s GROUP BY ap.date ORDER BY ap.date
        """, where))
        paid_by_date = {r['dt']: float(r['paid']) for r in self.env.cr.dictfetchall()}

        self.env.cr.execute(SQL("""
            SELECT sub.invoice_date::text AS dt, SUM(sub.amount_total) AS invoiced FROM (
                SELECT DISTINCT am.id, am.invoice_date, ABS(am.amount_total) AS amount_total
                FROM payment_invoice_line pil
                JOIN account_payment ap ON ap.id = pil.payment_id
                JOIN account_move am ON am.id = pil.invoice_id
                WHERE %s
            ) sub GROUP BY sub.invoice_date ORDER BY sub.invoice_date
        """, where))
        inv_by_date = {r['dt']: float(r['invoiced']) for r in self.env.cr.dictfetchall()}
        labels = sorted(set(inv_by_date) | set(paid_by_date))

        self.env.cr.execute(SQL("""
            SELECT COALESCE(ru.name, 'Sin asesor') AS advisor, ru.id AS user_id,
                   SUM(COALESCE(pil.amount, pil.actual_amount, 0)) AS paid
            FROM payment_invoice_line pil
            JOIN account_payment ap ON ap.id = pil.payment_id
            JOIN account_move am ON am.id = pil.invoice_id
            LEFT JOIN res_users ru ON ru.id = am.invoice_user_id
            WHERE %s GROUP BY ru.id, ru.name ORDER BY paid DESC LIMIT 10
        """, where))
        adv_rows = self.env.cr.dictfetchall()

        self.env.cr.execute(SQL("""
            SELECT customer, partner_id, SUM(paid) AS paid, SUM(inv) AS invoiced FROM (
                SELECT rp.name AS customer, rp.id AS partner_id,
                       COALESCE(pil.amount, pil.actual_amount, 0) AS paid,
                       ABS(am.amount_total) AS inv
                FROM payment_invoice_line pil
                JOIN account_payment ap ON ap.id = pil.payment_id
                JOIN account_move am ON am.id = pil.invoice_id
                JOIN res_partner rp ON rp.id = am.partner_id
                WHERE %s
            ) sub GROUP BY customer, partner_id ORDER BY invoiced DESC LIMIT 10
        """, where))
        cli_rows = self.env.cr.dictfetchall()

        self.env.cr.execute(SQL("""
            SELECT COALESCE(aj.name, 'Sin banco') AS bank, aj.id AS journal_id,
                   SUM(COALESCE(pil.amount, pil.actual_amount, 0)) AS amount
            FROM payment_invoice_line pil
            JOIN account_payment ap ON ap.id = pil.payment_id
            JOIN account_move am ON am.id = pil.invoice_id
            LEFT JOIN account_journal aj ON aj.id = ap.journal_id
            WHERE %s GROUP BY aj.id, aj.name ORDER BY amount DESC
        """, where))
        bank_rows = self.env.cr.dictfetchall()

        self.env.cr.execute(SQL("""
            SELECT am.payment_state, SUM(ABS(am.amount_residual)) AS amount
            FROM account_move am
            WHERE am.company_id = %s AND am.move_type IN ('out_invoice', 'out_refund')
              AND am.state = 'posted'
            GROUP BY am.payment_state
        """, parsed['company_id']))
        status_rows = self.env.cr.dictfetchall()

        return {
            'timeline': {
                'labels': labels,
                'series': [
                    {'key': 'invoiced', 'name': _('Facturado'),
                     'data': [inv_by_date.get(d, 0) for d in labels]},
                    {'key': 'paid', 'name': _('Pagado'),
                     'data': [paid_by_date.get(d, 0) for d in labels]},
                ],
                'drilldown': [
                    {'filter': {'date_from': d, 'date_to': d, 'payment_period': 'custom'}, 'tab': 'detail'}
                    for d in labels
                ],
            },
            'advisor_ranking': {
                'labels': [r['advisor'] for r in adv_rows],
                'paid': [float(r['paid']) for r in adv_rows],
                'invoiced': [0] * len(adv_rows),
                'drilldown': [
                    {'filter': {'user_ids': [r['user_id']]} if r.get('user_id') else {}, 'tab': 'detail'}
                    for r in adv_rows
                ],
            },
            'client_ranking': {
                'labels': [r['customer'] for r in cli_rows],
                'invoiced': [float(r['invoiced'] or 0) for r in cli_rows],
                'paid': [float(r['paid'] or 0) for r in cli_rows],
                'pending': [0] * len(cli_rows),
                'drilldown': [
                    {'filter': {'partner_ids': [r['partner_id']]}, 'tab': 'detail'}
                    for r in cli_rows
                ],
            },
            'bank_distribution': {
                'labels': [r['bank'] for r in bank_rows],
                'data': [float(r['amount']) for r in bank_rows],
                'drilldown': [
                    {'filter': {'journal_ids': [r['journal_id']]} if r.get('journal_id') else {}, 'tab': 'detail'}
                    for r in bank_rows
                ],
            },
            'status_distribution': {
                'labels': [r['payment_state'] for r in status_rows],
                'data': [float(r['amount']) for r in status_rows],
                'drilldown': [
                    {'filter': {'payment_state': r['payment_state']}, 'tab': 'detail'}
                    for r in status_rows
                ],
            },
            'category_distribution': {'labels': [], 'data': [], 'drilldown': []},
        }

    @api.model
    def compute_aging_sql(self, parsed):
        today = fields.Date.context_today(self)
        self.env.cr.execute("""
            SELECT bucket, COUNT(*) AS cnt, SUM(amount) AS amount FROM (
                SELECT
                    CASE
                        WHEN GREATEST(0, (%s - COALESCE(am.invoice_date_due, am.invoice_date))::integer) = 0
                            THEN 'current'
                        WHEN GREATEST(0, (%s - COALESCE(am.invoice_date_due, am.invoice_date))::integer) <= 30
                            THEN '1_30'
                        WHEN GREATEST(0, (%s - COALESCE(am.invoice_date_due, am.invoice_date))::integer) <= 60
                            THEN '31_60'
                        WHEN GREATEST(0, (%s - COALESCE(am.invoice_date_due, am.invoice_date))::integer) <= 90
                            THEN '61_90'
                        ELSE '90_plus'
                    END AS bucket,
                    ABS(am.amount_residual) AS amount
                FROM account_move am
                WHERE am.company_id = %s
                  AND am.move_type IN ('out_invoice', 'out_refund')
                  AND am.state = 'posted'
                  AND am.payment_state IN ('not_paid', 'partial', 'in_payment')
            ) sub GROUP BY bucket
        """, (today, today, today, today, parsed['company_id']))
        bucket_labels = {
            'current': _('No vencido'), '1_30': _('1-30 días'),
            '31_60': _('31-60 días'), '61_90': _('61-90 días'), '90_plus': _('+90 días'),
        }
        buckets = {k: {'label': v, 'amount': 0.0, 'count': 0} for k, v in bucket_labels.items()}
        for r in self.env.cr.dictfetchall():
            if r['bucket'] in buckets:
                buckets[r['bucket']]['amount'] = float(r['amount'] or 0)
                buckets[r['bucket']]['count'] = int(r['cnt'] or 0)
        return {'buckets': buckets, 'top_overdue_clients': [], 'overdue_invoices': []}
