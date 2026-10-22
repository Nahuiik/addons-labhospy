# -*- coding: utf-8 -*-
"""Servicio analítico del Dashboard de Compras Premium."""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

PO_CONFIRMED = ('purchase',)
PO_OPEN = ('draft', 'sent', 'to approve', 'purchase')
PERIOD_PRESETS = (
    'today', 'yesterday', 'this_week', 'this_month', 'this_quarter',
    'this_year', 'last_30', 'last_90', 'custom',
)
COMPARE_MODES = ('none', 'previous', 'yoy')

KPI_DEFS = (
    ('total_purchased', _('Total Comprado'), 'currency', 'fa-shopping-cart', 'up', 'primary'),
    ('po_count', _('Cantidad de OC'), 'number', 'fa-file-text-o', 'up', 'primary'),
    ('pending_approval', _('Pendiente de Aprobar'), 'currency', 'fa-clock-o', 'down', 'primary'),
    ('pending_receive', _('Pendiente de Recibir'), 'currency', 'fa-truck', 'down', 'primary'),
    ('pending_invoice', _('Pendiente de Facturar'), 'currency', 'fa-file-o', 'down', 'primary'),
    ('pending_amount', _('Monto Pendiente'), 'currency', 'fa-exclamation-circle', 'down', 'primary'),
    ('savings_generated', _('Ahorro Generado'), 'currency', 'fa-piggy-bank', 'up', 'secondary'),
    ('avg_purchase_price', _('Precio Promedio Compra'), 'currency', 'fa-tag', 'neutral', 'secondary'),
    ('avg_po_cycle_days', _('Tiempo Promedio de Compra'), 'days', 'fa-hourglass-half', 'down', 'secondary'),
    ('avg_lead_time_days', _('Lead Time Promedio'), 'days', 'fa-road', 'down', 'secondary'),
    ('urgent_orders', _('Órdenes Urgentes'), 'number', 'fa-bolt', 'down', 'secondary'),
    ('active_vendors', _('Proveedores Activos'), 'number', 'fa-users', 'up', 'secondary'),
)


class PurchaseDashboardService(models.AbstractModel):
    _name = 'purchase.dashboard.service'
    _description = 'Purchase Dashboard Premium Data Service'

    @api.model
    def _check_dashboard_access(self):
        if not self.env.user.has_group('gn_purchase_dashboard.group_purchase_dashboard_user'):
            raise AccessError(_('No tiene permiso para acceder al Dashboard de Compras.'))

    # ------------------------------------------------------------------
    # Public RPC
    # ------------------------------------------------------------------

    @api.model
    def get_filter_options(self):
        self._check_dashboard_access()
        company = self.env.company
        branches = self.env['res.branch'].search([('company_id', 'in', company.ids)], order='name')
        buyers = self.env['res.users'].search([
            ('share', '=', False), ('company_ids', 'in', company.ids),
        ], order='name', limit=200)
        vendors = self.env['res.partner'].search([
            ('supplier_rank', '>', 0),
        ], order='name', limit=300)
        warehouses = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id),
        ], order='name')
        categories = self.env['product.category'].search([], order='complete_name', limit=500)
        projects = []
        if 'account.analytic.account' in self.env:
            projects = self.env['account.analytic.account'].search([
                ('company_id', 'in', company.ids),
            ], order='name', limit=200)
        tags = self.env['res.partner.category'].search([], order='name', limit=100)
        return {
            'company_id': company.id,
            'company_name': company.name,
            'multi_company': len(self.env.companies) > 1,
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
            'currency_id': company.currency_id.id,
            'currency_symbol': company.currency_id.symbol,
            'period_presets': [
                {'id': 'today', 'label': _('Hoy')},
                {'id': 'yesterday', 'label': _('Ayer')},
                {'id': 'this_week', 'label': _('Semana actual')},
                {'id': 'this_month', 'label': _('Mes actual')},
                {'id': 'this_quarter', 'label': _('Trimestre actual')},
                {'id': 'this_year', 'label': _('Año actual')},
                {'id': 'last_30', 'label': _('Últimos 30 días')},
                {'id': 'last_90', 'label': _('Últimos 90 días')},
                {'id': 'custom', 'label': _('Personalizado')},
            ],
            'compare_modes': [
                {'id': 'none', 'label': _('Sin comparación')},
                {'id': 'previous', 'label': _('Período anterior')},
                {'id': 'yoy', 'label': _('Mismo período año anterior')},
            ],
            'po_states': [
                {'id': 'draft', 'label': _('Borrador')},
                {'id': 'sent', 'label': _('Enviada')},
                {'id': 'to approve', 'label': _('Por aprobar')},
                {'id': 'purchase', 'label': _('Confirmada')},
                {'id': 'cancel', 'label': _('Cancelada')},
            ],
            'branches': [{'id': b.id, 'name': b.name} for b in branches],
            'buyers': [{'id': u.id, 'name': u.name} for u in buyers],
            'vendors': [{'id': v.id, 'name': v.display_name} for v in vendors],
            'warehouses': [{'id': w.id, 'name': w.name} for w in warehouses],
            'categories': [{'id': c.id, 'name': c.display_name} for c in categories],
            'projects': [{'id': p.id, 'name': p.display_name} for p in projects],
            'tags': [{'id': t.id, 'name': t.name} for t in tags],
            'price_alert_threshold': 10,
        }

    @api.model
    def get_dashboard_init(self, filters=None):
        self._check_dashboard_access()
        t0 = time.time()
        cache = {}
        parsed = self._parse_filters(filters or {})
        compare_parsed = self._comparison_parsed(parsed)
        current = self._compute_metrics(parsed, cache)
        previous = self._compute_metrics(compare_parsed, cache) if compare_parsed else {}
        kpis = self._build_kpi_cards(current, previous, parsed, cache)
        duration_ms = int((time.time() - t0) * 1000)
        advanced = self._build_summary_advanced(parsed, cache, current, previous)
        return {
            'core': {
                'success': True,
                'filters': self._filters_payload(parsed),
                'currency': self._currency_payload(parsed),
                'header': self._build_header(parsed, duration_ms),
                'kpis': kpis,
                'metadata': {
                    'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
                    'duration_ms': duration_ms,
                },
            },
            'advanced': advanced,
            'duration_ms': duration_ms,
        }

    @api.model
    def get_dashboard_widgets(self, filters=None, keys=None):
        self._check_dashboard_access()
        keys = keys or []
        parsed = self._parse_filters(filters or {})
        cache = {}
        widgets = {}
        builders = self._widget_builders()
        for key in keys:
            fn = builders.get(key)
            if fn:
                widgets[key] = fn(parsed, cache)
        return {'success': True, 'widgets': widgets}

    @api.model
    def get_drilldown_action(self, metric, extra_domain=None, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        domain = self._po_base_domain(parsed)
        if extra_domain:
            domain = Domain.AND([domain, extra_domain])
        metric_domains = {
            'total_purchased': [('state', 'in', list(PO_CONFIRMED))],
            'pending_approval': [('state', '=', 'to approve')],
            'pending_receive': [('state', '=', 'purchase'), ('invoice_status', 'in', ('no', 'to invoice'))],
            'pending_invoice': [('invoice_status', '=', 'to invoice')],
            'urgent_orders': [('priority', 'in', ('1', '2', '3'))],
        }
        if metric in metric_domains:
            domain = Domain.AND([domain, metric_domains[metric]])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Órdenes de compra'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    @api.model
    def _parse_filters(self, filters):
        company_id = filters.get('company_id') or self.env.company.id
        company = self.env['res.company'].browse(company_id)
        if company.id not in self.env.companies.ids:
            company = self.env.company
        period = filters.get('period') or 'this_month'
        date_from, date_to = self._period_dates(period, filters)
        return {
            'company': company,
            'period': period,
            'compare_mode': filters.get('compare_mode') or 'previous',
            'date_from': date_from,
            'date_to': date_to,
            'branch_id': filters.get('branch_id') or False,
            'buyer_id': filters.get('buyer_id') or False,
            'vendor_id': filters.get('vendor_id') or False,
            'category_id': filters.get('category_id') or False,
            'warehouse_id': filters.get('warehouse_id') or False,
            'po_state': filters.get('po_state') or False,
            'project_id': filters.get('project_id') or False,
            'tag_id': filters.get('tag_id') or False,
        }

    @api.model
    def _period_dates(self, period, filters):
        today = fields.Date.context_today(self)
        if period == 'custom' and filters.get('date_from') and filters.get('date_to'):
            return filters['date_from'], filters['date_to']
        mapping = {
            'today': (today, today),
            'yesterday': (today - timedelta(days=1),) * 2,
            'this_week': (today - timedelta(days=today.weekday()), today),
            'this_month': (today.replace(day=1), today),
            'this_quarter': self._quarter_start(today, today),
            'this_year': (today.replace(month=1, day=1), today),
            'last_30': (today - timedelta(days=29), today),
            'last_90': (today - timedelta(days=89), today),
        }
        return mapping.get(period, mapping['this_month'])

    @api.model
    def _quarter_start(self, today, end):
        q = (today.month - 1) // 3
        start = today.replace(month=q * 3 + 1, day=1)
        return start, end

    @api.model
    def _comparison_parsed(self, parsed):
        if parsed.get('compare_mode') == 'none':
            return None
        days = (parsed['date_to'] - parsed['date_from']).days + 1
        prev_end = parsed['date_from'] - timedelta(days=1)
        if parsed.get('compare_mode') == 'yoy':
            try:
                prev_start = parsed['date_from'].replace(year=parsed['date_from'].year - 1)
                prev_end = parsed['date_to'].replace(year=parsed['date_to'].year - 1)
            except ValueError:
                prev_start = parsed['date_from'] - timedelta(days=365)
                prev_end = parsed['date_to'] - timedelta(days=365)
        else:
            prev_start = prev_end - timedelta(days=days - 1)
        cp = dict(parsed)
        cp['date_from'] = prev_start
        cp['date_to'] = prev_end
        return cp

    @api.model
    def _po_base_domain(self, parsed):
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('date_order', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
            ('date_order', '<=', fields.Datetime.to_datetime(parsed['date_to']) + timedelta(days=1)),
        ]
        if parsed.get('branch_id') and 'branch_id' in self.env['purchase.order']._fields:
            domain.append(('branch_id', '=', parsed['branch_id']))
        if parsed.get('buyer_id'):
            domain.append(('user_id', '=', parsed['buyer_id']))
        if parsed.get('vendor_id'):
            domain.append(('partner_id', '=', parsed['vendor_id']))
        if parsed.get('po_state'):
            domain.append(('state', '=', parsed['po_state']))
        if parsed.get('warehouse_id'):
            domain.append(('picking_type_id.warehouse_id', '=', parsed['warehouse_id']))
        if parsed.get('category_id'):
            domain.append(('order_line.product_id.categ_id', 'child_of', parsed['category_id']))
        if parsed.get('tag_id'):
            domain.append(('partner_id.category_id', 'in', [parsed['tag_id']]))
        return domain

    @api.model
    def _po_matches_project(self, po, project_id):
        if not project_id:
            return True
        pid = str(project_id)
        for line in po.order_line.filtered(lambda l: not l.display_type):
            dist = line.analytic_distribution or {}
            if pid in dist or project_id in dist:
                return True
        return False

    @api.model
    def _fetch_pos(self, parsed, cache, extra_domain=None):
        key = ('pos', tuple(sorted((k, v if k != 'company' else v.id) for k, v in parsed.items())), str(extra_domain))
        if key not in cache:
            domain = self._po_base_domain(parsed)
            if extra_domain:
                domain = Domain.AND([domain, extra_domain])
            pos = self.env['purchase.order'].search(domain)
            if parsed.get('project_id'):
                pos = pos.filtered(lambda p: self._po_matches_project(p, parsed['project_id']))
            cache[key] = pos
        return cache[key]

    @api.model
    def _convert_po_amount(self, po, company):
        amt = po.amount_total
        po_currency = po.currency_id
        company_currency = company.currency_id
        if po_currency == company_currency:
            return amt
        date = po.date_order.date() if po.date_order else fields.Date.context_today(self)
        return po_currency._convert(amt, company_currency, company, date)

    @api.model
    def _kpi_sparkline(self, parsed, cache, metric_key):
        """Serie histórica diaria del KPI en el período."""
        pos = self._fetch_pos(parsed, cache)
        buckets = defaultdict(float)
        for po in pos:
            if not po.date_order:
                continue
            day = po.date_order.strftime('%Y-%m-%d')
            if metric_key == 'total_purchased' and po.state in PO_CONFIRMED:
                buckets[day] += self._convert_po_amount(po, parsed['company'])
            elif metric_key == 'po_count' and po.state in PO_CONFIRMED:
                buckets[day] += 1
            elif metric_key == 'pending_approval' and po.state == 'to approve':
                buckets[day] += self._convert_po_amount(po, parsed['company'])
            elif metric_key == 'urgent_orders':
                urgent = po.priority and po.priority != '0'
                if urgent or (po.state in PO_CONFIRMED and po.date_planned and po.date_planned <= fields.Datetime.now()):
                    buckets[day] += 1
        labels = sorted(buckets.keys())
        return [buckets[d] for d in labels]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @api.model
    def _compute_metrics(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache)
        confirmed = pos.filtered(lambda p: p.state in PO_CONFIRMED)
        company = parsed['company']
        total = sum(self._convert_po_amount(p, company) for p in confirmed)
        pending_approval = pos.filtered(lambda p: p.state == 'to approve')
        pending_receive = confirmed.filtered(
            lambda p: any(
                l.product_qty > l.qty_received
                for l in p.order_line.filtered(lambda x: not x.display_type)
            )
        )
        pending_invoice = confirmed.filtered(lambda p: p.invoice_status == 'to invoice')
        pending_amt = sum(p.amount_total for p in pending_receive | pending_invoice)
        savings = 0.0
        qty_sum = 0.0
        price_weighted = 0.0
        cycle_days = []
        lead_days = []
        for po in confirmed:
            for line in po.order_line.filtered(lambda l: not l.display_type and l.product_id):
                std = line.product_id.standard_price or 0.0
                if std > line.price_unit:
                    savings += (std - line.price_unit) * line.product_qty
                qty_sum += line.product_qty
                price_weighted += line.price_unit * line.product_qty
            if po.date_approve and po.date_order:
                cycle_days.append((po.date_approve - po.date_order).days)
            if po.date_planned and po.date_order:
                lead_days.append((po.date_planned - po.date_order).days)
        urgent = pos.filtered(lambda p: p.priority and p.priority != '0')
        if not urgent:
            urgent = confirmed.filtered(
                lambda p: p.date_planned and p.date_planned <= fields.Datetime.now()
                and any(l.product_qty > l.qty_received for l in p.order_line if not l.display_type)
            )
        vendors = set(confirmed.mapped('partner_id').ids)
        return {
            'total_purchased': {'value': total},
            'po_count': {'value': len(confirmed)},
            'pending_approval': {'value': sum(p.amount_total for p in pending_approval)},
            'pending_receive': {'value': sum(p.amount_total for p in pending_receive)},
            'pending_invoice': {'value': sum(p.amount_total for p in pending_invoice)},
            'pending_amount': {'value': pending_amt},
            'savings_generated': {'value': max(savings, 0.0)},
            'avg_purchase_price': {'value': price_weighted / qty_sum if qty_sum else 0.0},
            'avg_po_cycle_days': {'value': sum(cycle_days) / len(cycle_days) if cycle_days else 0.0},
            'avg_lead_time_days': {'value': sum(lead_days) / len(lead_days) if lead_days else 0.0},
            'urgent_orders': {'value': len(urgent)},
            'active_vendors': {'value': len(vendors)},
        }

    @api.model
    def _variation_pct(self, current, previous):
        if not previous:
            return 0.0
        return ((current - previous) / abs(previous)) * 100.0

    @api.model
    def _build_kpi_cards(self, current, previous, parsed, cache=None):
        cache = cache or {}
        cards = []
        primary_keys = {k[0] for k in KPI_DEFS if k[5] == 'primary'}
        for key, label, fmt, icon, direction, tier in KPI_DEFS:
            val = current.get(key, {}).get('value', 0.0)
            prev = previous.get(key, {}).get('value', 0.0) if previous else 0.0
            var = self._variation_pct(val, prev) if previous else 0.0
            tone = 'neutral'
            if parsed.get('compare_mode') != 'none' and abs(var) >= 0.05:
                good = var > 0 if direction == 'up' else var < 0
                tone = 'success' if good else 'danger'
            semaphore = 'neutral'
            if tone == 'success':
                semaphore = 'good'
            elif tone == 'danger':
                semaphore = 'bad'
            elif direction == 'down' and val > 0 and key.startswith('pending'):
                semaphore = 'warn'
            sparkline = self._kpi_sparkline(parsed, cache, key) if cache is not None else []
            cards.append({
                'key': key,
                'label': label,
                'value': val,
                'format': fmt,
                'icon': icon,
                'direction': direction,
                'variation_pct': var,
                'semantic_tone': tone,
                'semaphore': semaphore,
                'sparkline': sparkline[-14:] if sparkline else [],
                'tooltip': _('%s en el período seleccionado', label),
                'metric': key,
                'has_data': True,
                'tier': tier,
            })
        return cards

    @api.model
    def _build_header(self, parsed, duration_ms):
        return {
            'title': _('Dashboard de Compras'),
            'subtitle': _('Análisis ejecutivo de procurement'),
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'duration_ms': duration_ms,
        }

    @api.model
    def _filters_payload(self, parsed):
        return {
            'period': parsed['period'],
            'compare_mode': parsed.get('compare_mode'),
            'date_from': str(parsed['date_from']),
            'date_to': str(parsed['date_to']),
        }

    @api.model
    def _currency_payload(self, parsed):
        c = parsed['company'].currency_id
        return {'id': c.id, 'symbol': c.symbol, 'name': c.name}
