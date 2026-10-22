# -*- coding: utf-8 -*-
"""Series temporales, sparklines reales y carga progresiva."""

import json
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.tools import float_round

SPARKLINE_DAYS_ALLOWED = (7, 30, 90, 365)

# Métricas con serie histórica real (basada en agregaciones SQL/ORM)
SERIES_METRICS = {
    'incoming_quantity', 'outgoing_quantity', 'stock_quantity',
    'receipts_today', 'deliveries_today', 'open_pickings',
    'overdue_deliveries', 'overdue_receipts', 'out_of_stock',
    'inventory_value', 'fill_rate', 'inventory_turnover',
    'days_of_inventory', 'backorders', 'pending_receipts',
    'awaiting_deliveries', 'reserved_quantity', 'available_quantity',
}


class InventoryDashboardTimeseries(models.AbstractModel):
    _inherit = 'inventory.dashboard.service'

    _TS_CACHE = {}
    _TS_TTL_SEC = 180

    @api.model
    def get_filter_options(self):
        opts = super().get_filter_options()
        opts['sparkline_days_presets'] = [
            {'id': 7, 'name': _('7 días')},
            {'id': 30, 'name': _('30 días')},
            {'id': 90, 'name': _('90 días')},
            {'id': 365, 'name': _('365 días')},
        ]
        return opts

    # ------------------------------------------------------------------
    # RPC progresivo
    # ------------------------------------------------------------------

    @api.model
    def get_dashboard_core(self, filters=None, sparkline_days=30):
        """Fase 1: header, health, KPIs con sparklines reales."""
        self._check_dashboard_access()
        sparkline_days = self._normalize_sparkline_days(sparkline_days)
        parsed = self._parse_filters(filters or {})
        prev = self._previous_parsed(parsed)
        current = self._compute_metrics(parsed)
        previous = self._compute_metrics(prev)
        return {
            'filters': self._filters_payload(parsed),
            'header': self._build_header(parsed),
            'health': self._build_health(parsed, current),
            'kpis': self._build_kpis_with_sparklines(
                parsed, current, previous, sparkline_days,
            ),
            'sparkline_days': sparkline_days,
            'updated_at': fields.Datetime.now().isoformat(),
        }

    @api.model
    def get_dashboard_widgets(self, filters=None, widget_keys=None):
        """Fase 2: gráficos, alertas, insights, paneles (independiente por widget)."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        current = self._compute_metrics(parsed)
        keys = widget_keys or [
            'charts', 'alerts', 'insights', 'recommendations',
            'activity', 'financial', 'quick_actions', 'hero_chart',
        ]
        out = {}
        if 'charts' in keys or 'hero_chart' in keys:
            charts = self._build_viz_catalog(parsed, current)
            out['charts'] = charts
            out['hero_chart'] = charts.get('inventory_trend') or charts.get('receipts_vs_deliveries')
        if 'alerts' in keys:
            out['alerts'] = self._build_alerts(parsed, current)
        if 'insights' in keys:
            out['insights'] = self._build_insights(parsed, current)
        if 'recommendations' in keys:
            out['recommendations'] = self._build_recommendations(parsed, current)
        if 'activity' in keys:
            out['activity_feed'] = self._build_activity_feed(parsed)
        if 'financial' in keys:
            out['financial_panel'] = self._build_financial_panel(parsed, current)
        if 'quick_actions' in keys:
            out['quick_actions'] = self._quick_actions()
        return out

    @api.model
    def get_dashboard_data(self, filters=None):
        """Compatibilidad: payload completo (usa carga en dos fases internamente)."""
        core = self.get_dashboard_core(filters, sparkline_days=30)
        widgets = self.get_dashboard_widgets(filters)
        parsed = self._parse_filters(filters or {})
        return {
            **core,
            **widgets,
            'tables': self._build_tables(parsed, filters or {}),
        }

    @api.model
    def get_kpi_sparkline(self, filters, metric_key, sparkline_days=30):
        """RPC puntual para refrescar sparkline de un KPI."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        sparkline_days = self._normalize_sparkline_days(sparkline_days)
        return self._sparkline_payload(parsed, metric_key, sparkline_days)

    @api.model
    def get_table_page_advanced(
        self, filters, table_key, page=1, page_size=25,
        search='', order='', column_filters=None, visible_columns=None,
    ):
        """Tabla avanzada con filtros por columna y ordenamiento."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        return self._table_page_advanced(
            parsed, table_key, page, page_size, search, order,
            column_filters or {}, visible_columns,
        )

    # ------------------------------------------------------------------
    # Sparklines
    # ------------------------------------------------------------------

    @api.model
    def _normalize_sparkline_days(self, days):
        days = int(days or 30)
        if days not in SPARKLINE_DAYS_ALLOWED:
            return 30
        return days

    @api.model
    def _ts_cache_key(self, parsed, metric, days):
        return json.dumps({
            'm': metric, 'd': days,
            'c': parsed['company'].id,
            'b': parsed.get('branch_id'),
            'w': parsed.get('warehouse_id'),
            'df': fields.Date.to_string(parsed['date_from']),
            'dt': fields.Date.to_string(parsed['date_to']),
        }, sort_keys=True)

    @api.model
    def _sparkline_buckets(self, end_date, days):
        """Buckets adaptativos: diario (≤30), semanal (≤90), mensual (365)."""
        buckets = []
        if days <= 30:
            for i in range(days - 1, -1, -1):
                d = end_date - timedelta(days=i)
                buckets.append((fields.Date.to_string(d), d, d))
        elif days <= 90:
            step = 7
            n = days // step
            for i in range(n - 1, -1, -1):
                b_end = end_date - timedelta(days=i * step)
                b_start = b_end - timedelta(days=step - 1)
                buckets.append((
                    f'{fields.Date.to_string(b_start)} — {fields.Date.to_string(b_end)}',
                    b_start, b_end,
                ))
        else:
            for i in range(11, -1, -1):
                month_start = (end_date.replace(day=1) - relativedelta(months=i))
                month_end = min(
                    end_date,
                    month_start + relativedelta(months=1) - timedelta(days=1),
                )
                buckets.append((
                    month_start.strftime('%b %Y'),
                    month_start, month_end,
                ))
        return buckets

    @api.model
    def _series_from_picking_count(self, parsed, sparkline_days, extra_domain=None):
        Picking = self.env['stock.picking']
        end = parsed['date_to']
        start = end - timedelta(days=sparkline_days - 1)
        sub = {**parsed, 'date_from': start, 'date_to': end}
        domain = self._picking_domain(sub, extra_domain or [])
        rows = Picking._read_group(
            domain=domain,
            groupby=['scheduled_date:day'],
            aggregates=['__count'],
            order='scheduled_date:day',
        )
        by_day = {}
        for day_val, cnt in rows:
            if day_val:
                by_day[fields.Date.to_string(day_val)] = int(cnt or 0)
        buckets = self._sparkline_buckets(end, sparkline_days)
        labels, values = [], []
        for label, d_from, d_to in buckets:
            if d_from == d_to:
                values.append(by_day.get(fields.Date.to_string(d_from), 0))
            else:
                total = sum(
                    by_day.get(fields.Date.to_string(d_from + timedelta(days=i)), 0)
                    for i in range((d_to - d_from).days + 1)
                )
                values.append(total)
            labels.append(label if isinstance(label, str) else fields.Date.to_string(label))
        return labels, values

    @api.model
    def _series_from_move_qty(self, parsed, sparkline_days, extra=None):
        MoveLine = self.env['stock.move.line']
        end = parsed['date_to']
        start = end - timedelta(days=sparkline_days - 1)
        sub = {**parsed, 'date_from': start, 'date_to': end}
        domain = self._move_line_domain(sub, extra or [])
        rows = MoveLine._read_group(
            domain=domain,
            groupby=['date:day'],
            aggregates=['quantity:sum'],
            order='date:day',
        )
        by_day = {}
        for day_val, qty in rows:
            if day_val:
                by_day[fields.Date.to_string(day_val)] = float(qty or 0)
        buckets = self._sparkline_buckets(end, sparkline_days)
        labels, values = [], []
        for label, d_from, d_to in buckets:
            if d_from == d_to:
                values.append(by_day.get(fields.Date.to_string(d_from), 0.0))
            else:
                total = sum(
                    by_day.get(fields.Date.to_string(d_from + timedelta(days=i)), 0.0)
                    for i in range((d_to - d_from).days + 1)
                )
                values.append(total)
            labels.append(label)
        return labels, values

    @api.model
    def _series_for_metric(self, parsed, metric_key, sparkline_days):
        cache_key = self._ts_cache_key(parsed, metric_key, sparkline_days)
        entry = self._TS_CACHE.get(cache_key)
        now = fields.Datetime.now()
        if entry and (now - entry['ts']).total_seconds() < self._TS_TTL_SEC:
            return entry['data']

        handlers = {
            'incoming_quantity': lambda: self._series_from_move_qty(
                parsed, sparkline_days,
                [('picking_id.picking_type_code', '=', 'incoming')],
            ),
            'outgoing_quantity': lambda: self._series_from_move_qty(
                parsed, sparkline_days,
                [('picking_id.picking_type_code', '=', 'outgoing')],
            ),
            'receipts_today': lambda: self._series_from_picking_count(
                parsed, sparkline_days, [('picking_type_code', '=', 'incoming')],
            ),
            'deliveries_today': lambda: self._series_from_picking_count(
                parsed, sparkline_days, [('picking_type_code', '=', 'outgoing')],
            ),
            'open_pickings': lambda: self._series_from_picking_count(parsed, sparkline_days),
            'overdue_deliveries': lambda: self._series_from_picking_count(
                parsed, sparkline_days, [
                    ('picking_type_code', '=', 'outgoing'),
                    ('state', 'not in', ('done', 'cancel')),
                ],
            ),
            'overdue_receipts': lambda: self._series_from_picking_count(
                parsed, sparkline_days, [
                    ('picking_type_code', '=', 'incoming'),
                    ('state', 'not in', ('done', 'cancel')),
                ],
            ),
            'awaiting_deliveries': lambda: self._series_from_picking_count(
                parsed, sparkline_days, [
                    ('picking_type_code', '=', 'outgoing'),
                    ('state', 'in', ('confirmed', 'assigned', 'waiting', 'partially_available')),
                ],
            ),
            'pending_receipts': lambda: self._series_from_picking_count(
                parsed, sparkline_days, [
                    ('picking_type_code', '=', 'incoming'),
                    ('state', 'in', ('confirmed', 'assigned', 'waiting', 'partially_available')),
                ],
            ),
            'backorders': lambda: self._series_from_picking_count(
                parsed, sparkline_days, [('backorder_id', '!=', False)],
            ),
        }
        handler = handlers.get(metric_key)
        if not handler:
            data = {'labels': [], 'values': [], 'insufficient': True}
        else:
            labels, values = handler()
            non_zero = sum(1 for v in values if v)
            data = {
                'labels': labels,
                'values': values,
                'insufficient': non_zero < 2,
            }
        self._TS_CACHE[cache_key] = {'ts': now, 'data': data}
        return data

    @api.model
    def _sparkline_payload(self, parsed, metric_key, sparkline_days):
        series = self._series_for_metric(parsed, metric_key, sparkline_days)
        if metric_key not in SERIES_METRICS:
            series = {'labels': [], 'values': [], 'insufficient': True}
        return series

    @api.model
    def _build_kpis_with_sparklines(self, parsed, current, previous, sparkline_days):
        items = []
        catalog = self._kpi_catalog()
        for key, meta in catalog.items():
            cur_val = self._metric_value(key, current)
            prev_val = self._metric_value(key, previous)
            var_abs = float_round(cur_val - prev_val, 2)
            var_pct = self._variation(cur_val, prev_val)
            spark = self._sparkline_payload(parsed, key, sparkline_days)
            items.append({
                'key': key,
                'label': meta['label'],
                'icon': meta['icon'],
                'tone': meta['tone'],
                'format': meta['format'],
                'metric': meta['metric'],
                'value': cur_val,
                'previous_value': prev_val,
                'variation_abs': var_abs,
                'variation_pct': var_pct,
                'count': current.get(key, {}).get('count', 0),
                'trend': 'up' if var_pct > 0.5 else ('down' if var_pct < -0.5 else 'flat'),
                'sparkline': spark.get('values', []),
                'sparkline_labels': spark.get('labels', []),
                'sparkline_insufficient': spark.get('insufficient', True),
                'sparkline_message': _('Historial insuficiente') if spark.get('insufficient') else '',
            })
        return items

    # ------------------------------------------------------------------
    # Tabla avanzada
    # ------------------------------------------------------------------

    @api.model
    def _table_page_advanced(
        self, parsed, table_key, page, page_size, search, order,
        column_filters, visible_columns,
    ):
        page_data = self._table_page(
            parsed, table_key, page, page_size, search, order,
            column_filters=column_filters or {},
        )
        columns = self._table_columns(table_key)
        if visible_columns:
            columns = [c for c in columns if c['key'] in visible_columns]
        page_data['columns'] = columns
        page_data['column_filters'] = column_filters or {}
        return page_data

    @api.model
    def _table_page(
        self, parsed, table_key, page, page_size, search='', order='',
        column_filters=None,
    ):
        """Paginación con filtros por columna en dominio ORM."""
        column_filters = column_filters or {}
        cf = {k: (v or '').strip() for k, v in column_filters.items() if (v or '').strip()}
        page = max(1, int(page or 1))
        page_size = min(100, max(5, int(page_size or 10)))
        offset = (page - 1) * page_size
        rows = []
        total = 0

        if table_key == 'out_of_stock':
            domain = self._product_domain(parsed, [('qty_available', '<=', 0)])
            if search:
                domain.append(('name', 'ilike', search))
            if cf.get('name'):
                domain.append(('name', 'ilike', cf['name']))
            Product = self.env['product.product']
            total = Product.search_count(domain)
            for p in Product.search(domain, offset=offset, limit=page_size, order=order or 'name'):
                rows.append({
                    'id': p.id, 'name': p.display_name,
                    'qty': p.qty_available, 'model': 'product.product',
                })
        elif table_key == 'top_selling':
            MoveLine = self.env['stock.move.line']
            domain = self._move_line_domain(parsed, [
                ('location_dest_id.usage', 'not in', ('internal', 'transit')),
            ])
            if cf.get('name'):
                domain.append(('product_id.name', 'ilike', cf['name']))
            grouped = MoveLine._read_group(
                domain=domain, groupby=['product_id'],
                aggregates=['quantity:sum'], order='quantity:sum desc',
            )
            total = len(grouped)
            slice_rows = grouped[offset:offset + page_size]
            for product, qty in slice_rows:
                if product:
                    rows.append({
                        'id': product.id, 'name': product.display_name,
                        'qty': qty, 'model': 'product.product',
                    })
        elif table_key == 'receipts':
            domain = self._picking_domain(parsed, [('picking_type_code', '=', 'incoming')])
            if search:
                domain.append(('name', 'ilike', search))
            if cf.get('name'):
                domain.append(('name', 'ilike', cf['name']))
            if cf.get('partner'):
                domain.append(('partner_id.name', 'ilike', cf['partner']))
            if cf.get('state'):
                domain.append(('state', 'ilike', cf['state']))
            Picking = self.env['stock.picking']
            total = Picking.search_count(domain)
            for p in Picking.search(domain, offset=offset, limit=page_size, order=order or 'scheduled_date desc'):
                rows.append({
                    'id': p.id, 'name': p.name,
                    'partner': p.partner_id.display_name if p.partner_id else '',
                    'date': fields.Datetime.to_string(p.scheduled_date) if p.scheduled_date else '',
                    'state': p.state, 'model': 'stock.picking',
                })
        elif table_key == 'deliveries':
            domain = self._picking_domain(parsed, [('picking_type_code', '=', 'outgoing')])
            if search:
                domain.append(('name', 'ilike', search))
            if cf.get('name'):
                domain.append(('name', 'ilike', cf['name']))
            if cf.get('partner'):
                domain.append(('partner_id.name', 'ilike', cf['partner']))
            if cf.get('state'):
                domain.append(('state', 'ilike', cf['state']))
            Picking = self.env['stock.picking']
            total = Picking.search_count(domain)
            for p in Picking.search(domain, offset=offset, limit=page_size, order=order or 'scheduled_date desc'):
                rows.append({
                    'id': p.id, 'name': p.name,
                    'partner': p.partner_id.display_name if p.partner_id else '',
                    'date': fields.Datetime.to_string(p.scheduled_date) if p.scheduled_date else '',
                    'state': p.state, 'model': 'stock.picking',
                })
        else:
            return super()._table_page(parsed, table_key, page, page_size, search, order)

        return {
            'rows': rows,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': max(1, (total + page_size - 1) // page_size),
        }

    @api.model
    def _table_columns(self, table_key):
        if table_key in ('out_of_stock', 'top_selling'):
            return [
                {'key': 'name', 'label': _('Nombre'), 'sortable': True, 'filterable': True},
                {'key': 'qty', 'label': _('Cantidad'), 'sortable': True, 'filterable': False},
            ]
        return [
            {'key': 'name', 'label': _('Nombre'), 'sortable': True, 'filterable': True},
            {'key': 'partner', 'label': _('Contacto'), 'sortable': True, 'filterable': True},
            {'key': 'date', 'label': _('Fecha'), 'sortable': True, 'filterable': False},
            {'key': 'state', 'label': _('Estado'), 'sortable': True, 'filterable': True},
        ]
