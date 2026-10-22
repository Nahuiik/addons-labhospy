# -*- coding: utf-8 -*-
"""Servicio analítico del tablero premium Facturas y pagos."""

import json
import logging
import time
from collections import defaultdict
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

PAYMENT_PERIOD_PRESETS = (
    'today', 'yesterday', 'this_week', 'this_month', 'last_month',
    'this_quarter', 'this_year', 'custom',
)
COMPARE_MODES = ('none', 'previous', 'yoy', 'custom')
VIEW_MODES = ('by_payment', 'by_invoice', 'consolidated')
TABLE_SORT_FIELDS = {
    'customer', 'invoice_number', 'invoice_date_raw', 'payment_receipt',
    'payment_date_raw', 'days_invoice_to_payment', 'advisor', 'bank',
    'amount_untaxed', 'amount_tax', 'amount_total', 'amount_applied',
    'balance_pending', 'days_overdue', 'invoice_status', 'due_date_raw',
    'collection_priority', 'collection_priority_score', 'branch', 'payment_state',
}
GROUP_BY_FIELDS = (
    'customer', 'advisor', 'bank', 'branch', 'invoice_status',
    'payment_state', 'payment_date', 'payment_month', 'invoice_month',
)
OVERDUE_FILTER_MODES = ('all_balance', 'overdue_only', 'upcoming_due')


class InvoicePaymentReportService(models.AbstractModel):
    _name = 'gn.accounting.invoice.payment.service'
    _description = 'Servicio analítico Facturas y pagos Premium'

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @api.model
    def _check_report_access(self):
        if not (
            self.env.user.has_group('account.group_account_user')
            or self.env.user.has_group('sales_team.group_sale_salesman')
        ):
            raise AccessError(_('No tiene permiso para acceder al reporte de facturas y pagos.'))

    # ------------------------------------------------------------------
    # Filter parsing
    # ------------------------------------------------------------------

    @api.model
    def _today(self):
        return fields.Date.context_today(self)

    @api.model
    def _period_bounds(self, preset, date_from=None, date_to=None):
        today = self._today()
        if preset == 'today':
            return today, today
        if preset == 'yesterday':
            y = today - timedelta(days=1)
            return y, y
        if preset == 'this_week':
            start = today - timedelta(days=today.weekday())
            return start, today
        if preset == 'this_month':
            return today.replace(day=1), today
        if preset == 'last_month':
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            return last_prev.replace(day=1), last_prev
        if preset == 'this_quarter':
            q_month = ((today.month - 1) // 3) * 3 + 1
            return date(today.year, q_month, 1), today
        if preset == 'this_year':
            return date(today.year, 1, 1), today
        df = fields.Date.from_string(date_from) if date_from else today.replace(day=1)
        dt = fields.Date.from_string(date_to) if date_to else today
        return df, dt

    @api.model
    def _comparison_bounds(self, date_from, date_to, compare_mode):
        if compare_mode == 'none':
            return None, None
        span = (date_to - date_from).days + 1
        if compare_mode == 'previous':
            prev_to = date_from - timedelta(days=1)
            prev_from = prev_to - timedelta(days=span - 1)
            return prev_from, prev_to
        if compare_mode == 'yoy':
            try:
                return date_from.replace(year=date_from.year - 1), date_to.replace(year=date_to.year - 1)
            except ValueError:
                return date_from - timedelta(days=365), date_to - timedelta(days=365)
        return None, None

    @api.model
    def _parse_filters(self, filters=None):
        filters = dict(filters or {})
        company_id = filters.get('company_id') or self.env.company.id
        company = self.env['res.company'].browse(company_id)
        if company not in self.env.companies:
            company = self.env.company

        payment_preset = filters.get('payment_period') or 'this_month'
        date_from, date_to = self._period_bounds(
            payment_preset,
            filters.get('date_from'),
            filters.get('date_to'),
        )
        inv_from = filters.get('invoice_date_from')
        inv_to = filters.get('invoice_date_to')
        compare_mode = filters.get('compare_mode') or 'none'
        cmp_from, cmp_to = self._comparison_bounds(date_from, date_to, compare_mode)

        return {
            'company': company,
            'company_id': company.id,
            'date_from': date_from,
            'date_to': date_to,
            'invoice_date_from': fields.Date.from_string(inv_from) if inv_from else False,
            'invoice_date_to': fields.Date.from_string(inv_to) if inv_to else False,
            'branch_ids': filters.get('branch_ids') or [],
            'user_ids': filters.get('user_ids') or [],
            'partner_ids': filters.get('partner_ids') or [],
            'journal_ids': filters.get('journal_ids') or [],
            'categ_ids': filters.get('categ_ids') or [],
            'payment_state': filters.get('payment_state') or 'all',
            'credit_term_filter': filters.get('credit_term_filter') or 'all',
            'show_pending_invoices': filters.get('show_pending_invoices', True),
            'overdue_only': bool(filters.get('overdue_only')),
            'overdue_filter_mode': filters.get('overdue_filter_mode') or (
                'overdue_only' if filters.get('overdue_only') else 'all_balance'
            ),
            'upcoming_days': int(filters.get('upcoming_days') or 7),
            'amount_min': float(filters.get('amount_min') or 0),
            'amount_max': float(filters.get('amount_max') or 0),
            'search': (filters.get('search') or '').strip().lower(),
            'invoice_number': (filters.get('invoice_number') or '').strip(),
            'payment_receipt': (filters.get('payment_receipt') or '').strip(),
            'payment_user_ids': filters.get('payment_user_ids') or [],
            'view_mode': filters.get('view_mode') or 'by_payment',
            'compare_mode': compare_mode,
            'compare_date_from': cmp_from,
            'compare_date_to': cmp_to,
            'active_tab': filters.get('active_tab') or 'summary',
        }

    @api.model
    def _filters_to_wizard_vals(self, parsed):
        vals = {
            'date_from': parsed['date_from'],
            'date_to': parsed['date_to'],
            'company_id': parsed['company_id'],
            'payment_state': parsed['payment_state'],
            'credit_term_filter': parsed['credit_term_filter'],
            'show_pending_invoices': parsed['show_pending_invoices'],
            'branch_ids': [(6, 0, parsed['branch_ids'])],
            'user_ids': [(6, 0, parsed['user_ids'])],
            'partner_ids': [(6, 0, parsed['partner_ids'])],
            'journal_ids': [(6, 0, parsed['journal_ids'])],
            'categ_ids': [(6, 0, parsed['categ_ids'])],
        }
        if parsed['invoice_date_from']:
            vals['invoice_date_from'] = parsed['invoice_date_from']
        if parsed['invoice_date_to']:
            vals['invoice_date_to'] = parsed['invoice_date_to']
        return vals

    @api.model
    def _collect_rows(self, parsed):
        """Obtiene filas usando la lógica probada del wizard."""
        Wizard = self.env['gn.accounting.invoice.payment.report.wizard']
        wiz = Wizard.create(self._filters_to_wizard_vals(parsed))
        try:
            data = wiz._build_report_data()
            rows = data['rows']
        finally:
            wiz.unlink()
        return self._post_filter_rows(rows, parsed)

    @api.model
    def _post_filter_rows(self, rows, parsed):
        result = []
        for row in rows:
            if parsed['overdue_only'] and not row.get('is_overdue') and row.get('balance_pending', 0) <= 0:
                continue
            if parsed['amount_min'] and row.get('amount_total', 0) < parsed['amount_min']:
                continue
            if parsed['amount_max'] and row.get('amount_total', 0) > parsed['amount_max']:
                continue
            if parsed['invoice_number'] and parsed['invoice_number'].lower() not in (
                row.get('invoice_number') or ''
            ).lower():
                continue
            if parsed['payment_receipt'] and parsed['payment_receipt'].lower() not in (
                row.get('payment_receipt') or ''
            ).lower():
                continue
            if parsed['payment_user_ids'] and row.get('payment_user_id') not in parsed['payment_user_ids']:
                continue
            if parsed['search']:
                blob = ' '.join(filter(None, [
                    row.get('customer'), row.get('invoice_number'),
                    row.get('payment_receipt'), row.get('advisor'), row.get('bank'),
                ])).lower()
                if parsed['search'] not in blob:
                    continue
            result.append(row)
        return result

    @api.model
    def _top_n_chart_series(self, items, sort_key='paid', top_n=10, drilldown_key=None):
        """Construye series de gráfico con Top N + Otros."""
        sorted_items = sorted(items, key=lambda x: x['metrics'].get(sort_key, 0), reverse=True)
        top = sorted_items[:top_n]
        rest = sorted_items[top_n:]
        if rest:
            others = {
                'label': _('Otros'),
                'full_label': _('Otros (%s registros)', len(rest)),
                'metrics': defaultdict(float),
                'meta': {'invoice_count': 0, 'payment_count': 0, 'doc_count': 0},
                'drilldown': {},
            }
            for item in rest:
                for mk, mv in item['metrics'].items():
                    if mk == 'recovery_pct':
                        continue
                    others['metrics'][mk] += mv
                for mk, mv in item.get('meta', {}).items():
                    if isinstance(mv, (int, float)):
                        others['meta'][mk] = others['meta'].get(mk, 0) + mv
            inv = others['metrics'].get('invoiced', 0)
            paid = others['metrics'].get('paid', 0)
            others['metrics']['recovery_pct'] = (paid / inv * 100) if inv else 0
            others['metrics'] = dict(others['metrics'])
            top.append(others)
        metric_keys = ('invoiced', 'paid', 'pending', 'invoice_count', 'recovery_pct', 'avg_collection_days')
        result = {
            'labels': [i['label'] for i in top],
            'full_labels': [i.get('full_label') or i['label'] for i in top],
            'metrics': {mk: [i['metrics'].get(mk, 0) for i in top] for mk in metric_keys},
            'meta': [i.get('meta', {}) for i in top],
            'drilldown': [i.get('drilldown', {}) for i in top],
        }
        return result

    @api.model
    def _pie_top_n(self, items, top_n=6):
        sorted_items = sorted(items, key=lambda x: x['amount'], reverse=True)
        top = sorted_items[:top_n]
        rest = sorted_items[top_n:]
        if rest:
            top.append({
                'label': _('Otros'),
                'amount': sum(r['amount'] for r in rest),
                'drilldown': {},
            })
        total = sum(i['amount'] for i in top) or 1
        return {
            'labels': [i['label'] for i in top],
            'data': [i['amount'] for i in top],
            'percentages': [round(i['amount'] / total * 100, 1) for i in top],
            'drilldown': [i.get('drilldown', {}) for i in top],
            'total': total,
        }

    @api.model
    def _collection_priority(self, row, max_balance=1.0):
        balance = float(row.get('balance_pending') or 0)
        days = int(row.get('days_overdue') or 0)
        rank = int(row.get('customer_rank_num') or 0)
        bal_score = min(balance / max_balance, 1.0) if max_balance else 0
        days_score = min(days / 90.0, 1.0)
        rank_score = min(rank / 10.0, 1.0) if rank else 0.25
        score = bal_score * 0.5 + days_score * 0.35 + rank_score * 0.15
        if score >= 0.65:
            level, tone = _('Alta'), 'danger'
        elif score >= 0.35:
            level, tone = _('Media'), 'warning'
        else:
            level, tone = _('Baja'), 'info'
        tooltip = _(
            'Prioridad %(level)s: saldo %(bal).2f, %(days)s días de atraso, '
            'ranking cliente %(rank)s (pesos: saldo 50%%, atraso 35%%, cliente 15%%).',
            level=level, bal=balance, days=days, rank=rank or _('sin ranking'),
        )
        return {'level': level, 'tone': tone, 'score': round(score, 3), 'tooltip': tooltip}

    @api.model
    def _enrich_rows(self, rows):
        max_bal = max((float(r.get('balance_pending') or 0) for r in rows), default=1.0) or 1.0
        for row in rows:
            if row.get('due_date_raw') and not row.get('due_date'):
                d = fields.Date.from_string(row['due_date_raw'])
                row['due_date'] = d.strftime('%d/%m/%Y')
            if row.get('invoice_date_raw'):
                row['invoice_month'] = row['invoice_date_raw'][:7]
            if row.get('payment_date_raw'):
                row['payment_month'] = row['payment_date_raw'][:7]
            pri = self._collection_priority(row, max_bal)
            row['collection_priority'] = pri['level']
            row['collection_priority_score'] = pri['score']
            row['collection_priority_tooltip'] = pri['tooltip']
            row['collection_priority_tone'] = pri['tone']
        return rows

    @api.model
    def _table_meta(self, rows):
        return {
            'payment_count': sum(1 for r in rows if r.get('_has_payment')),
            'invoice_count': len({r.get('invoice_id') for r in rows if r.get('invoice_id')}),
            'client_count': len({r.get('partner_id') for r in rows if r.get('partner_id')}),
        }

    @api.model
    def _group_key(self, row, group_by):
        if group_by == 'payment_month':
            return row.get('payment_month') or _('Sin mes de pago')
        if group_by == 'invoice_month':
            return row.get('invoice_month') or _('Sin mes de factura')
        if group_by == 'payment_date':
            return row.get('payment_date') or _('Sin fecha de pago')
        if group_by == 'payment_state':
            return row.get('invoice_status') or _('Sin estado')
        return row.get(group_by) or _('Sin valor')

    @api.model
    def _transform_view_mode(self, rows, view_mode):
        rows = self._enrich_rows(list(rows))
        if view_mode == 'by_payment':
            return rows
        if view_mode == 'by_invoice':
            grouped = {}
            for row in rows:
                iid = row.get('invoice_id')
                if iid not in grouped:
                    grouped[iid] = dict(row)
                    grouped[iid]['amount_applied'] = row.get('amount_applied', 0) if row.get('_has_payment') else 0
                    grouped[iid]['payment_receipt'] = ''
                    grouped[iid]['payment_date'] = ''
                    grouped[iid]['payment_date_raw'] = False
                    grouped[iid]['bank'] = ''
                    grouped[iid]['payment_user'] = ''
                    grouped[iid]['_has_payment'] = False
                elif row.get('_has_payment'):
                    grouped[iid]['amount_applied'] += row.get('amount_applied', 0)
                grouped[iid]['balance_pending'] = max(
                    0.0,
                    grouped[iid].get('amount_total', 0) - grouped[iid]['amount_applied'],
                )
            return list(grouped.values())
        if view_mode == 'consolidated':
            grouped = {}
            children = defaultdict(list)
            for row in rows:
                iid = row.get('invoice_id')
                if iid not in grouped:
                    grouped[iid] = dict(row)
                    grouped[iid]['amount_applied'] = 0
                    grouped[iid]['_children'] = []
                    grouped[iid]['_expandable'] = False
                if row.get('_has_payment'):
                    child = {k: v for k, v in row.items() if not k.startswith('_') or k == '_has_payment'}
                    children[iid].append(child)
                    grouped[iid]['amount_applied'] += row.get('amount_applied', 0)
                grouped[iid]['balance_pending'] = max(
                    0.0,
                    grouped[iid].get('amount_total', 0) - grouped[iid]['amount_applied'],
                )
            result = []
            for iid, parent in grouped.items():
                parent['_children'] = children.get(iid, [])
                parent['_expandable'] = len(parent['_children']) > 1
                parent['payment_count'] = len(parent['_children'])
                if parent['_children']:
                    parent['payment_receipt'] = _('%s pagos') % len(parent['_children'])
                result.append(parent)
            return result
        return rows

    @api.model
    def _public_row(self, row):
        skip = {k for k in row if k.startswith('_') and k not in ('_children', '_expandable')}
        pub = {k: v for k, v in row.items() if k not in skip}
        if row.get('_children') is not None:
            pub['children'] = row.get('_children', [])
            pub['expandable'] = row.get('_expandable', False)
        return pub

    # ------------------------------------------------------------------
    # Public RPC
    # ------------------------------------------------------------------

    @api.model
    def get_filter_options(self, company_id=None):
        self._check_report_access()
        company_id = company_id or self.env.company.id
        company = self.env['res.company'].browse(company_id)
        branches = self.env['res.branch'].search([('company_id', '=', company_id)], order='name')
        users = self.env['res.users'].search([
            ('share', '=', False),
            ('company_ids', 'in', company_id),
        ], order='name', limit=300)
        journals = self.env['account.journal'].search([
            ('company_id', '=', company_id),
            ('type', 'in', ('bank', 'cash')),
        ], order='name')
        categories = self.env['product.category'].search([], order='complete_name', limit=500)
        self.env['gn.accounting.invoice.payment.saved.view'].ensure_system_views()
        saved_views = self.env['gn.accounting.invoice.payment.saved.view'].list_views(company_id)
        return {
            'company_id': company.id,
            'company_name': company.name,
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
            'currency_symbol': company.currency_id.symbol,
            'currency_id': company.currency_id.id,
            'payment_period_presets': [
                {'id': 'today', 'label': _('Hoy')},
                {'id': 'yesterday', 'label': _('Ayer')},
                {'id': 'this_week', 'label': _('Esta semana')},
                {'id': 'this_month', 'label': _('Mes actual')},
                {'id': 'last_month', 'label': _('Mes anterior')},
                {'id': 'this_quarter', 'label': _('Trimestre actual')},
                {'id': 'this_year', 'label': _('Año actual')},
                {'id': 'custom', 'label': _('Personalizado')},
            ],
            'compare_modes': [
                {'id': 'none', 'label': _('Sin comparación')},
                {'id': 'previous', 'label': _('Período anterior')},
                {'id': 'yoy', 'label': _('Mismo período año anterior')},
            ],
            'view_modes': [
                {'id': 'by_payment', 'label': _('Por pago')},
                {'id': 'by_invoice', 'label': _('Por factura')},
                {'id': 'consolidated', 'label': _('Vista consolidada')},
            ],
            'branches': [{'id': b.id, 'name': b.name} for b in branches],
            'users': [{'id': u.id, 'name': u.name} for u in users],
            'journals': [{'id': j.id, 'name': j.display_name} for j in journals],
            'categories': [{'id': c.id, 'name': c.display_name} for c in categories],
            'saved_views': saved_views,
            'thresholds': self._thresholds(company),
            'default_page_size': company.inv_pay_table_page_size or 50,
        }

    @api.model
    def get_dashboard_init(self, filters=None):
        """Carga inicial: metadatos + KPIs + gráficos + hallazgos + primera página."""
        self._check_report_access()
        t0 = time.time()
        parsed = self._parse_filters(filters)
        agg = self.env['gn.accounting.invoice.payment.aggregation']
        sql_mode = agg.should_use_sql_mode(parsed)
        page_size = parsed['company'].inv_pay_table_page_size or 50

        compare_rows = []
        if not sql_mode and parsed['compare_date_from'] and parsed['compare_date_to']:
            cmp_parsed = dict(parsed)
            cmp_parsed.update({
                'date_from': parsed['compare_date_from'],
                'date_to': parsed['compare_date_to'],
                'compare_mode': 'none',
            })
            compare_rows = self._transform_view_mode(
                self._collect_rows(cmp_parsed), parsed['view_mode']
            )

        if sql_mode:
            kpis = agg.compute_summary_sql(parsed, compare_rows)
            charts = agg.compute_charts_sql(parsed)
            aging = agg.compute_aging_sql(parsed)
            table = agg.fetch_table_page_sql(
                parsed, 1, page_size, 'payment_date_raw', 'desc', None
            )
            row_count = table.get('total_rows', 0)
            insights = self._build_insights_from_charts(charts, kpis, aging)
        else:
            rows = self._transform_view_mode(
                self._collect_rows(parsed), parsed['view_mode']
            )
            kpis = self._build_kpis(rows, compare_rows, parsed)
            charts = self._build_charts(rows, parsed)
            insights = self._build_insights(rows, kpis, parsed)
            aging = self._build_aging(rows, parsed)
            table = self._paginate_table(rows, 1, page_size, 'payment_date_raw', 'desc', None)
            row_count = len(rows)

        duration_ms = int((time.time() - t0) * 1000)
        return {
            'success': True,
            'header': self._build_header(parsed, row_count, duration_ms, sql_mode),
            'kpis': kpis,
            'charts': charts,
            'insights': insights,
            'aging': aging,
            'table': table,
            'currency': {
                'id': parsed['company'].currency_id.id,
                'symbol': parsed['company'].currency_id.symbol,
            },
            'thresholds': self._thresholds(parsed['company']),
            'filters_applied': self._filters_summary(parsed),
            'sql_mode': sql_mode,
        }

    @api.model
    def get_overdue_page(self, filters=None, page=1, page_size=50, sort_by='days_overdue', sort_dir='desc'):
        self._check_report_access()
        parsed = self._parse_filters(filters)
        rows = self._transform_view_mode(self._collect_rows(parsed), parsed['view_mode'])
        aging = self._build_aging(rows, parsed)
        invoices = aging.get('overdue_invoices', [])
        reverse = (sort_dir or 'desc') == 'desc'
        invoices = sorted(invoices, key=lambda r: r.get(sort_by) or 0, reverse=reverse)
        page = max(1, int(page or 1))
        page_size = min(500, max(1, int(page_size or 50)))
        total = len(invoices)
        start = (page - 1) * page_size
        page_rows = invoices[start:start + page_size]
        inv_map = {r.get('invoice_id'): r for r in invoices}
        totals = {
            'amount_total': sum(r.get('amount_total', 0) for r in inv_map.values()),
            'balance_pending': sum(r.get('balance_pending', 0) for r in inv_map.values()),
            'invoice_count': len(inv_map),
            'avg_days_overdue': round(
                sum(r.get('days_overdue', 0) for r in inv_map.values()) / len(inv_map), 1
            ) if inv_map else None,
        }
        return {
            'rows': page_rows,
            'page': page,
            'page_size': page_size,
            'total_rows': total,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'totals': totals,
            'aging': aging,
            'sort_by': sort_by,
            'sort_dir': sort_dir,
            'title': _('Facturas vencidas') if parsed['overdue_filter_mode'] == 'overdue_only' else _('Cartera con saldo'),
        }

    @api.model
    def get_table_page(self, filters=None, page=1, page_size=50, sort_by='payment_date_raw',
                       sort_dir='desc', search=None, group_by=None):
        self._check_report_access()
        parsed = self._parse_filters(filters)
        if search:
            parsed['search'] = search
        agg = self.env['gn.accounting.invoice.payment.aggregation']
        if agg.should_use_sql_mode(parsed):
            result = agg.fetch_table_page_sql(
                parsed, page, page_size, sort_by, sort_dir, search
            )
        else:
            rows = self._transform_view_mode(
                self._collect_rows(parsed), parsed['view_mode']
            )
            result = self._paginate_table(rows, page, page_size, sort_by, sort_dir, group_by)
        if group_by and not result.get('groups'):
            result['groups'] = result.get('groups')
        return result

    @api.model
    def get_record_detail(self, invoice_id, payment_id=None):
        self._check_report_access()
        invoice = self.env['account.move'].browse(invoice_id)
        if not invoice.exists():
            return {'success': False, 'error': _('Factura no encontrada.')}
        payment = self.env['account.payment'].browse(payment_id) if payment_id else False
        payments = []
        widget = invoice.invoice_payments_widget or {}
        for item in widget.get('content', []):
            pid = item.get('account_payment_id')
            if pid:
                pay = self.env['account.payment'].browse(pid)
                payments.append({
                    'id': pay.id,
                    'name': pay.name,
                    'date': item.get('date') or (pay.date and fields.Date.to_string(pay.date)),
                    'amount': item.get('amount', 0),
                    'journal': pay.journal_id.display_name if pay.journal_id else '',
                    'user': pay.create_uid.name if pay.create_uid else '',
                })
        categories = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id
        ).mapped('product_id.categ_id.complete_name')
        return {
            'success': True,
            'invoice': {
                'id': invoice.id,
                'name': invoice.name,
                'partner': invoice.partner_id.display_name,
                'partner_id': invoice.partner_id.id,
                'invoice_date': fields.Date.to_string(invoice.invoice_date) if invoice.invoice_date else '',
                'due_date': fields.Date.to_string(invoice.invoice_date_due) if invoice.invoice_date_due else '',
                'amount_total': abs(invoice.amount_total),
                'amount_residual': abs(invoice.amount_residual),
                'payment_state': invoice.payment_state,
                'advisor': invoice.invoice_user_id.name if invoice.invoice_user_id else '',
                'branch': invoice.branch_id.name if getattr(invoice, 'branch_id', False) else '',
                'categories': ', '.join(sorted(set(filter(None, categories)))),
            },
            'payment': {
                'id': payment.id,
                'name': payment.name,
                'date': fields.Date.to_string(payment.date) if payment and payment.date else '',
                'journal': payment.journal_id.display_name if payment and payment.journal_id else '',
            } if payment else None,
            'payments': payments,
            'timeline': self._build_timeline(invoice, payments),
            'actions': {
                'invoice': {'res_model': 'account.move', 'res_id': invoice.id},
                'partner': {'res_model': 'res.partner', 'res_id': invoice.partner_id.id},
                'payment': {'res_model': 'account.payment', 'res_id': payment.id} if payment else None,
            },
        }

    @api.model
    def save_filter_view(self, name, filters, is_default=False):
        self._check_report_access()
        return self.env['gn.accounting.invoice.payment.saved.view'].save_view(
            name, filters, filters.get('company_id'), is_default
        )

    @api.model
    def delete_filter_view(self, view_id):
        self._check_report_access()
        return self.env['gn.accounting.invoice.payment.saved.view'].delete_view(view_id)

    # ------------------------------------------------------------------
    # KPIs & analytics
    # ------------------------------------------------------------------

    @api.model
    def _thresholds(self, company):
        return {
            'recovery_good': company.inv_pay_recovery_good_threshold or 85.0,
            'recovery_warn': company.inv_pay_recovery_warn_threshold or 65.0,
            'punctuality_good': company.inv_pay_punctuality_good_threshold or 80.0,
            'punctuality_warn': company.inv_pay_punctuality_warn_threshold or 60.0,
        }

    @api.model
    def _unique_invoice_totals(self, rows):
        seen = {}
        for row in rows:
            iid = row.get('invoice_id')
            if iid and iid not in seen:
                seen[iid] = row.get('amount_total', 0)
        return seen

    @api.model
    def _build_kpis(self, rows, compare_rows, parsed):
        inv_map = self._unique_invoice_totals(rows)
        total_invoiced = sum(inv_map.values())
        total_paid = sum(r.get('amount_applied', 0) for r in rows if r.get('_has_payment'))
        total_pending = sum(
            max(0.0, r.get('amount_total', 0) - r.get('amount_applied', 0))
            for r in rows
            if not r.get('_has_payment') or r.get('balance_pending', 0) > 0
        )
        # Dedupe pending by invoice
        pending_by_inv = {}
        for row in rows:
            iid = row.get('invoice_id')
            if iid:
                pending_by_inv[iid] = row.get('balance_pending', 0)
        total_pending = sum(pending_by_inv.values())

        overdue_rows = [r for r in rows if r.get('is_overdue')]
        overdue_balance = sum(
            self._unique_invoice_totals(overdue_rows).values()
        )
        recovery_pct = (total_paid / total_invoiced * 100) if total_invoiced else 0
        paid_with_terms = [r for r in rows if r.get('_has_payment') and r.get('within_credit')]
        punctuality_pct = (
            sum(1 for r in paid_with_terms if r.get('_within_credit_bool')) / len(paid_with_terms) * 100
            if paid_with_terms else 0
        )
        payment_rows = [r for r in rows if r.get('_has_payment')]
        avg_invoice = total_invoiced / len(inv_map) if inv_map else 0
        avg_payment = total_paid / len(payment_rows) if payment_rows else 0
        dso_vals = [
            r['days_invoice_to_payment'] for r in payment_rows
            if isinstance(r.get('days_invoice_to_payment'), int)
        ]
        avg_collection_days = sum(dso_vals) / len(dso_vals) if dso_vals else 0
        unique_clients = len({r.get('partner_id') for r in rows if r.get('partner_id')})

        cmp_kpis = {}
        if compare_rows:
            cmp_inv = self._unique_invoice_totals(compare_rows)
            cmp_invoiced = sum(cmp_inv.values())
            cmp_paid = sum(r.get('amount_applied', 0) for r in compare_rows if r.get('_has_payment'))
            cmp_recovery = (cmp_paid / cmp_invoiced * 100) if cmp_invoiced else None
            cmp_kpis = {
                'total_invoiced': cmp_invoiced,
                'total_paid': cmp_paid,
                'recovery_pct': cmp_recovery,
            }

        def _delta(current, previous):
            if previous in (None, 0):
                return {'abs': None, 'pct': None, 'label': _('Sin base comparable')}
            abs_d = current - previous
            pct_d = (abs_d / previous * 100) if previous else None
            return {'abs': abs_d, 'pct': pct_d, 'label': None}

        return {
            'cards': [
                self._kpi_card('total_invoiced', _('Total facturado'), total_invoiced,
                               _('Suma de facturas únicas en el período'), 'info', cmp_kpis.get('total_invoiced')),
                self._kpi_card('total_paid', _('Total pagado'), total_paid,
                               _('Pagos registrados en el período'), 'success', cmp_kpis.get('total_paid')),
                self._kpi_card('total_pending', _('Saldo pendiente'), total_pending,
                               _('Saldo por cobrar según facturas filtradas'), 'warning', None),
                self._kpi_card('recovery_pct', _('Índice de recuperación'), recovery_pct,
                               _('Total pagado ÷ total facturado × 100'), 'primary', cmp_kpis.get('recovery_pct'), is_pct=True),
                self._kpi_card('invoice_count', _('Facturas'), len(inv_map),
                               _('Cantidad de facturas únicas'), 'neutral', None, is_count=True),
                self._kpi_card('payment_count', _('Pagos'), len(payment_rows),
                               _('Movimientos de pago en el período'), 'neutral', None, is_count=True),
                self._kpi_card('avg_invoice', _('Ticket promedio'), avg_invoice,
                               _('Facturación media por factura'), 'info', None),
                self._kpi_card('avg_payment', _('Pago promedio'), avg_payment,
                               _('Monto medio por pago'), 'success', None),
                self._kpi_card('overdue_count', _('Facturas vencidas'), len(set(r.get('invoice_id') for r in overdue_rows)),
                               _('Facturas con saldo y fecha vencida'), 'danger', None, is_count=True),
                self._kpi_card('overdue_balance', _('Saldo vencido'), overdue_balance,
                               _('Monto en facturas vencidas'), 'danger', None),
                self._kpi_card('avg_collection_days', _('Días promedio de cobro'), avg_collection_days,
                               _('Días entre factura y pago'), 'neutral', None, is_days=True),
                self._kpi_card('punctuality_pct', _('Pagos dentro del plazo'), punctuality_pct,
                               _('% pagos realizados antes o en la fecha de vencimiento'), 'success', None, is_pct=True),
                self._kpi_card('unique_clients', _('Clientes únicos'), unique_clients,
                               _('Clientes distintos en el resultado'), 'neutral', None, is_count=True),
            ],
            'recovery_index': recovery_pct,
            'punctuality_index': punctuality_pct,
        }

    @api.model
    def _build_kpis_from_totals(self, parsed, compare_rows=None, total_invoiced=0,
                                total_paid=0, total_pending=0, invoice_count=0,
                                payment_count=0, unique_clients=0, recovery_pct=0):
        """Construye KPIs desde totales agregados (modo SQL)."""
        cmp_kpis = {}
        if compare_rows:
            cmp_inv = self._unique_invoice_totals(compare_rows)
            cmp_invoiced = sum(cmp_inv.values())
            cmp_paid = sum(r.get('amount_applied', 0) for r in compare_rows if r.get('_has_payment'))
            cmp_kpis = {
                'total_invoiced': cmp_invoiced,
                'total_paid': cmp_paid,
                'recovery_pct': (cmp_paid / cmp_invoiced * 100) if cmp_invoiced else None,
            }
        avg_invoice = total_invoiced / invoice_count if invoice_count else 0
        avg_payment = total_paid / payment_count if payment_count else 0
        return {
            'cards': [
                self._kpi_card('total_invoiced', _('Total facturado'), total_invoiced,
                               _('Suma de facturas únicas en el período'), 'info', cmp_kpis.get('total_invoiced')),
                self._kpi_card('total_paid', _('Total pagado'), total_paid,
                               _('Pagos registrados en el período'), 'success', cmp_kpis.get('total_paid')),
                self._kpi_card('total_pending', _('Saldo pendiente'), total_pending,
                               _('Saldo por cobrar'), 'warning', None),
                self._kpi_card('recovery_pct', _('Índice de recuperación'), recovery_pct,
                               _('Total pagado ÷ total facturado × 100'), 'primary',
                               cmp_kpis.get('recovery_pct'), is_pct=True),
                self._kpi_card('invoice_count', _('Facturas'), invoice_count,
                               _('Cantidad de facturas únicas'), 'neutral', None, is_count=True),
                self._kpi_card('payment_count', _('Pagos'), payment_count,
                               _('Movimientos de pago'), 'neutral', None, is_count=True),
                self._kpi_card('avg_invoice', _('Ticket promedio'), avg_invoice,
                               _('Facturación media por factura'), 'info', None),
                self._kpi_card('avg_payment', _('Pago promedio'), avg_payment,
                               _('Monto medio por pago'), 'success', None),
                self._kpi_card('unique_clients', _('Clientes únicos'), unique_clients,
                               _('Clientes distintos'), 'neutral', None, is_count=True),
            ],
            'recovery_index': recovery_pct,
            'punctuality_index': 0,
        }

    @api.model
    def _kpi_card(self, key, label, value, tooltip, tone, compare_value=None,
                  is_pct=False, is_count=False, is_days=False):
        delta = None
        if compare_value is not None and not is_count:
            if compare_value == 0:
                delta = {'pct': None, 'label': _('Sin base comparable')}
            elif is_pct:
                delta = {'pp': value - compare_value, 'is_pp': True}
            else:
                delta = {'pct': (value - compare_value) / compare_value * 100}
        return {
            'key': key,
            'label': label,
            'value': value,
            'tooltip': tooltip,
            'tone': tone,
            'is_pct': is_pct,
            'is_count': is_count,
            'is_days': is_days,
            'delta': delta,
        }

    @api.model
    def _fmt_money(self, amount, company):
        return formatLang(
            self.env,
            round(float(amount or 0), 2),
            digits=2,
            currency_obj=company.currency_id,
        )

    @api.model
    def _build_timeline_data(self, rows, parsed, base='payment', scope='period'):
        """Serie temporal con alcance y base temporal configurables."""
        daily = defaultdict(lambda: {'invoiced': 0.0, 'paid': 0.0})
        inv_seen = defaultdict(set)
        period_start = fields.Date.to_string(parsed['date_from'])
        period_end = fields.Date.to_string(parsed['date_to'])

        for row in rows:
            if base == 'payment':
                pdate = row.get('payment_date_raw')
                if pdate and row.get('_has_payment'):
                    daily[pdate]['paid'] += row.get('amount_applied', 0)
                    iid = row.get('invoice_id')
                    if iid and iid not in inv_seen[pdate]:
                        daily[pdate]['invoiced'] += row.get('amount_total', 0)
                        inv_seen[pdate].add(iid)
            elif base in ('invoice', 'accounting'):
                idate = row.get('invoice_date_raw')
                if not idate:
                    continue
                if base == 'accounting' and (idate < period_start or idate > period_end):
                    continue
                iid = row.get('invoice_id')
                if iid and iid not in inv_seen[idate]:
                    daily[idate]['invoiced'] += row.get('amount_total', 0)
                    inv_seen[idate].add(iid)
                if row.get('_has_payment'):
                    daily[idate]['paid'] += row.get('amount_applied', 0)

        labels = sorted(daily.keys())
        if scope == 'period':
            labels = [d for d in labels if period_start <= d <= period_end]

        if base == 'payment':
            inv_name = _('Facturas cobradas')
            paid_name = _('Pagos registrados')
        elif base == 'accounting':
            inv_name = _('Facturado (fecha factura)')
            paid_name = _('Pagado (fecha factura)')
        else:
            inv_name = _('Facturado')
            paid_name = _('Pagado')

        return {
            'labels': labels,
            'base': base,
            'scope': scope,
            'series': [
                {'key': 'invoiced', 'name': inv_name, 'data': [daily[d]['invoiced'] for d in labels]},
                {'key': 'paid', 'name': paid_name, 'data': [daily[d]['paid'] for d in labels]},
            ],
            'drilldown': [
                {
                    'filter': {
                        'date_from': d,
                        'date_to': d,
                        'payment_period': 'custom',
                        **({'invoice_date_from': d, 'invoice_date_to': d} if base != 'payment' else {}),
                    },
                    'tab': 'detail',
                }
                for d in labels
            ],
        }

    @api.model
    def _build_charts(self, rows, parsed):
        timeline_payment = self._build_timeline_data(rows, parsed, 'payment', 'period')
        timeline_invoice = self._build_timeline_data(rows, parsed, 'invoice', 'period')
        timeline_accounting = self._build_timeline_data(rows, parsed, 'accounting', 'period')
        timeline_historical = self._build_timeline_data(rows, parsed, 'payment', 'historical')
        # Status distribution
        status_counts = defaultdict(float)
        for row in rows:
            status_counts[row.get('payment_state') or 'unknown'] += row.get('balance_pending', 0) or row.get('amount_total', 0)
        # By advisor
        advisor_data = defaultdict(lambda: {
            'invoiced': 0.0, 'paid': 0.0, 'pending': 0.0,
            'invoice_count': 0, 'user_id': False, 'collection_days': [],
        })
        inv_adv = set()
        for row in rows:
            key = row.get('advisor') or _('Sin asesor')
            uid = row.get('user_id')
            iid = row.get('invoice_id')
            if iid and (key, iid) not in inv_adv:
                advisor_data[key]['invoiced'] += row.get('amount_total', 0)
                advisor_data[key]['pending'] += row.get('balance_pending', 0)
                advisor_data[key]['invoice_count'] += 1
                advisor_data[key]['user_id'] = uid
                inv_adv.add((key, iid))
            if row.get('_has_payment'):
                advisor_data[key]['paid'] += row.get('amount_applied', 0)
                if isinstance(row.get('days_invoice_to_payment'), int):
                    advisor_data[key]['collection_days'].append(row['days_invoice_to_payment'])
        advisor_items = []
        for name, data in advisor_data.items():
            inv = data['invoiced']
            paid = data['paid']
            avg_days = (
                sum(data['collection_days']) / len(data['collection_days'])
                if data['collection_days'] else 0
            )
            advisor_items.append({
                'label': name,
                'full_label': name,
                'metrics': {
                    'invoiced': inv,
                    'paid': paid,
                    'pending': data['pending'],
                    'invoice_count': data['invoice_count'],
                    'recovery_pct': (paid / inv * 100) if inv else 0,
                    'avg_collection_days': avg_days,
                },
                'meta': {'invoice_count': data['invoice_count'], 'doc_count': data['invoice_count']},
                'drilldown': {
                    'filter': {'user_ids': [data['user_id']]} if data.get('user_id') else {},
                    'tab': 'detail',
                },
            })
        advisor_ranking = self._top_n_chart_series(advisor_items, 'paid', 10)
        # Top clients
        client_data = defaultdict(lambda: {
            'invoiced': 0.0, 'paid': 0.0, 'pending': 0.0,
            'partner_id': False, 'invoice_count': 0, 'collection_days': [],
        })
        inv_cli = set()
        for row in rows:
            key = row.get('customer') or _('Sin cliente')
            pid = row.get('partner_id')
            iid = row.get('invoice_id')
            if iid and (key, iid) not in inv_cli:
                client_data[key]['invoiced'] += row.get('amount_total', 0)
                client_data[key]['pending'] += row.get('balance_pending', 0)
                client_data[key]['invoice_count'] += 1
                client_data[key]['partner_id'] = pid
                inv_cli.add((key, iid))
            if row.get('_has_payment'):
                client_data[key]['paid'] += row.get('amount_applied', 0)
                if isinstance(row.get('days_invoice_to_payment'), int):
                    client_data[key]['collection_days'].append(row['days_invoice_to_payment'])
        client_items = []
        for name, data in client_data.items():
            inv = data['invoiced']
            paid = data['paid']
            avg_days = (
                sum(data['collection_days']) / len(data['collection_days'])
                if data['collection_days'] else 0
            )
            client_items.append({
                'label': name if len(name) <= 40 else name[:37] + '…',
                'full_label': name,
                'metrics': {
                    'invoiced': inv,
                    'paid': paid,
                    'pending': data['pending'],
                    'invoice_count': data['invoice_count'],
                    'recovery_pct': (paid / inv * 100) if inv else 0,
                    'avg_collection_days': avg_days,
                },
                'meta': {
                    'invoice_count': data['invoice_count'],
                    'doc_count': data['invoice_count'],
                    'full_name': name,
                },
                'drilldown': {
                    'filter': {'partner_ids': [data['partner_id']]} if data.get('partner_id') else {},
                    'tab': 'detail',
                },
            })
        client_ranking = self._top_n_chart_series(client_items, 'paid', 10)
        # Banks
        bank_data = defaultdict(lambda: {'amount': 0.0, 'journal_id': False, 'count': 0})
        for row in rows:
            if row.get('_has_payment'):
                bkey = row.get('bank') or _('Sin banco')
                bank_data[bkey]['amount'] += row.get('amount_applied', 0)
                bank_data[bkey]['journal_id'] = row.get('journal_id')
                bank_data[bkey]['count'] += 1
        bank_items = [{
            'label': k,
            'amount': v['amount'],
            'drilldown': {
                'filter': {'journal_ids': [v['journal_id']]} if v.get('journal_id') else {},
                'tab': 'detail',
            },
        } for k, v in bank_data.items()]
        # Categories
        categ_data = defaultdict(float)
        categ_counts = defaultdict(int)
        for row in rows:
            for cat in (row.get('product_categories') or '').split(','):
                cat = cat.strip()
                if cat:
                    categ_data[cat] += row.get('amount_total', 0)
                    categ_counts[cat] += 1
        categ_items = [{
            'label': k,
            'amount': v,
            'drilldown': {'filter': {}, 'tab': 'detail'},
        } for k, v in categ_data.items()]

        return {
            'timeline': timeline_payment,
            'timeline_invoice': timeline_invoice,
            'timeline_accounting': timeline_accounting,
            'timeline_historical': timeline_historical,
            'status_distribution': {
                'labels': list(status_counts.keys()),
                'data': list(status_counts.values()),
                'drilldown': [
                    {'filter': {'payment_state': st}, 'tab': 'detail'}
                    for st in status_counts.keys()
                ],
            },
            'advisor_ranking': advisor_ranking,
            'client_ranking': client_ranking,
            'bank_distribution': self._pie_top_n(bank_items, 6),
            'category_distribution': self._pie_top_n(categ_items, 6),
        }

    @api.model
    def _build_aging(self, rows, parsed=None):
        buckets = {
            'current': {'label': _('No vencido'), 'amount': 0.0, 'count': 0},
            '1_30': {'label': _('1-30 días'), 'amount': 0.0, 'count': 0},
            '31_60': {'label': _('31-60 días'), 'amount': 0.0, 'count': 0},
            '61_90': {'label': _('61-90 días'), 'amount': 0.0, 'count': 0},
            '90_plus': {'label': _('+90 días'), 'amount': 0.0, 'count': 0},
        }
        seen_inv = set()
        overdue_clients = defaultdict(float)
        overdue_invoices = []
        upcoming_days = (parsed or {}).get('upcoming_days', 7)
        today = self._today()
        for row in rows:
            iid = row.get('invoice_id')
            if not iid or iid in seen_inv:
                continue
            pending = row.get('balance_pending', 0)
            if pending <= 0:
                continue
            seen_inv.add(iid)
            overdue = row.get('days_overdue', 0) or 0
            if overdue <= 0:
                buckets['current']['amount'] += pending
                buckets['current']['count'] += 1
            elif overdue <= 30:
                buckets['1_30']['amount'] += pending
                buckets['1_30']['count'] += 1
            elif overdue <= 60:
                buckets['31_60']['amount'] += pending
                buckets['31_60']['count'] += 1
            elif overdue <= 90:
                buckets['61_90']['amount'] += pending
                buckets['61_90']['count'] += 1
            else:
                buckets['90_plus']['amount'] += pending
                buckets['90_plus']['count'] += 1
            pub = self._public_row(row)
            if row.get('is_overdue'):
                overdue_clients[row.get('customer', '')] += pending
                overdue_invoices.append(pub)
            elif row.get('due_date_raw'):
                due = fields.Date.from_string(row['due_date_raw'])
                if today <= due <= today + timedelta(days=upcoming_days):
                    pub['_upcoming'] = True
                    overdue_invoices.append(pub)
        total_pending = sum(b['amount'] for b in buckets.values()) or 1
        for bk in buckets:
            buckets[bk]['pct'] = round(buckets[bk]['amount'] / total_pending * 100, 1)
        top_overdue_clients = sorted(
            overdue_clients.items(), key=lambda x: x[1], reverse=True
        )[:10]
        mode = (parsed or {}).get('overdue_filter_mode', 'all_balance')
        if mode == 'overdue_only':
            filtered = [r for r in overdue_invoices if (r.get('days_overdue') or 0) > 0]
        elif mode == 'upcoming_due':
            filtered = [r for r in overdue_invoices if r.get('_upcoming')]
        else:
            filtered = [self._public_row(r) for r in rows
                        if r.get('invoice_id') and r.get('balance_pending', 0) > 0]
            seen = set()
            dedup = []
            for r in filtered:
                iid = r.get('invoice_id')
                if iid not in seen:
                    seen.add(iid)
                    dedup.append(r)
            filtered = dedup
        return {
            'buckets': buckets,
            'total_pending': total_pending,
            'top_overdue_clients': [
                {'name': n, 'amount': a} for n, a in top_overdue_clients
            ],
            'overdue_invoices': sorted(
                filtered, key=lambda r: (r.get('collection_priority_score', 0), r.get('days_overdue', 0)),
                reverse=True,
            ),
            'filter_mode': mode,
        }

    @api.model
    def _insight_action_filter(self, filters=None, tab=None):
        action = {'type': 'filter', 'filters': filters or {}}
        if tab:
            action['tab'] = tab
        return action

    @api.model
    def _build_insights(self, rows, kpis, parsed):
        company = parsed['company']
        insights = []
        aging = self._build_aging(rows)
        charts = self._build_charts(rows, parsed)
        total_pending = sum(b['amount'] for b in aging['buckets'].values())
        b90 = aging['buckets']['90_plus']['amount']
        if total_pending > 0 and b90 > 0:
            pct = round(b90 / total_pending * 100, 1)
            insights.append({
                'text': _('El %(pct).1f%% del saldo pendiente supera los 90 días.', pct=pct),
                'action': self._insight_action_filter({'overdue_only': True}, 'overdue'),
                'tone': 'danger',
            })
        adv = charts.get('advisor_ranking', {})
        paid_series = adv.get('metrics', {}).get('paid') or adv.get('paid') or []
        if adv.get('labels') and paid_series:
            total_paid = sum(paid_series) or 1
            idx = paid_series.index(max(paid_series))
            pct = round(paid_series[idx] / total_paid * 100, 1)
            drill = adv.get('drilldown', [{}])[idx] if idx < len(adv.get('drilldown', [])) else {}
            insights.append({
                'text': _('El asesor %(name)s concentra el %(pct).1f%% de los cobros del período.',
                          name=adv['labels'][idx], pct=pct),
                'action': self._insight_action_filter(drill.get('filter', {}), 'detail'),
                'tone': 'info',
            })
        if aging['top_overdue_clients']:
            top = aging['top_overdue_clients'][0]
            insights.append({
                'text': _('El cliente %(name)s presenta el mayor saldo vencido: %(amt)s.',
                          name=top['name'], amt=self._fmt_money(top['amount'], company)),
                'action': self._insight_action_filter({'overdue_only': True}, 'overdue'),
                'tone': 'warning',
            })
        for card in kpis.get('cards', []):
            if card['key'] == 'recovery_pct' and card.get('delta') and card['delta'].get('pp') is not None:
                pp = card['delta']['pp']
                insights.append({
                    'text': _('La recuperación varió %(pp).1f puntos porcentuales frente al período anterior.', pp=pp),
                    'action': self._insight_action_filter({}, 'summary'),
                    'tone': 'info' if pp >= 0 else 'warning',
                })
                break
        banks = charts.get('bank_distribution', {})
        if banks.get('labels') and banks.get('data'):
            idx = banks['data'].index(max(banks['data']))
            amt = banks['data'][idx]
            drill = banks.get('drilldown', [{}])[idx] if idx < len(banks.get('drilldown', [])) else {}
            insights.append({
                'text': _('%(name)s procesó el mayor volumen de pagos: %(amt)s.',
                          name=banks['labels'][idx], amt=self._fmt_money(amt, company)),
                'action': self._insight_action_filter(drill.get('filter', {}), 'detail'),
                'tone': 'info',
            })
        return insights[:6]

    @api.model
    def _build_insights_from_charts(self, charts, kpis, aging):
        """Hallazgos simplificados cuando se usa modo SQL."""
        company = self.env.company
        insights = []
        total_pending = sum(b.get('amount', 0) for b in aging.get('buckets', {}).values())
        b90 = aging.get('buckets', {}).get('90_plus', {}).get('amount', 0)
        if total_pending > 0 and b90 > 0:
            pct = round(b90 / total_pending * 100, 1)
            insights.append({
                'text': _('El %(pct).1f%% del saldo pendiente supera los 90 días.', pct=pct),
                'action': self._insight_action_filter({'overdue_only': True}, 'overdue'),
                'tone': 'danger',
            })
        adv = charts.get('advisor_ranking', {})
        paid_series = adv.get('metrics', {}).get('paid') or adv.get('paid') or []
        if adv.get('labels') and paid_series:
            total_paid = sum(paid_series) or 1
            idx = paid_series.index(max(paid_series))
            pct = round(paid_series[idx] / total_paid * 100, 1)
            drill = adv.get('drilldown', [{}])[idx] if idx < len(adv.get('drilldown', [])) else {}
            insights.append({
                'text': _('El asesor %(name)s concentra el %(pct).1f%% de los cobros del período.',
                          name=adv['labels'][idx], pct=pct),
                'action': self._insight_action_filter(drill.get('filter', {}), 'detail'),
                'tone': 'info',
            })
        recovery = round(kpis.get('recovery_index', 0) or 0, 1)
        insights.append({
            'text': _('Índice de recuperación del período: %(pct).1f%%.', pct=recovery),
            'action': self._insight_action_filter({}, 'summary'),
            'tone': 'info' if recovery >= 65 else 'warning',
        })
        return insights[:6]

    @api.model
    def _format_period_label(self, parsed):
        parts = [
            _('Pagos: %(d1)s — %(d2)s') % {
                'd1': fields.Date.to_string(parsed['date_from']),
                'd2': fields.Date.to_string(parsed['date_to']),
            },
        ]
        if parsed.get('invoice_date_from') or parsed.get('invoice_date_to'):
            inv_from = parsed['invoice_date_from'] or parsed['date_from']
            inv_to = parsed['invoice_date_to'] or parsed['date_to']
            parts.append(_('Facturas: %(d1)s — %(d2)s') % {
                'd1': fields.Date.to_string(inv_from),
                'd2': fields.Date.to_string(inv_to),
            })
        return ' · '.join(parts)

    @api.model
    def _build_header(self, parsed, row_count, duration_ms, sql_mode=False):
        header = {
            'title': _('Facturas y pagos'),
            'subtitle': _('Análisis integral de facturación, cobranza y comportamiento de pago'),
            'company_name': parsed['company'].name,
            'period_label': self._format_period_label(parsed),
            'filters_by_payment_date': not (
                parsed.get('invoice_date_from') or parsed.get('invoice_date_to')
            ),
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'row_count': row_count,
            'duration_ms': duration_ms,
            'sql_mode': sql_mode,
            'has_filters': bool(
                parsed['branch_ids'] or parsed['user_ids'] or parsed['partner_ids']
                or parsed['journal_ids'] or parsed['categ_ids']
                or parsed['payment_state'] != 'all'
                or parsed['overdue_only'] or parsed['search']
            ),
        }
        return header

    @api.model
    def _filters_summary(self, parsed):
        return {
            'date_from': fields.Date.to_string(parsed['date_from']),
            'date_to': fields.Date.to_string(parsed['date_to']),
            'payment_state': parsed['payment_state'],
            'view_mode': parsed['view_mode'],
            'compare_mode': parsed['compare_mode'],
        }

    @api.model
    def _paginate_table(self, rows, page, page_size, sort_by, sort_dir, group_by):
        page = max(1, int(page or 1))
        page_size = min(500, max(1, int(page_size or 50)))
        sort_by = sort_by if sort_by in TABLE_SORT_FIELDS else 'payment_date_raw'
        reverse = (sort_dir or 'desc') == 'desc'

        def sort_key(row):
            val = row.get(sort_by)
            if val in (False, None, ''):
                return ''
            return val

        sorted_rows = sorted(rows, key=sort_key, reverse=reverse)
        total = len(sorted_rows)
        start = (page - 1) * page_size
        page_rows = sorted_rows[start:start + page_size]

        # Global totals from ALL filtered rows (not just page)
        inv_map = self._unique_invoice_totals(sorted_rows)
        pending_map = {}
        for r in sorted_rows:
            iid = r.get('invoice_id')
            if iid:
                pending_map[iid] = r.get('balance_pending', 0)

        groups = None
        if group_by and group_by in GROUP_BY_FIELDS:
            grouped = defaultdict(list)
            for row in sorted_rows:
                grouped[self._group_key(row, group_by)].append(row)
            groups = []
            for name, grows in grouped.items():
                ginvs = self._unique_invoice_totals(grows)
                inv_ids = {r.get('invoice_id') for r in grows if r.get('invoice_id')}
                groups.append({
                    'name': name,
                    'count': len(grows),
                    'invoice_count': len(inv_ids),
                    'payment_count': sum(1 for r in grows if r.get('_has_payment')),
                    'amount_total': sum(ginvs.values()),
                    'amount_applied': sum(r.get('amount_applied', 0) for r in grows if r.get('_has_payment')),
                    'balance_pending': sum(
                        {r.get('invoice_id'): r.get('balance_pending', 0) for r in grows}.values()
                    ),
                    'rows': [self._public_row(r) for r in grows[:50]],
                    'collapsed': False,
                })

        overdue_vals = [
            r.get('days_overdue', 0) for r in sorted_rows
            if r.get('days_overdue', 0) > 0
        ]
        inv_ids_all = {r.get('invoice_id') for r in sorted_rows if r.get('invoice_id')}
        totals = {
            'amount_untaxed': sum(r.get('amount_untaxed', 0) for r in sorted_rows),
            'amount_tax': sum(r.get('amount_tax', 0) for r in sorted_rows),
            'amount_total': sum(inv_map.values()),
            'amount_applied': sum(r.get('amount_applied', 0) for r in sorted_rows if r.get('_has_payment')),
            'balance_pending': sum(pending_map.values()),
            'invoice_count': len(inv_ids_all),
            'payment_count': sum(1 for r in sorted_rows if r.get('_has_payment')),
            'avg_days_overdue': round(sum(overdue_vals) / len(overdue_vals), 1) if overdue_vals else None,
        }

        return {
            'rows': [self._public_row(r) for r in page_rows],
            'page': page,
            'page_size': page_size,
            'total_rows': total,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            'totals': totals,
            'meta': self._table_meta(sorted_rows),
            'groups': groups,
            'sort_by': sort_by,
            'sort_dir': sort_dir,
        }

    @api.model
    def _build_timeline(self, invoice, payments):
        events = []
        if invoice.invoice_date:
            events.append({
                'date': fields.Date.to_string(invoice.invoice_date),
                'label': _('Factura emitida'),
                'type': 'invoice',
            })
        if invoice.invoice_date_due:
            events.append({
                'date': fields.Date.to_string(invoice.invoice_date_due),
                'label': _('Fecha de vencimiento'),
                'type': 'due',
            })
        for pay in payments:
            events.append({
                'date': pay.get('date'),
                'label': _('Pago %(name)s', name=pay.get('name', '')),
                'amount': pay.get('amount'),
                'type': 'payment',
            })
        return sorted(events, key=lambda e: e.get('date') or '')
