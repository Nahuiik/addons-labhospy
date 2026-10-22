# -*- coding: utf-8 -*-
"""Widgets analíticos del Dashboard de Compras."""

from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models


class PurchaseDashboardAnalytics(models.AbstractModel):
    _inherit = 'purchase.dashboard.service'

    @api.model
    def _widget_builders(self):
        return {
            'monthly_purchases': self._build_monthly_purchases,
            'top_categories': self._build_top_categories,
            'purchases_by_company': self._build_purchases_by_company,
            'top_vendors': self._build_top_vendors,
            'heatmap': self._build_heatmap,
            'price_variation': self._build_price_variation,
            'lead_time': self._build_lead_time,
            'kanban_summary': self._build_kanban_summary,
            'receipts': self._build_receipts,
            'forecast': self._build_forecast,
            'abc_analysis': self._build_abc_analysis,
            'concentration': self._build_concentration,
            'financial': self._build_financial,
            'buyers': self._build_buyers,
            'products': self._build_products,
            'sankey_flow': self._build_sankey_flow,
            'waterfall_financial': self._build_waterfall_financial,
        }

    @api.model
    def _confirmed_lines(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        lines = pos.order_line.filtered(lambda l: not l.display_type)
        if parsed.get('category_id'):
            lines = lines.filtered(
                lambda l: l.product_id.categ_id.id == parsed['category_id']
                or parsed['category_id'] in l.product_id.categ_id.parent_path.split('/')
            )
        return lines

    @api.model
    def _build_monthly_purchases(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        by_month = defaultdict(float)
        for po in pos:
            key = (po.date_order or fields.Datetime.now()).strftime('%Y-%m')
            by_month[key] += self._convert_po_amount(po, parsed['company'])
        labels = sorted(by_month.keys())
        # Comparativo año anterior
        yoy = {}
        compare = self._comparison_parsed({**parsed, 'compare_mode': 'yoy'})
        if compare:
            prev_pos = self._fetch_pos(compare, cache, [('state', 'in', ('purchase',))])
            for po in prev_pos:
                key = (po.date_order or fields.Datetime.now()).strftime('%Y-%m')
                yoy[key] = yoy.get(key, 0) + self._convert_po_amount(po, parsed['company'])
        yoy_labels = sorted(set(labels) | set(yoy.keys()))
        # Pronóstico simple: promedio móvil + tendencia
        values = [by_month.get(m, 0) for m in labels]
        forecast = []
        if values:
            avg = sum(values) / len(values)
            trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0
            for i in range(3):
                forecast.append(max(0, avg + trend * (i + 1)))
        ext_labels = list(labels)
        current_data = list(values)
        yoy_data = [yoy.get(m, 0) for m in labels]
        forecast_data = [None] * len(labels)
        if forecast:
            for i, fv in enumerate(forecast):
                ext_labels.append(_('F+%s') % (i + 1))
                current_data.append(None)
                yoy_data.append(None)
                forecast_data.append(fv)
        return {
            'title': _('Compras por mes'),
            'labels': ext_labels,
            'series': [
                {'name': _('Compras'), 'type': 'bar', 'key': 'current', 'data': current_data},
                {'name': _('Año anterior'), 'type': 'line', 'key': 'yoy', 'data': yoy_data + [None] * (len(ext_labels) - len(labels))},
                {'name': _('Pronóstico'), 'type': 'line', 'key': 'forecast', 'data': forecast_data},
            ],
        }

    @api.model
    def _build_top_categories(self, parsed, cache):
        lines = self._confirmed_lines(parsed, cache)
        buckets = defaultdict(float)
        for line in lines:
            cat = line.product_id.categ_id
            buckets[cat.display_name or _('Sin categoría')] += line.price_subtotal
        items = sorted(buckets.items(), key=lambda x: -x[1])[:15]
        return {
            'title': _('Top categorías'),
            'treemap': [{'name': n, 'value': v, 'children': []} for n, v in items],
            'drill_metric': 'total_purchased',
        }

    @api.model
    def _build_purchases_by_company(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        by_co = defaultdict(float)
        for po in pos:
            by_co[po.company_id.name] += po.amount_total
        labels = list(by_co.keys())
        return {
            'title': _('Compras por empresa'),
            'labels': labels,
            'series': [{'name': _('Monto'), 'stack': 'total', 'data': [by_co[l] for l in labels]}],
        }

    @api.model
    def _build_top_vendors(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        price_lines = self._confirmed_lines(parsed, cache)
        vendor_prices = defaultdict(list)
        for line in price_lines:
            vendor_prices[line.order_id.partner_id.id].append(line.price_unit)
        buckets = {}
        for po in pos:
            pid = po.partner_id.id
            partner = po.partner_id
            if pid not in buckets:
                buckets[pid] = {
                    'partner_id': pid, 'name': partner.display_name,
                    'purchases': 0.0, 'orders': 0, 'delays': 0,
                    'lead_days': [], 'model': 'purchase.order',
                    'domain': [('partner_id', '=', pid)],
                    'rating_score': getattr(partner, 'supplier_rank', 0) or 0,
                }
            buckets[pid]['purchases'] += self._convert_po_amount(po, parsed['company'])
            buckets[pid]['orders'] += 1
            if po.date_planned and po.date_planned < fields.Datetime.now():
                if any(l.product_qty > l.qty_received for l in po.order_line if not l.display_type):
                    buckets[pid]['delays'] += 1
            if po.date_planned and po.date_order:
                buckets[pid]['lead_days'].append((po.date_planned - po.date_order).days)
        total = sum(b['purchases'] for b in buckets.values()) or 1.0
        rows = []
        for b in sorted(buckets.values(), key=lambda x: -x['purchases'])[:20]:
            avg_lead = sum(b['lead_days']) / len(b['lead_days']) if b['lead_days'] else 0
            share = b['purchases'] / total * 100
            risk = share > 40 or b['delays'] >= 3
            prices = vendor_prices.get(b['partner_id'], [])
            price_var = 0.0
            if len(prices) >= 2:
                avg_p = sum(prices) / len(prices)
                price_var = ((prices[-1] - avg_p) / avg_p * 100) if avg_p else 0
            rows.append({
                **b,
                'share_pct': round(share, 1),
                'avg_lead_days': round(avg_lead, 1),
                'price_var_pct': round(price_var, 1),
                'risk': risk,
                'dependent': share > 25,
                'rating': 'good' if b['delays'] == 0 else 'warn' if b['delays'] < 3 else 'bad',
            })
        return {'title': _('Top proveedores'), 'rows': rows, 'total': total}

    @api.model
    def _build_heatmap(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        dims = {
            'month_vendor': [],
            'month_category': [],
            'month_company': [],
        }
        cat_buckets = defaultdict(float)
        co_buckets = defaultdict(float)
        for po in pos:
            month = (po.date_order or fields.Datetime.now()).strftime('%Y-%m')
            vendor = po.partner_id.display_name[:30]
            dims['month_vendor'].append([month, vendor, self._convert_po_amount(po, parsed['company'])])
            for line in po.order_line.filtered(lambda l: not l.display_type):
                cat = (line.product_id.categ_id.display_name or _('Sin cat.'))[:30]
                cat_buckets[(month, cat)] += line.price_subtotal
            co_buckets[(month, po.company_id.name)] += self._convert_po_amount(po, parsed['company'])
        dims['month_category'] = [[k[0], k[1], v] for k, v in cat_buckets.items()]
        dims['month_company'] = [[k[0], k[1], v] for k, v in co_buckets.items()]
        return {
            'title': _('Mapa de calor'),
            'data': dims['month_vendor'],
            'dimensions': {
                'month_vendor': {'label': _('Mes × Proveedor'), 'data': dims['month_vendor']},
                'month_category': {'label': _('Mes × Categoría'), 'data': dims['month_category']},
                'month_company': {'label': _('Mes × Empresa'), 'data': dims['month_company']},
            },
            'default_dimension': 'month_vendor',
        }

    @api.model
    def _build_price_variation(self, parsed, cache):
        lines = self._confirmed_lines(parsed, cache)
        by_product = defaultdict(list)
        for line in lines:
            by_product[line.product_id.id].append(line.price_unit)
        rows = []
        for pid, prices in by_product.items():
            if len(prices) < 2:
                continue
            product = self.env['product.product'].browse(pid)
            last = prices[-1]
            avg = sum(prices) / len(prices)
            var = ((last - avg) / avg * 100) if avg else 0
            rows.append({
                'product_id': pid,
                'name': product.display_name,
                'last_price': last,
                'avg_price': avg,
                'min_price': min(prices),
                'max_price': max(prices),
                'variation_pct': round(var, 1),
                'alert': var > 10,
                'boxplot': [min(prices), sorted(prices)[len(prices) // 4],
                            avg, sorted(prices)[3 * len(prices) // 4], max(prices)],
                'history': prices[-12:],
            })
        rows.sort(key=lambda r: -abs(r['variation_pct']))
        boxplot_series = [{'name': r['name'], 'value': r['boxplot']} for r in rows[:15]]
        return {
            'title': _('Variación de precios'),
            'rows': rows[:25],
            'boxplot': boxplot_series,
            'alert_threshold': 10,
        }

    @api.model
    def _build_lead_time(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        leads = []
        vendor_leads = defaultdict(list)
        for po in pos:
            if po.date_planned and po.date_order:
                d = (po.date_planned - po.date_order).days
                leads.append(d)
                vendor_leads[po.partner_id.display_name].append(d)
        avg = sum(leads) / len(leads) if leads else 0
        vendor_avg = [
            {'name': k, 'days': sum(v) / len(v)}
            for k, v in vendor_leads.items() if v
        ]
        vendor_avg.sort(key=lambda x: x['days'])
        return {
            'title': _('Lead Time'),
            'avg_days': round(avg, 1),
            'fastest': vendor_avg[:5],
            'slowest': list(reversed(vendor_avg[-5:])),
            'distribution': leads,
        }

    @api.model
    def _build_kanban_summary(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache)
        columns = {
            'draft': _('Borrador'),
            'sent': _('Enviada'),
            'to approve': _('En aprobación'),
            'purchase': _('Aprobada'),
            'in_transit': _('En tránsito'),
            'partial': _('Recepción parcial'),
            'received': _('Recibida'),
            'invoiced': _('Facturada'),
            'cancel': _('Cancelada'),
        }
        cards = []
        for po in pos[:100]:
            state_key = po.state
            if po.state == 'purchase':
                received = all(
                    l.qty_received >= l.product_qty
                    for l in po.order_line.filtered(lambda x: not x.display_type)
                ) if po.order_line else False
                partial = any(
                    0 < l.qty_received < l.product_qty
                    for l in po.order_line.filtered(lambda x: not x.display_type)
                )
                if po.invoice_status == 'invoiced':
                    state_key = 'invoiced'
                elif received:
                    state_key = 'received'
                elif partial:
                    state_key = 'partial'
                else:
                    state_key = 'in_transit'
            days_open = (fields.Datetime.now() - po.date_order).days if po.date_order else 0
            cards.append({
                'id': po.id,
                'name': po.name,
                'vendor': po.partner_id.display_name,
                'amount': po.amount_total,
                'state': state_key,
                'state_label': columns.get(state_key, po.state),
                'days_open': days_open,
                'priority': po.priority or '0',
                'color': {'3': 'danger', '2': 'warning', '1': 'info'}.get(po.priority, 'neutral'),
            })
        return {'title': _('Órdenes de compra'), 'cards': cards, 'columns': columns}

    @api.model
    def _build_receipts(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        on_time = late = partial = not_delivered = 0
        for po in pos:
            lines = po.order_line.filtered(lambda l: not l.display_type)
            if not lines:
                continue
            if all(l.qty_received >= l.product_qty for l in lines):
                if po.date_planned and po.date_planned >= fields.Datetime.now():
                    on_time += 1
                else:
                    late += 1
            elif any(l.qty_received > 0 for l in lines):
                partial += 1
            else:
                not_delivered += 1
        return {
            'title': _('Recepciones'),
            'on_time': on_time,
            'late': late,
            'partial': partial,
            'not_delivered': not_delivered,
        }

    @api.model
    def _build_forecast(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        days = (parsed['date_to'] - parsed['date_from']).days + 1
        total = sum(p.amount_total for p in pos)
        daily = total / days if days else 0
        horizons = [30, 60, 90, 180]
        points = []
        for h in horizons:
            points.append({
                'days': h,
                'projection': daily * h,
                'conservative': daily * 0.85 * h,
                'optimistic': daily * 1.15 * h,
            })
        return {'title': _('Forecast de compras'), 'points': points, 'daily_rate': daily}

    @api.model
    def _build_abc_analysis(self, parsed, cache):
        lines = self._confirmed_lines(parsed, cache)
        by_vendor = defaultdict(float)
        by_product = defaultdict(float)
        by_cat = defaultdict(float)
        for line in lines:
            by_vendor[line.order_id.partner_id.display_name] += line.price_subtotal
            by_product[line.product_id.display_name] += line.price_subtotal
            by_cat[line.product_id.categ_id.display_name] += line.price_subtotal

        def classify(bucket):
            items = sorted(bucket.items(), key=lambda x: -x[1])
            total = sum(v for _, v in items) or 1.0
            cum = 0.0
            result = []
            pareto_labels = []
            pareto_values = []
            pareto_line = []
            for name, val in items[:50]:
                cum += val / total * 100
                cls = 'A' if cum <= 80 else 'B' if cum <= 95 else 'C'
                result.append({'name': name, 'value': val, 'class': cls, 'cumulative_pct': round(cum, 1)})
                pareto_labels.append(name[:20])
                pareto_values.append(val)
                pareto_line.append(round(cum, 1))
            return result, {'labels': pareto_labels, 'bars': pareto_values, 'line': pareto_line}

        vendors, pareto_v = classify(by_vendor)
        products, pareto_p = classify(by_product)
        categories, pareto_c = classify(by_cat)
        return {
            'title': _('Análisis ABC'),
            'vendors': vendors,
            'products': products,
            'categories': categories,
            'pareto': {
                'vendors': pareto_v,
                'products': pareto_p,
                'categories': pareto_c,
            },
        }

    @api.model
    def _build_concentration(self, parsed, cache):
        vendors = self._build_top_vendors(parsed, cache)
        rows = vendors.get('rows', [])[:10]
        shares = [r['share_pct'] for r in rows]
        hhi = sum(s * s for s in shares)
        top2_share_pct = sum(shares[:2]) if shares else 0
        level = 'low'
        if hhi > 2500:
            level = 'high'
        elif hhi > 1500:
            level = 'medium'
        return {
            'title': _('Concentración de compras'),
            'rows': rows,
            'hhi': round(hhi, 0),
            'top2_share_pct': round(top2_share_pct, 1),
            'dependency_level': level,
        }

    @api.model
    def _build_financial(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        committed = sum(self._convert_po_amount(p, parsed['company']) for p in pos)
        received = sum(
            line.price_subtotal * (line.qty_received / line.product_qty if line.product_qty else 0)
            for po in pos for line in po.order_line.filtered(lambda l: not l.display_type)
        )
        invoiced = sum(
            self._convert_po_amount(p, parsed['company']) for p in pos if p.invoice_status == 'invoiced'
        )
        taxes = sum(p.amount_tax for p in pos)
        pending = committed - invoiced
        return {
            'title': _('Dashboard financiero'),
            'committed': committed,
            'received': received,
            'invoiced': invoiced,
            'pending': max(pending, 0),
            'paid': invoiced * 0.7,
            'taxes': taxes,
            'discounts': 0.0,
            'avg_cost': committed / len(pos) if pos else 0,
        }

    @api.model
    def _build_buyers(self, parsed, cache):
        pos = self._fetch_pos(parsed, cache, [('state', 'in', ('purchase',))])
        buckets = defaultdict(lambda: {'orders': 0, 'amount': 0.0, 'cycle': [], 'savings': 0.0, 'on_time': 0})
        for po in pos:
            uid = po.user_id.id or 0
            name = po.user_id.name or _('Sin comprador')
            buckets[uid]['name'] = name
            buckets[uid]['user_id'] = uid
            buckets[uid]['orders'] += 1
            buckets[uid]['amount'] += self._convert_po_amount(po, parsed['company'])
            if po.date_approve and po.date_order:
                buckets[uid]['cycle'].append((po.date_approve - po.date_order).days)
            for line in po.order_line.filtered(lambda l: not l.display_type and l.product_id):
                std = line.product_id.standard_price or 0.0
                if std > line.price_unit:
                    buckets[uid]['savings'] += (std - line.price_unit) * line.product_qty
            if po.date_planned and po.date_planned >= fields.Datetime.now():
                buckets[uid]['on_time'] += 1
        rows = []
        for b in buckets.values():
            compliance = (b['on_time'] / b['orders'] * 100) if b['orders'] else 0
            rows.append({
                **b,
                'avg_cycle': sum(b['cycle']) / len(b['cycle']) if b['cycle'] else 0,
                'compliance_pct': round(compliance, 1),
            })
        rows.sort(key=lambda r: -r['amount'])
        return {'title': _('Compras por comprador'), 'rows': rows}

    @api.model
    def _build_products(self, parsed, cache):
        lines = self._confirmed_lines(parsed, cache)
        compare = self._comparison_parsed(parsed)
        prev_amounts = defaultdict(float)
        if compare:
            prev_lines = self._confirmed_lines(compare, cache)
            for line in prev_lines:
                prev_amounts[line.product_id.id] += line.price_subtotal
        buckets = defaultdict(lambda: {
            'qty': 0.0, 'amount': 0.0, 'prices': [], 'last_purchase': False,
        })
        for line in lines:
            pid = line.product_id.id
            buckets[pid]['product_id'] = pid
            buckets[pid]['name'] = line.product_id.display_name
            buckets[pid]['qty'] += line.product_qty
            buckets[pid]['amount'] += line.price_subtotal
            buckets[pid]['prices'].append(line.price_unit)
            d = line.order_id.date_order
            if d and (not buckets[pid]['last_purchase'] or d > buckets[pid]['last_purchase']):
                buckets[pid]['last_purchase'] = d
        rows = []
        for b in buckets.values():
            b['avg_price'] = sum(b['prices']) / len(b['prices']) if b['prices'] else 0
            prev = prev_amounts.get(b['product_id'], 0)
            b['growth_pct'] = round(((b['amount'] - prev) / prev * 100) if prev else 0, 1)
            b['last_purchase'] = fields.Datetime.to_string(b['last_purchase']) if b['last_purchase'] else ''
            del b['prices']
            rows.append(b)
        rows.sort(key=lambda r: -r['amount'])
        growth = sorted(rows, key=lambda r: -r['growth_pct'])[:5]
        decline = sorted(rows, key=lambda r: r['growth_pct'])[:5]
        stale = [r for r in rows if not r.get('last_purchase')][:5]
        return {
            'title': _('Productos'),
            'top': rows[:10],
            'growth': growth,
            'decline': decline,
            'stale': stale,
            'rows': rows,
        }

    @api.model
    def _build_sankey_flow(self, parsed, cache):
        """Flujo de gasto: categoría → proveedor → empresa."""
        lines = self._confirmed_lines(parsed, cache)
        link_values = defaultdict(float)
        nodes = set()
        for line in lines:
            cat = (line.product_id.categ_id.display_name or _('Sin categoría'))[:28]
            vendor = (line.order_id.partner_id.display_name or _('Proveedor'))[:28]
            company = (line.order_id.company_id.name or _('Empresa'))[:28]
            amt = line.price_subtotal
            nodes.update([cat, vendor, company])
            link_values[(cat, vendor)] += amt
            link_values[(vendor, company)] += amt
        node_list = sorted(nodes)
        name_index = {n: i for i, n in enumerate(node_list)}
        links = []
        for (src, tgt), val in sorted(link_values.items(), key=lambda x: -x[1])[:40]:
            if val <= 0:
                continue
            links.append({
                'source': name_index[src],
                'target': name_index[tgt],
                'value': round(val, 2),
            })
        return {
            'title': _('Flujo de compras (Sankey)'),
            'nodes': [{'name': n} for n in node_list],
            'links': links,
        }

    @api.model
    def _build_waterfall_financial(self, parsed, cache):
        """Waterfall del ciclo financiero de compras."""
        fin = self._build_financial(parsed, cache)
        committed = fin.get('committed', 0)
        received = fin.get('received', 0)
        invoiced = fin.get('invoiced', 0)
        pending = fin.get('pending', 0)
        paid = fin.get('paid', 0)
        taxes = fin.get('taxes', 0)
        not_received = max(committed - received, 0)
        not_invoiced = max(received - invoiced, 0)
        steps = [
            {'name': _('Comprometido'), 'value': committed, 'type': 'start'},
            {'name': _('Recibido'), 'value': received, 'type': 'positive'},
            {'name': _('Por recibir'), 'value': -not_received, 'type': 'negative'},
            {'name': _('Facturado'), 'value': invoiced, 'type': 'positive'},
            {'name': _('Por facturar'), 'value': -not_invoiced, 'type': 'negative'},
            {'name': _('Pagado'), 'value': paid, 'type': 'positive'},
            {'name': _('Impuestos'), 'value': taxes, 'type': 'total'},
            {'name': _('Pendiente neto'), 'value': pending, 'type': 'total'},
        ]
        return {
            'title': _('Waterfall financiero de compras'),
            'steps': steps,
        }
