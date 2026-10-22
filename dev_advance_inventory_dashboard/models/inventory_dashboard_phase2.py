# -*- coding: utf-8 -*-
"""Extensiones fase 2: KPIs, gráficos avanzados, exportación y reporte."""

import base64
import csv
import io
import json
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools import float_round


class InventoryDashboardServicePhase2(models.AbstractModel):
    _inherit = 'inventory.dashboard.service'

    _CACHE = {}
    _CACHE_TTL_SEC = 120

    @api.model
    def _cache_key(self, parsed):
        return json.dumps({
            'c': parsed['company'].id,
            'b': parsed.get('branch_id'),
            'w': parsed.get('warehouse_id'),
            'l': parsed.get('location_id'),
            'cat': parsed.get('category_id'),
            'p': parsed.get('product_id'),
            'df': fields.Date.to_string(parsed['date_from']),
            'dt': fields.Date.to_string(parsed['date_to']),
        }, sort_keys=True)

    @api.model
    def _get_cached_metrics(self, parsed):
        key = self._cache_key(parsed)
        entry = self._CACHE.get(key)
        now = fields.Datetime.now()
        if entry and (now - entry['ts']).total_seconds() < self._CACHE_TTL_SEC:
            return entry['data']
        data = super()._compute_metrics(parsed)
        data.update(self._compute_extended_metrics(parsed))
        self._CACHE[key] = {'ts': now, 'data': data}
        return data

    @api.model
    def _compute_metrics(self, parsed):
        return self._get_cached_metrics(parsed)

    @api.model
    def _compute_extended_metrics(self, parsed):
        """KPIs adicionales de fases 2–3."""
        m = {}
        Product = self.env['product.product']
        MoveLine = self.env['stock.move.line']
        Quant = self.env['stock.quant']
        pdomain = self._product_domain(parsed)

        analysis_end = parsed['date_to']
        analysis_start = analysis_end - timedelta(days=90)
        move_domain = [
            ('company_id', '=', parsed['company'].id),
            ('state', '=', 'done'),
            ('date', '>=', fields.Datetime.to_datetime(analysis_start)),
            ('date', '<=', fields.Datetime.to_datetime(analysis_end + timedelta(days=1))),
        ]
        if parsed.get('warehouse_id'):
            loc_ids = self._warehouse_locations(parsed['warehouse_id'])
            if loc_ids:
                move_domain += ['|', ('location_id', 'in', loc_ids), ('location_dest_id', 'in', loc_ids)]

        product_moves = MoveLine._read_group(
            domain=move_domain, groupby=['product_id'], aggregates=['quantity:sum'],
        )
        move_map = {p.id: float(q or 0) for p, q in product_moves if p}
        stocked = Product.search(pdomain + [('qty_available', '>', 0)])

        slow, fast = self.env['product.product'], self.env['product.product']
        slow_ids, fast_ids = [], []
        for p in stocked:
            mv = move_map.get(p.id, 0.0)
            if mv <= 0:
                slow_ids.append(p.id)
            elif mv >= 50:
                fast_ids.append(p.id)
        slow = Product.browse(slow_ids)
        fast = Product.browse(fast_ids)
        m['slow_moving'] = {'count': len(slow), 'ids': slow.ids}
        m['fast_moving'] = {'count': len(fast), 'ids': fast.ids}

        top_selling = MoveLine._read_group(
            domain=self._move_line_domain(parsed, [
                ('location_dest_id.usage', 'not in', ('internal', 'transit')),
            ]),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
            order='quantity:sum desc',
            limit=1,
        )
        if top_selling and top_selling[0][0]:
            p = top_selling[0][0]
            m['top_selling'] = {'count': 1, 'ids': [p.id], 'value': float(top_selling[0][1] or 0)}

        critical = Product.search(pdomain + [('qty_available', '<=', 0)])
        excess = []
        for p in stocked:
            max_qty = getattr(p, 'reordering_max_qty', 0) or 0
            if max_qty and p.qty_available > max_qty * 1.5:
                excess.append(p.id)
        m['critical_stock'] = {'count': len(critical), 'ids': critical.ids}
        m['excess_stock'] = {'count': len(excess), 'ids': excess}

        returned = MoveLine._read_group(
            domain=self._move_line_domain(parsed, [
                ('location_id.usage', 'not in', ('internal', 'transit')),
                ('location_dest_id.usage', '=', 'internal'),
            ]),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
            order='quantity:sum desc',
            limit=10,
        )
        ret_ids = [p.id for p, _q in returned if p]
        m['most_returned'] = {'count': len(ret_ids), 'ids': ret_ids}

        return m

    @api.model
    def _kpi_catalog(self):
        catalog = super()._kpi_catalog()
        catalog.update({
            'slow_moving': {'label': _('Productos lentos'), 'icon': 'fa-hourglass-half', 'format': 'count', 'tone': 'warning', 'metric': 'slow_moving'},
            'fast_moving': {'label': _('Productos rápidos'), 'icon': 'fa-bolt', 'format': 'count', 'tone': 'success', 'metric': 'fast_moving'},
            'top_selling': {'label': _('Top ventas'), 'icon': 'fa-star', 'format': 'qty', 'tone': 'success', 'metric': 'top_selling'},
            'critical_stock': {'label': _('Stock crítico'), 'icon': 'fa-exclamation', 'format': 'count', 'tone': 'danger', 'metric': 'critical_stock'},
            'excess_stock': {'label': _('Stock excesivo'), 'icon': 'fa-expand', 'format': 'count', 'tone': 'warning', 'metric': 'excess_stock'},
            'most_returned': {'label': _('Más devueltos'), 'icon': 'fa-reply', 'format': 'count', 'tone': 'warning', 'metric': 'most_returned'},
            'overdue_receipts': {'label': _('Recepciones atrasadas'), 'icon': 'fa-calendar-times-o', 'format': 'count', 'tone': 'danger', 'metric': 'overdue_receipts'},
            'reserved_quantity': {'label': _('Cantidad reservada'), 'icon': 'fa-lock', 'format': 'qty', 'tone': 'info', 'metric': 'reserved_quantity'},
        })
        return catalog

    @api.model
    def _build_charts(self, parsed, metrics):
        charts = super()._build_charts(parsed, metrics)
        MoveLine = self.env['stock.move.line']
        Picking = self.env['stock.picking']
        Quant = self.env['stock.quant']
        Product = self.env['product.product']

        # ABC por valor de inventario
        abc_labels, abc_values = [], []
        prod_vals = []
        for product, qty_sum in Quant._read_group(
            domain=self._quant_domain(parsed), groupby=['product_id'], aggregates=['quantity:sum'],
        ):
            if product:
                prod_vals.append((product, float(qty_sum or 0) * (product.standard_price or 0)))
        prod_vals.sort(key=lambda x: x[1], reverse=True)
        total_val = sum(v for _p, v in prod_vals) or 1.0
        cum = 0.0
        a, b, c = 0.0, 0.0, 0.0
        for _p, val in prod_vals:
            cum += val
            pct = cum / total_val * 100
            if pct <= 80:
                a += val
            elif pct <= 95:
                b += val
            else:
                c += val
        charts['abc_analysis'] = {
            'type': 'stacked_bar',
            'labels': [_('Clase A'), _('Clase B'), _('Clase C')],
            'datasets': [{'label': _('Valor'), 'data': [a, b, c]}],
        }

        # Pareto top productos
        top = MoveLine._read_group(
            domain=self._move_line_domain(parsed),
            groupby=['product_id'], aggregates=['quantity:sum'],
            order='quantity:sum desc', limit=10,
        )
        pareto_labels = [p.display_name for p, _q in top if p]
        pareto_vals = [float(q or 0) for p, q in top if p]
        charts['pareto'] = {'type': 'bar', 'labels': pareto_labels, 'values': pareto_vals}

        # Waterfall flujo neto
        inc = metrics.get('incoming_quantity', {}).get('value', 0)
        out = metrics.get('outgoing_quantity', {}).get('value', 0)
        charts['waterfall'] = {
            'type': 'waterfall',
            'labels': [_('Entradas'), _('Salidas'), _('Neto')],
            'values': [inc, -out, inc - out],
        }

        # Tendencia mensual (6 meses)
        trend_labels, trend_vals = [], []
        end = parsed['date_to'].replace(day=1)
        for i in range(5, -1, -1):
            month_end = end - timedelta(days=1) if i else parsed['date_to']
            month_start = (end - timedelta(days=30 * i)).replace(day=1)
            sub = {**parsed, 'date_from': month_start, 'date_to': min(month_end, parsed['date_to'])}
            qrows = Quant._read_group(
                domain=self._quant_domain(sub), groupby=['product_id'], aggregates=['quantity:sum'],
            )
            trend_labels.append(month_start.strftime('%b %Y'))
            trend_vals.append(sum(float(q or 0) for _p, q in qrows))
        charts['inventory_trend'] = {'type': 'line', 'labels': trend_labels, 'values': trend_vals}

        # Proveedores (recepciones)
        sup_rows = Picking._read_group(
            domain=self._picking_domain(parsed, [
                ('picking_type_code', '=', 'incoming'), ('state', '=', 'done'),
            ]),
            groupby=['partner_id'], aggregates=['__count'],
            order='__count desc', limit=8,
        )
        charts['supplier_performance'] = {
            'type': 'horizontal_bar',
            'labels': [p.display_name if p else _('N/A') for p, c in sup_rows],
            'values': [float(c or 0) for _p, c in sup_rows],
        }

        # Capacidad almacén (ocupación por ubicación top)
        loc_acc = defaultdict(float)
        for location, qty_sum in Quant._read_group(
            domain=self._quant_domain(parsed), groupby=['location_id'], aggregates=['quantity:sum'],
        ):
            if location:
                loc_acc[location.complete_name] += float(qty_sum or 0)
        loc_sorted = sorted(loc_acc.items(), key=lambda x: x[1], reverse=True)[:10]
        charts['warehouse_capacity'] = {
            'type': 'bar',
            'labels': [n for n, _q in loc_sorted],
            'values': [q for _n, q in loc_sorted],
        }

        # Heatmap simplificado: día de semana x semana del mes
        heat_labels = [_('Lun'), _('Mar'), _('Mié'), _('Jue'), _('Vie'), _('Sáb'), _('Dom')]
        heat_matrix = [[0.0] * 7 for _ in range(4)]
        for ml in MoveLine.search(self._move_line_domain(parsed), limit=5000):
            if not ml.date:
                continue
            d = fields.Datetime.to_datetime(ml.date)
            week_idx = min(3, (d.day - 1) // 7)
            heat_matrix[week_idx][d.weekday()] += float(ml.quantity or 0)
        charts['movement_heatmap'] = {
            'type': 'heatmap',
            'labels': heat_labels,
            'matrix': heat_matrix,
        }

        # XYZ variabilidad (simplificado por coeficiente de movimiento)
        xyz_counts = {'X': 0, 'Y': 0, 'Z': 0}
        for product, qty_sum in MoveLine._read_group(
            domain=self._move_line_domain(parsed), groupby=['product_id'], aggregates=['quantity:sum'],
        ):
            if not product:
                continue
            q = float(qty_sum or 0)
            if q > 100:
                xyz_counts['X'] += 1
            elif q > 20:
                xyz_counts['Y'] += 1
            else:
                xyz_counts['Z'] += 1
        charts['xyz_analysis'] = {
            'type': 'doughnut',
            'labels': list(xyz_counts.keys()),
            'values': list(xyz_counts.values()),
        }

        charts['monthly_inventory_value'] = {
            'type': 'line',
            'labels': trend_labels,
            'values': [
                sum(
                    float(q or 0) * (p.standard_price or 0)
                    for p, q in Quant._read_group(
                        domain=self._quant_domain({**parsed, 'date_from': (end - timedelta(days=30 * i)).replace(day=1), 'date_to': parsed['date_to']}),
                        groupby=['product_id'], aggregates=['quantity:sum'],
                    ) if p
                )
                for i in range(5, -1, -1)
            ],
        }

        sales_qty = sum(
            float(q or 0) for _p, q in MoveLine._read_group(
                domain=self._move_line_domain(parsed, [
                    ('location_dest_id.usage', 'not in', ('internal', 'transit')),
                ]),
                groupby=['product_id'], aggregates=['quantity:sum'],
            )
        )
        charts['sales_vs_inventory'] = {
            'type': 'bar',
            'labels': [_('Ventas (u.)'), _('Inventario (u.)')],
            'values': [sales_qty, metrics.get('stock_quantity', {}).get('value', 0)],
        }

        charts['dead_stock_analysis'] = {
            'type': 'horizontal_bar',
            'labels': [_('Stock muerto'), _('Activos')],
            'values': [
                metrics.get('dead_stock', {}).get('count', 0),
                max(0, metrics.get('available_products', {}).get('count', 0) - metrics.get('dead_stock', {}).get('count', 0)),
            ],
        }

        return charts

    @api.model
    def export_table_data(self, filters, table_key, export_format='csv', search=''):
        """Exportación server-side CSV (Excel-compatible)."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        page = self._table_page(parsed, table_key, 1, 5000, search, '')
        output = io.StringIO()
        writer = csv.writer(output)
        if table_key in ('out_of_stock', 'top_selling'):
            writer.writerow(['ID', _('Nombre'), _('Cantidad')])
            for row in page['rows']:
                writer.writerow([row['id'], row['name'], row.get('qty', '')])
        else:
            writer.writerow(['ID', _('Nombre'), _('Contacto'), _('Fecha'), _('Estado')])
            for row in page['rows']:
                writer.writerow([row['id'], row['name'], row.get('partner', ''), row.get('date', ''), row.get('state', '')])
        content = output.getvalue().encode('utf-8-sig')
        filename = f'inventory_{table_key}.{"csv" if export_format == "csv" else "xls"}'
        return {
            'filename': filename,
            'data': base64.b64encode(content).decode('ascii'),
            'mimetype': 'text/csv' if export_format == 'csv' else 'application/vnd.ms-excel',
        }

    @api.model
    def get_resolve_action(self, metric, filters=None):
        """Acción sugerida para resolver una alerta."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        resolve_map = {
            'out_of_stock': ('purchase.order', 'form', {'default_order_line': []}),
            'overdue_receipts': ('stock.picking', 'list,form', {}),
            'overdue_deliveries': ('stock.picking', 'list,form', {}),
            'products_without_vendor': ('product.product', 'list,form', {}),
        }
        model, view_mode, ctx = resolve_map.get(metric, ('stock.picking', 'list,form', {}))
        action = self._drilldown_action(parsed, metric, [])
        action['view_mode'] = view_mode
        action['views'] = self._views_for_mode(view_mode)
        action['context'] = ctx
        action['name'] = _('Resolver: %s') % action.get('name', metric)
        return action

    @api.model
    def get_executive_report_action(self, filters=None):
        """Reporte QWeb PDF ejecutivo."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        data = self.get_dashboard_data(filters or {})
        return self.env.ref(
            'dev_advance_inventory_dashboard.action_report_inventory_executive'
        ).report_action(
            parsed['company'].ids,
            data={
                'filters': self._filters_payload(parsed),
                'health': data['health'],
                'kpis': data['kpis'][:20],
                'alerts': data['alerts'],
                'insights': data['insights'],
                'recommendations': data['recommendations'],
                'user_name': self.env.user.name,
            },
        )

    @api.model
    def _drilldown_action(self, parsed, metric, extra_domain):
        model_map = {
            'open_pickings': 'stock.picking',
            'overdue_pickings': 'stock.picking',
            'awaiting_deliveries': 'stock.picking',
            'overdue_deliveries': 'stock.picking',
            'overdue_receipts': 'stock.picking',
            'out_of_stock': 'product.product',
            'negative_inventory': 'stock.quant',
            'purchase_orders_waiting': 'purchase.order',
            'dead_stock': 'product.product',
            'slow_moving': 'product.product',
            'fast_moving': 'product.product',
            'critical_stock': 'product.product',
            'excess_stock': 'product.product',
            'most_returned': 'product.product',
            'receipts_today': 'stock.picking',
            'deliveries_today': 'stock.picking',
            'products_without_vendor': 'product.product',
            'products_without_barcode': 'product.product',
            'products_without_cost': 'product.product',
        }
        action = super()._drilldown_action(parsed, metric, extra_domain)
        if metric in model_map:
            action['res_model'] = model_map[metric]
        return action
