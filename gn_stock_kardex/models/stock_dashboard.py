# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools.float_utils import float_round


class StockDashboard(models.AbstractModel):
    _name = 'gn.stock.dashboard'
    _description = 'Datos del Panel de Stock'

    @api.model
    def get_dashboard_data(self, product_id=False, date_from=False, date_to=False,
                           location_id=False, warehouse_id=False):
        company = self.env.company
        today = fields.Date.today()
        if not date_from:
            date_from = today - timedelta(days=180)
        elif isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        if not date_to:
            date_to = today
        elif isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        result = {
            'company_name': company.name,
            'currency_symbol': company.currency_id.symbol,
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
        }

        # Product info
        product = None
        if product_id:
            product = self.env['product.product'].browse(product_id)
            if not product.exists():
                product = None

        result['product'] = {
            'id': product.id if product else False,
            'name': product.display_name if product else '',
            'default_code': product.default_code or '' if product else '',
            'qty_available': float_round(product.qty_available, precision_digits=2) if product else 0,
            'uom': product.uom_id.name if product else '',
            'is_storable': product.is_storable if product else False,
        } if product else False

        # Internal locations
        loc_domain = [('usage', '=', 'internal'), ('company_id', '=', company.id)]
        if warehouse_id:
            loc_domain.append(('warehouse_id', '=', warehouse_id))
        internal_locs = self.env['stock.location'].search(loc_domain)
        int_loc_ids = internal_locs.ids

        # ── Inventory summary ──
        cid_str = str(company.id)
        quant_where = "sq.company_id = %s AND sq.location_id = ANY(%s)"
        quant_params = [company.id, int_loc_ids]
        if product_id:
            quant_where += " AND sq.product_id = %s"
            quant_params.append(product_id)

        self.env.cr.execute(f"""
            SELECT COALESCE(SUM(sq.quantity), 0) AS total_qty,
                   COALESCE(SUM(sq.quantity *
                       COALESCE((pp.standard_price->>%s)::numeric, 0)), 0) AS total_value,
                   COUNT(DISTINCT sq.product_id) AS product_count
              FROM stock_quant sq
              JOIN product_product pp ON pp.id = sq.product_id
             WHERE {quant_where} AND sq.quantity > 0
        """, [cid_str] + quant_params)
        inv = self.env.cr.dictfetchone()
        result['inventory'] = {
            'total_qty': float_round(inv['total_qty'], precision_digits=2),
            'total_value': float_round(inv['total_value'], precision_digits=2),
            'product_count': inv['product_count'],
        }

        # ── Location breakdown (pie chart data) ──
        loc_params = [company.id, int_loc_ids]
        loc_product_clause = ""
        if product_id:
            loc_product_clause = " AND sq.product_id = %s"
            loc_params.append(product_id)
        self.env.cr.execute(f"""
            SELECT sl.complete_name AS loc_name,
                   COALESCE(SUM(sq.quantity), 0) AS qty
              FROM stock_quant sq
              JOIN stock_location sl ON sl.id = sq.location_id
             WHERE sq.company_id = %s AND sq.location_id = ANY(%s)
               AND sq.quantity > 0
               {loc_product_clause}
             GROUP BY sl.complete_name
             ORDER BY qty DESC
             LIMIT 8
        """, loc_params)
        result['locations'] = [
            {'name': r['loc_name'], 'qty': float_round(r['qty'], precision_digits=2)}
            for r in self.env.cr.dictfetchall()
        ]

        # ── Stock level history (line chart - monthly) ──
        result['stock_history'] = self._get_stock_history(
            company.id, int_loc_ids, date_from, date_to, product_id)

        # ── Recent movements ──
        result['movements'] = self._get_recent_movements(
            company.id, int_loc_ids, date_from, date_to, product_id)

        # ── Pending orders ──
        result['pending'] = self._get_pending_orders(company.id, product_id)

        # ── Top products (if no specific product) ──
        if not product_id:
            result['top_products'] = self._get_top_products(company.id, int_loc_ids)

        # ── Advanced analytics (global only) ──
        if not product_id:
            result['stock_rotation'] = self._get_stock_rotation(company.id, int_loc_ids, cid_str)
            result['overstock'] = self._get_overstock_analysis(company.id, int_loc_ids, cid_str)
            result['turnover'] = self._get_turnover_analysis(
                company.id, int_loc_ids, date_from, date_to, cid_str)

        return result

    @api.model
    def _get_stock_history(self, company_id, loc_ids, date_from, date_to, product_id=False):
        """Monthly stock level snapshots for chart."""
        from dateutil.relativedelta import relativedelta

        product_clause = ""
        params = [company_id, loc_ids]
        if product_id:
            product_clause = " AND sm.product_id = %s"
            params.append(product_id)

        # Get moves in the period grouped by month
        self.env.cr.execute(f"""
            SELECT date_trunc('month', sm.date)::date AS month,
                   SUM(CASE WHEN sm.location_dest_id = ANY(%s) AND sm.location_id != ALL(%s)
                            THEN sm.quantity ELSE 0 END) AS qty_in,
                   SUM(CASE WHEN sm.location_id = ANY(%s) AND sm.location_dest_id != ALL(%s)
                            THEN sm.quantity ELSE 0 END) AS qty_out
              FROM stock_move sm
             WHERE sm.state = 'done' AND sm.company_id = %s
               AND sm.date >= %s AND sm.date <= %s
               AND (sm.location_dest_id = ANY(%s) OR sm.location_id = ANY(%s))
               {product_clause}
             GROUP BY date_trunc('month', sm.date)
             ORDER BY month
        """, (loc_ids, loc_ids, loc_ids, loc_ids, company_id,
              date_from, date_to, loc_ids, loc_ids, *([product_id] if product_id else [])))

        months = []
        for r in self.env.cr.dictfetchall():
            months.append({
                'month': r['month'].strftime('%b %Y'),
                'qty_in': float_round(r['qty_in'], precision_digits=2),
                'qty_out': float_round(r['qty_out'], precision_digits=2),
            })
        return months

    @api.model
    def _get_recent_movements(self, company_id, loc_ids, date_from, date_to, product_id=False):
        """Last 20 stock movements."""
        product_clause = ""
        params = [company_id, date_from, date_to, loc_ids, loc_ids]
        if product_id:
            product_clause = " AND sm.product_id = %s"
            params.append(product_id)

        self.env.cr.execute(f"""
            SELECT sm.id, sm.date, sm.quantity,
                   pp.id AS product_id,
                   sm.reference,
                   sm.origin,
                   CASE
                       WHEN sm.location_dest_id = ANY(%s) AND sm.location_id != ALL(%s) THEN 'in'
                       WHEN sm.location_id = ANY(%s) AND sm.location_dest_id != ALL(%s) THEN 'out'
                       ELSE 'internal'
                   END AS move_type,
                   sl_src.complete_name AS src_location,
                   sl_dst.complete_name AS dst_location,
                   sp.name AS picking_name,
                   sw.name AS warehouse_name
              FROM stock_move sm
              JOIN product_product pp ON pp.id = sm.product_id
              LEFT JOIN stock_location sl_src ON sl_src.id = sm.location_id
              LEFT JOIN stock_location sl_dst ON sl_dst.id = sm.location_dest_id
              LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
              LEFT JOIN stock_warehouse sw ON sw.id = sm.warehouse_id
             WHERE sm.state = 'done' AND sm.company_id = %s
               AND sm.date >= %s AND sm.date <= %s
               AND (sm.location_dest_id = ANY(%s) OR sm.location_id = ANY(%s))
               {product_clause}
             ORDER BY sm.date DESC
             LIMIT 20
        """, (loc_ids, loc_ids, loc_ids, loc_ids, *params))

        moves = []
        for r in self.env.cr.dictfetchall():
            label = 'Entrada' if r['move_type'] == 'in' else ('Salida' if r['move_type'] == 'out' else 'Transferencia Interna')
            moves.append({
                'id': r['id'],
                'date': r['date'].strftime('%d-%m-%Y') if r['date'] else '',
                'time': r['date'].strftime('%I:%M %p') if r['date'] else '',
                'quantity': float_round(r['quantity'], precision_digits=2),
                'reference': r['picking_name'] or r['reference'] or '',
                'origin': r['origin'] or '',
                'move_type': r['move_type'],
                'label': label,
                'warehouse': r['warehouse_name'] or '',
                'picking_id': False,
            })
        return moves

    @api.model
    def _get_pending_orders(self, company_id, product_id=False):
        product_clause = ""
        params = [company_id]
        if product_id:
            product_clause = " AND sm.product_id = %s"
            params.append(product_id)

        self.env.cr.execute(f"""
            SELECT COUNT(*) AS count,
                   COALESCE(SUM(sm.product_uom_qty), 0) AS total_qty
              FROM stock_move sm
             WHERE sm.state IN ('confirmed', 'waiting', 'assigned')
               AND sm.company_id = %s
               {product_clause}
        """, params)
        r = self.env.cr.dictfetchone()
        return {
            'count': r['count'],
            'total_qty': float_round(r['total_qty'], precision_digits=2),
        }

    @api.model
    def _get_top_products(self, company_id, loc_ids):
        cid_str = str(company_id)
        self.env.cr.execute("""
            SELECT sq.product_id,
                   COALESCE(SUM(sq.quantity), 0) AS qty,
                   COALESCE(SUM(sq.quantity *
                       COALESCE((pp.standard_price->>%s)::numeric, 0)), 0) AS value
              FROM stock_quant sq
              JOIN product_product pp ON pp.id = sq.product_id
             WHERE sq.company_id = %s AND sq.location_id = ANY(%s) AND sq.quantity > 0
             GROUP BY sq.product_id
             ORDER BY value DESC
             LIMIT 10
        """, (cid_str, company_id, loc_ids))
        rows = self.env.cr.dictfetchall()
        if not rows:
            return []

        pids = [r['product_id'] for r in rows]
        products = {p.id: p for p in self.env['product.product'].browse(pids)}
        return [{
            'product_id': r['product_id'],
            'name': products[r['product_id']].display_name if r['product_id'] in products else '',
            'qty': float_round(r['qty'], precision_digits=2),
            'value': float_round(r['value'], precision_digits=2),
        } for r in rows]

    # ══════════════════════════════════════════════════
    #  STOCK ROTATION ANALYSIS
    # ══════════════════════════════════════════════════

    @api.model
    def _get_stock_rotation(self, company_id, loc_ids, cid_str):
        self.env.cr.execute("""
            SELECT sq.product_id,
                   COALESCE(SUM(sq.quantity), 0) AS qty,
                   COALESCE(SUM(sq.quantity *
                       COALESCE((pp.standard_price->>%s)::numeric, 0)), 0) AS value,
                   MAX(sm.date)::date AS last_move
              FROM stock_quant sq
              JOIN product_product pp ON pp.id = sq.product_id
              LEFT JOIN stock_move sm
                ON sm.product_id = sq.product_id
               AND sm.state = 'done'
               AND sm.company_id = %s
             WHERE sq.company_id = %s
               AND sq.location_id = ANY(%s)
               AND sq.quantity > 0
             GROUP BY sq.product_id
        """, (cid_str, company_id, company_id, loc_ids))
        raw = self.env.cr.dictfetchall()
        if not raw:
            return {'summary': [], 'products': []}

        today = fields.Date.today()
        pids = [r['product_id'] for r in raw]
        prod_map = {p.id: p for p in self.env['product.product'].browse(pids)}

        buckets = {'fast': 0, 'medium': 0, 'slow': 0, 'none': 0}
        bucket_value = {'fast': 0.0, 'medium': 0.0, 'slow': 0.0, 'none': 0.0}
        products = []

        for r in raw:
            days = (today - r['last_move']).days if r['last_move'] else 9999
            if days <= 30:
                cls = 'fast'
            elif days <= 90:
                cls = 'medium'
            elif days <= 180:
                cls = 'slow'
            else:
                cls = 'none'
            buckets[cls] += 1
            bucket_value[cls] += r['value'] or 0.0
            p = prod_map.get(r['product_id'])
            products.append({
                'product_id': r['product_id'],
                'name': p.display_name if p else '',
                'qty': float_round(r['qty'], precision_digits=2),
                'value': float_round(r['value'], precision_digits=2),
                'days_since': days,
                'classification': cls,
            })

        products.sort(key=lambda x: x['days_since'], reverse=True)

        summary = [
            {'label': 'Rápido (≤30d)', 'key': 'fast', 'count': buckets['fast'],
             'value': float_round(bucket_value['fast'], precision_digits=2)},
            {'label': 'Medio (31-90d)', 'key': 'medium', 'count': buckets['medium'],
             'value': float_round(bucket_value['medium'], precision_digits=2)},
            {'label': 'Lento (91-180d)', 'key': 'slow', 'count': buckets['slow'],
             'value': float_round(bucket_value['slow'], precision_digits=2)},
            {'label': 'Sin mov. (>180d)', 'key': 'none', 'count': buckets['none'],
             'value': float_round(bucket_value['none'], precision_digits=2)},
        ]
        return {'summary': summary, 'products': products[:50]}

    # ══════════════════════════════════════════════════
    #  OVERSTOCK ANALYSIS
    # ══════════════════════════════════════════════════

    @api.model
    def _get_overstock_analysis(self, company_id, loc_ids, cid_str):
        OVERSTOCK_MULTIPLIER = 2.0
        MONTHS = 6

        # Average monthly demand = outgoing qty over last 6 months / 6
        self.env.cr.execute("""
            SELECT sm.product_id,
                   SUM(sm.quantity) / %s AS avg_monthly_demand
              FROM stock_move sm
             WHERE sm.state = 'done'
               AND sm.company_id = %s
               AND sm.location_id = ANY(%s)
               AND sm.location_dest_id != ALL(%s)
               AND sm.date >= (CURRENT_DATE - INTERVAL '%s months')
             GROUP BY sm.product_id
        """, (float(MONTHS), company_id, loc_ids, loc_ids, MONTHS))
        demand_map = {r['product_id']: r['avg_monthly_demand']
                      for r in self.env.cr.dictfetchall()}

        # Current stock
        self.env.cr.execute("""
            SELECT sq.product_id,
                   COALESCE(SUM(sq.quantity), 0) AS qty,
                   COALESCE(SUM(sq.quantity *
                       COALESCE((pp.standard_price->>%s)::numeric, 0)), 0) AS value
              FROM stock_quant sq
              JOIN product_product pp ON pp.id = sq.product_id
             WHERE sq.company_id = %s
               AND sq.location_id = ANY(%s)
               AND sq.quantity > 0
             GROUP BY sq.product_id
        """, (cid_str, company_id, loc_ids))
        quant_rows = self.env.cr.dictfetchall()

        if not quant_rows:
            return {'total_excess_value': 0, 'overstock_count': 0, 'products': []}

        pids = [r['product_id'] for r in quant_rows]
        prod_map = {p.id: p for p in self.env['product.product'].browse(pids)}

        overstock_products = []
        total_excess_value = 0.0
        for r in quant_rows:
            pid = r['product_id']
            demand = demand_map.get(pid, 0.0) or 0.0
            threshold = demand * OVERSTOCK_MULTIPLIER
            qty = r['qty']
            if qty <= threshold or demand <= 0:
                continue
            excess_qty = qty - threshold
            unit_cost = r['value'] / qty if qty else 0
            excess_value = excess_qty * unit_cost
            total_excess_value += excess_value
            p = prod_map.get(pid)
            overstock_products.append({
                'product_id': pid,
                'name': p.display_name if p else '',
                'qty': float_round(qty, precision_digits=2),
                'demand': float_round(demand, precision_digits=2),
                'threshold': float_round(threshold, precision_digits=2),
                'excess_qty': float_round(excess_qty, precision_digits=2),
                'excess_value': float_round(excess_value, precision_digits=2),
                'ratio': float_round(qty / demand if demand else 0, precision_digits=1),
            })

        overstock_products.sort(key=lambda x: x['excess_value'], reverse=True)
        return {
            'total_excess_value': float_round(total_excess_value, precision_digits=2),
            'overstock_count': len(overstock_products),
            'products': overstock_products[:30],
        }

    # ══════════════════════════════════════════════════
    #  INVENTORY TURNOVER ANALYSIS
    # ══════════════════════════════════════════════════

    @api.model
    def _get_turnover_analysis(self, company_id, loc_ids, date_from, date_to, cid_str):
        days_in_period = max((date_to - date_from).days, 1)

        # COGS by category (outgoing moves value)
        self.env.cr.execute("""
            SELECT pt.categ_id,
                   SUM(sm.quantity * ABS(COALESCE(sm.price_unit, 0))) AS cogs
              FROM stock_move sm
              JOIN product_product pp ON pp.id = sm.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE sm.state = 'done'
               AND sm.company_id = %s
               AND sm.location_id = ANY(%s)
               AND sm.location_dest_id != ALL(%s)
               AND sm.date >= %s AND sm.date <= %s
             GROUP BY pt.categ_id
        """, (company_id, loc_ids, loc_ids, date_from, date_to))
        cogs_map = {r['categ_id']: r['cogs'] for r in self.env.cr.dictfetchall()}

        # Average inventory value by category
        self.env.cr.execute("""
            SELECT pt.categ_id,
                   COALESCE(SUM(sq.quantity *
                       COALESCE((pp.standard_price->>%s)::numeric, 0)), 0) AS inv_value
              FROM stock_quant sq
              JOIN product_product pp ON pp.id = sq.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE sq.company_id = %s
               AND sq.location_id = ANY(%s)
               AND sq.quantity > 0
             GROUP BY pt.categ_id
        """, (cid_str, company_id, loc_ids))
        inv_map = {r['categ_id']: r['inv_value'] for r in self.env.cr.dictfetchall()}

        all_categ_ids = set(list(cogs_map.keys()) + list(inv_map.keys()))
        all_categ_ids.discard(None)
        all_categ_ids.discard(False)
        if not all_categ_ids:
            return {'overall_ratio': 0, 'overall_dsi': 0, 'categories': [], 'monthly': []}

        categ_objs = {c.id: c for c in self.env['product.category'].browse(list(all_categ_ids))}

        categories = []
        total_cogs = 0.0
        total_inv = 0.0
        for cid in sorted(all_categ_ids):
            cogs = cogs_map.get(cid, 0.0) or 0.0
            inv_val = inv_map.get(cid, 0.0) or 0.0
            ratio = cogs / inv_val if inv_val > 0 else 0.0
            dsi = days_in_period / ratio if ratio > 0 else 0.0
            total_cogs += cogs
            total_inv += inv_val
            cat = categ_objs.get(cid)
            categories.append({
                'categ_id': cid,
                'name': cat.complete_name if cat else 'Sin categoría',
                'cogs': float_round(cogs, precision_digits=2),
                'inv_value': float_round(inv_val, precision_digits=2),
                'ratio': float_round(ratio, precision_digits=2),
                'dsi': float_round(dsi, precision_digits=1),
            })
        categories.sort(key=lambda x: x['ratio'], reverse=True)

        overall_ratio = total_cogs / total_inv if total_inv > 0 else 0.0
        overall_dsi = days_in_period / overall_ratio if overall_ratio > 0 else 0.0

        # Monthly turnover trend
        self.env.cr.execute("""
            SELECT date_trunc('month', sm.date)::date AS month,
                   SUM(sm.quantity * ABS(COALESCE(sm.price_unit, 0))) AS cogs
              FROM stock_move sm
             WHERE sm.state = 'done'
               AND sm.company_id = %s
               AND sm.location_id = ANY(%s)
               AND sm.location_dest_id != ALL(%s)
               AND sm.date >= %s AND sm.date <= %s
             GROUP BY date_trunc('month', sm.date)
             ORDER BY month
        """, (company_id, loc_ids, loc_ids, date_from, date_to))
        monthly = []
        for r in self.env.cr.dictfetchall():
            m_cogs = r['cogs'] or 0.0
            m_ratio = m_cogs / total_inv if total_inv > 0 else 0.0
            monthly.append({
                'month': r['month'].strftime('%b %Y'),
                'cogs': float_round(m_cogs, precision_digits=2),
                'ratio': float_round(m_ratio * 12, precision_digits=2),
            })

        return {
            'overall_ratio': float_round(overall_ratio, precision_digits=2),
            'overall_dsi': float_round(overall_dsi, precision_digits=1),
            'total_cogs': float_round(total_cogs, precision_digits=2),
            'categories': categories[:20],
            'monthly': monthly,
        }
