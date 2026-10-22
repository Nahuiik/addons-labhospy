# -*- coding: utf-8 -*-
"""Dashboards por área (V20 Fase 4): Comercial, Compras, Inventario.

Cada panel está disponible solo si el módulo de origen está instalado
(detección suave de modelos), así el módulo principal sigue siendo
*account-only* y agrega valor incremental cuando hay sale/purchase/stock.

Para integrar paneles propios (p.ej. hospitalario, manufactura, etc.)
crea un módulo que herede ``gn.financial.dashboard`` y sobreescriba
``_register_area_panels()`` agregando una entrada al diccionario
``custom``. Cada entrada define:

- ``key``: identificador único usado como sub-pestaña.
- ``label`` / ``icon``: presentación en el menú de sub-pestañas.
- ``rpc``: nombre del método del modelo que devuelve el payload.

El frontend reconocerá automáticamente las entradas adicionales y
renderizará una sub-pestaña por cada una.
"""
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models


# Estados confirmados en cada flujo (Odoo 19).
SALE_CONFIRMED = ('sale',)
SALE_QUOTATION = ('draft', 'sent')
PURCHASE_CONFIRMED = ('purchase',)
PURCHASE_RFQ = ('draft', 'sent', 'to approve')
LIMIT_DEFAULT = 15


class GnFinancialDashboardAreas(models.AbstractModel):
    _inherit = 'gn.financial.dashboard'

    # ==================================================================
    # Capacidades por área (detección suave)
    # ==================================================================
    @api.model
    def _area_capabilities(self):
        """Devuelve qué áreas y paneles personalizados están disponibles."""
        has_sales = self.env.get('sale.order') is not None
        has_purchase = self.env.get('purchase.order') is not None
        has_stock = self.env.get('stock.quant') is not None
        customs = self._register_area_panels() or []
        # Limpieza de seguridad: cada entrada debe traer key, label y rpc.
        customs = [
            c for c in customs
            if c.get('key') and c.get('label') and c.get('rpc')
        ]
        return {
            'sales': has_sales,
            'purchase': has_purchase,
            'inventory': has_stock,
            'customs': customs,
        }

    @api.model
    def _register_area_panels(self):
        """Hook de extensión.

        Sobreescribe en un módulo descendente para añadir paneles propios::

            class MyDashboard(models.AbstractModel):
                _inherit = 'gn.financial.dashboard'

                def _register_area_panels(self):
                    panels = super()._register_area_panels()
                    panels.append({
                        'key': 'hospital',
                        'label': _('Hospitalario'),
                        'icon': 'fa-medkit',
                        'rpc': 'get_hospital_area_data',
                    })
                    return panels
        """
        return []

    # ==================================================================
    # Comercial (#11)
    # ==================================================================
    @api.model
    def get_sales_data(self, filters):
        if self.env.get('sale.order') is None:
            return {'available': False}
        parsed = self._parse_filters(filters)
        company = parsed['company']
        df, dt = parsed['date_from'], parsed['date_to']
        limit = int(filters.get('limit') or LIMIT_DEFAULT)
        SO = self.env['sale.order'].sudo()
        SOL = self.env['sale.order.line'].sudo()

        # Dominio base por compañía + rango de fechas.
        base = [('company_id', '=', company.id)]
        if parsed.get('branch_ids'):
            base.append(('branch_id', 'in', parsed['branch_ids'])) \
                if 'branch_id' in SO._fields else None
        period = base + [('date_order', '>=', df), ('date_order', '<=', dt)]

        # ----- KPIs principales -----
        quot_domain = period + [('state', 'in', list(SALE_QUOTATION))]
        conf_domain = period + [('state', 'in', list(SALE_CONFIRMED))]
        canc_domain = period + [('state', '=', 'cancel')]
        n_quot = SO.search_count(quot_domain)
        n_conf = SO.search_count(conf_domain)
        n_canc = SO.search_count(canc_domain)
        amt_quot = sum(SO.search(quot_domain).mapped('amount_untaxed'))
        amt_conf = sum(SO.search(conf_domain).mapped('amount_untaxed'))
        avg_ticket = (amt_conf / n_conf) if n_conf else 0.0
        # Conversion = confirmadas / (confirmadas + quotations + canceladas).
        total_attempts = n_conf + n_quot + n_canc
        conversion = (n_conf / total_attempts * 100.0) if total_attempts else 0.0

        # ----- Mensual (12 últimos meses dentro del rango) -----
        monthly = self._sales_monthly(SO, period)

        # ----- Top vendedores -----
        sellers = SO._read_group(
            conf_domain,
            groupby=['user_id'],
            aggregates=['amount_untaxed:sum', '__count'],
            order='amount_untaxed:sum desc',
            limit=limit,
        )
        top_sellers = [{
            'user_id': u.id if u else None,
            'name': u.display_name if u else _('(Sin vendedor)'),
            'amount': round(float(amt or 0.0), 2),
            'orders': int(count or 0),
        } for u, amt, count in sellers]

        # ----- Top equipos (si crm_team está disponible y poblado) -----
        top_teams = []
        if 'team_id' in SO._fields:
            teams = SO._read_group(
                conf_domain,
                groupby=['team_id'],
                aggregates=['amount_untaxed:sum', '__count'],
                order='amount_untaxed:sum desc',
                limit=limit,
            )
            top_teams = [{
                'team_id': t.id if t else None,
                'name': t.display_name if t else _('(Sin equipo)'),
                'amount': round(float(amt or 0.0), 2),
                'orders': int(count or 0),
            } for t, amt, count in teams]

        # ----- Top clientes -----
        customers = SO._read_group(
            conf_domain,
            groupby=['partner_id'],
            aggregates=['amount_untaxed:sum', '__count'],
            order='amount_untaxed:sum desc',
            limit=limit,
        )
        top_customers = [{
            'partner_id': p.id if p else None,
            'name': p.display_name if p else _('(Sin cliente)'),
            'amount': round(float(amt or 0.0), 2),
            'orders': int(count or 0),
        } for p, amt, count in customers]

        # ----- Top productos vendidos -----
        line_domain = [
            ('order_id.company_id', '=', company.id),
            ('order_id.state', 'in', list(SALE_CONFIRMED)),
            ('order_id.date_order', '>=', df),
            ('order_id.date_order', '<=', dt),
        ]
        prod_lines = SOL._read_group(
            line_domain,
            groupby=['product_id'],
            aggregates=['price_subtotal:sum', 'product_uom_qty:sum'],
            order='price_subtotal:sum desc',
            limit=limit,
        )
        top_products = [{
            'product_id': p.id if p else None,
            'name': p.display_name if p else _('(Sin producto)'),
            'amount': round(float(amt or 0.0), 2),
            'qty': round(float(qty or 0.0), 2),
        } for p, amt, qty in prod_lines]

        return {
            'available': True,
            'kpis': {
                'confirmed_amount': round(amt_conf, 2),
                'confirmed_count': n_conf,
                'pipeline_amount': round(amt_quot, 2),
                'pipeline_count': n_quot,
                'cancelled_count': n_canc,
                'avg_ticket': round(avg_ticket, 2),
                'conversion_pct': round(conversion, 1),
            },
            'monthly': monthly,
            'top_sellers': top_sellers,
            'top_teams': top_teams,
            'top_customers': top_customers,
            'top_products': top_products,
            'currency': self._currency_payload(company.currency_id),
        }

    def _sales_monthly(self, SO, domain):
        rows = SO._read_group(
            domain + [('state', 'in', list(SALE_CONFIRMED))],
            groupby=['date_order:month'],
            aggregates=['amount_untaxed:sum', '__count'],
            order='date_order:month',
        )
        labels, amounts, counts = [], [], []
        for label, amt, cnt in rows:
            labels.append(label)
            amounts.append(round(float(amt or 0.0), 2))
            counts.append(int(cnt or 0))
        return {'labels': labels, 'amounts': amounts, 'counts': counts}

    # ==================================================================
    # Compras (#12)
    # ==================================================================
    @api.model
    def get_purchase_data(self, filters):
        if self.env.get('purchase.order') is None:
            return {'available': False}
        parsed = self._parse_filters(filters)
        company = parsed['company']
        df, dt = parsed['date_from'], parsed['date_to']
        limit = int(filters.get('limit') or LIMIT_DEFAULT)
        PO = self.env['purchase.order'].sudo()
        POL = self.env['purchase.order.line'].sudo()

        base = [('company_id', '=', company.id)]
        period = base + [('date_order', '>=', df), ('date_order', '<=', dt)]

        rfq_domain = period + [('state', 'in', list(PURCHASE_RFQ))]
        conf_domain = period + [('state', 'in', list(PURCHASE_CONFIRMED))]
        canc_domain = period + [('state', '=', 'cancel')]
        n_rfq = PO.search_count(rfq_domain)
        n_conf = PO.search_count(conf_domain)
        n_canc = PO.search_count(canc_domain)
        amt_rfq = sum(PO.search(rfq_domain).mapped('amount_untaxed'))
        amt_conf = sum(PO.search(conf_domain).mapped('amount_untaxed'))
        avg_po = (amt_conf / n_conf) if n_conf else 0.0
        approved_rate = (n_conf / (n_conf + n_rfq + n_canc) * 100.0) \
            if (n_conf + n_rfq + n_canc) else 0.0

        # Lead time promedio y on-time rate sobre POs confirmadas con
        # effective_date conocida.
        lead_days, on_time = self._purchase_lead_metrics(PO, conf_domain)

        # Mensual confirmadas
        monthly = self._purchase_monthly(PO, period)

        # Top proveedores
        suppliers = PO._read_group(
            conf_domain,
            groupby=['partner_id'],
            aggregates=['amount_untaxed:sum', '__count'],
            order='amount_untaxed:sum desc',
            limit=limit,
        )
        top_suppliers = [{
            'partner_id': p.id if p else None,
            'name': p.display_name if p else _('(Sin proveedor)'),
            'amount': round(float(amt or 0.0), 2),
            'orders': int(count or 0),
        } for p, amt, count in suppliers]

        # Compradores (user_id)
        buyers = PO._read_group(
            conf_domain,
            groupby=['user_id'],
            aggregates=['amount_untaxed:sum', '__count'],
            order='amount_untaxed:sum desc',
            limit=limit,
        )
        top_buyers = [{
            'user_id': u.id if u else None,
            'name': u.display_name if u else _('(Sin comprador)'),
            'amount': round(float(amt or 0.0), 2),
            'orders': int(count or 0),
        } for u, amt, count in buyers]

        # Top productos comprados
        line_domain = [
            ('order_id.company_id', '=', company.id),
            ('order_id.state', 'in', list(PURCHASE_CONFIRMED)),
            ('order_id.date_order', '>=', df),
            ('order_id.date_order', '<=', dt),
        ]
        prod_lines = POL._read_group(
            line_domain,
            groupby=['product_id'],
            aggregates=['price_subtotal:sum', 'product_qty:sum'],
            order='price_subtotal:sum desc',
            limit=limit,
        )
        top_products = [{
            'product_id': p.id if p else None,
            'name': p.display_name if p else _('(Sin producto)'),
            'amount': round(float(amt or 0.0), 2),
            'qty': round(float(qty or 0.0), 2),
        } for p, amt, qty in prod_lines]

        return {
            'available': True,
            'kpis': {
                'confirmed_amount': round(amt_conf, 2),
                'confirmed_count': n_conf,
                'rfq_amount': round(amt_rfq, 2),
                'rfq_count': n_rfq,
                'cancelled_count': n_canc,
                'avg_po': round(avg_po, 2),
                'approved_rate_pct': round(approved_rate, 1),
                'avg_lead_days': lead_days,
                'on_time_pct': on_time,
            },
            'monthly': monthly,
            'top_suppliers': top_suppliers,
            'top_buyers': top_buyers,
            'top_products': top_products,
            'currency': self._currency_payload(company.currency_id),
        }

    def _purchase_lead_metrics(self, PO, domain):
        """Calcula lead time promedio y % de POs entregadas a tiempo.

        Lead time = effective_date - date_order (días).
        On-time = effective_date <= date_planned.

        ``date_order`` y ``date_planned`` son DateTime; ``effective_date`` es
        Date. Normalizamos a ``date`` para evitar TypeError al restar.
        """
        orders = PO.search_read(
            domain + [('effective_date', '!=', False)],
            ['date_order', 'effective_date', 'date_planned'],
            limit=2000,
        )
        if not orders:
            return 0.0, 0.0

        def _as_date(v):
            # ``datetime`` hereda de ``date``, así que es importante chequear
            # primero datetime y luego date.
            if isinstance(v, datetime):
                return v.date()
            if isinstance(v, date):
                return v
            return None

        lead_total = 0.0
        on_time_count = 0
        valid = 0
        for o in orders:
            do_d = _as_date(o.get('date_order'))
            ed_d = _as_date(o.get('effective_date'))
            pd = _as_date(o.get('date_planned'))
            if do_d and ed_d:
                lead_total += max(0, (ed_d - do_d).days)
                valid += 1
            if pd and ed_d and ed_d <= pd:
                on_time_count += 1
        avg_lead = (lead_total / valid) if valid else 0.0
        on_time_pct = (on_time_count / len(orders)) * 100.0
        return round(avg_lead, 1), round(on_time_pct, 1)

    def _purchase_monthly(self, PO, domain):
        rows = PO._read_group(
            domain + [('state', 'in', list(PURCHASE_CONFIRMED))],
            groupby=['date_order:month'],
            aggregates=['amount_untaxed:sum', '__count'],
            order='date_order:month',
        )
        labels, amounts, counts = [], [], []
        for label, amt, cnt in rows:
            labels.append(label)
            amounts.append(round(float(amt or 0.0), 2))
            counts.append(int(cnt or 0))
        return {'labels': labels, 'amounts': amounts, 'counts': counts}

    # ==================================================================
    # Inventario (#13)
    # ==================================================================
    @api.model
    def get_inventory_data(self, filters):
        if self.env.get('stock.quant') is None:
            return {'available': False}
        parsed = self._parse_filters(filters)
        company = parsed['company']
        df, dt = parsed['date_from'], parsed['date_to']
        limit = int(filters.get('limit') or LIMIT_DEFAULT)
        SQ = self.env['stock.quant'].sudo()
        SM = self.env['stock.move'].sudo()

        # Stock interno por producto: valor y cantidad agregados.
        # Filtramos qty > 0 para evitar productos con saldo cero pero registros
        # residuales (que en BDs medianas pueden dominar el read_group).
        base_quant = [
            ('company_id', '=', company.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
        ]
        has_value = 'value' in SQ._fields
        rows = SQ._read_group(
            base_quant,
            groupby=['product_id'],
            aggregates=['quantity:sum'] + (['value:sum'] if has_value else []),
            order=('value:sum desc' if has_value else 'quantity:sum desc'),
            # Pedimos más para poder ordenar localmente por valor real (algunos
            # productos quedan con value=0 si nunca se costearon).
            limit=max(limit * 4, 50),
        )
        top_candidates = []
        for r in rows:
            if has_value:
                product, qty, value = r
            else:
                product, qty = r
                value = float(qty or 0.0) * (product.standard_price if product else 0.0)
            value = float(value or 0.0)
            # Si stock_account no costeó la línea (value=0), fallback a
            # standard_price para no perder ese stock en el ranking.
            if value == 0.0 and product:
                value = float(qty or 0.0) * (product.standard_price or 0.0)
            top_candidates.append({
                'product_id': product.id if product else None,
                'name': product.display_name if product else _('(Sin producto)'),
                'qty': round(float(qty or 0.0), 2),
                'value': round(value, 2),
            })
        # Orden final por valor descendente y recorte al límite original.
        top_candidates.sort(key=lambda r: r['value'], reverse=True)
        top_products = top_candidates[:limit]

        # Totales globales (sin limit).
        all_rows = SQ._read_group(
            base_quant,
            groupby=[],
            aggregates=['quantity:sum'] + (
                ['value:sum'] if 'value' in SQ._fields else []
            ),
        )
        if all_rows:
            agg = all_rows[0]
            if 'value' in SQ._fields:
                global_qty, global_value = agg
            else:
                global_qty, = agg
                global_value = total_value  # estimación si no hay stock_account
            global_qty = float(global_qty or 0.0)
            global_value = float(global_value or 0.0)
        else:
            global_qty, global_value = 0.0, 0.0

        # Conteo de SKUs distintos con stock > 0.
        sku_rows = SQ._read_group(
            base_quant + [('quantity', '>', 0)],
            groupby=['product_id'],
            aggregates=['__count'],
        )
        n_products = len(sku_rows)

        # Productos sin movimiento N días (90 días por defecto).
        no_move_days = int(filters.get('no_move_days') or 90)
        slow_movers = self._inventory_slow_movers(SM, base_quant, no_move_days)

        # Movimientos del periodo (in/out).
        moves_in, moves_out = self._inventory_period_moves(SM, company, df, dt)

        return {
            'available': True,
            'kpis': {
                'total_value': round(global_value, 2),
                'total_qty': round(global_qty, 2),
                'n_products': n_products,
                'slow_movers_count': len(slow_movers),
                'moves_in': moves_in,
                'moves_out': moves_out,
                'no_move_days': no_move_days,
            },
            'top_products': top_products,
            'slow_movers': slow_movers[:limit],
            'currency': self._currency_payload(company.currency_id),
        }

    def _inventory_slow_movers(self, SM, base_quant, days):
        """Productos con stock > 0 y sin movimiento en los últimos N días."""
        cutoff = fields.Datetime.now() - timedelta(days=days)
        SQ = self.env['stock.quant'].sudo()
        product_ids_with_stock = set()
        # Primero, productos con stock interno > 0.
        rows = SQ._read_group(
            base_quant + [('quantity', '>', 0)],
            groupby=['product_id'],
            aggregates=['quantity:sum'],
        )
        stock_by_pid = {p.id: float(q or 0.0) for p, q in rows if p}
        if not stock_by_pid:
            return []
        # Productos con algún movimiento done desde cutoff.
        recent_rows = SM._read_group(
            [('state', '=', 'done'),
             ('date', '>=', cutoff),
             ('product_id', 'in', list(stock_by_pid))],
            groupby=['product_id'],
            aggregates=['__count'],
        )
        recent_pids = {p.id for p, _c in recent_rows if p}
        slow_pids = [pid for pid in stock_by_pid if pid not in recent_pids]
        if not slow_pids:
            return []
        products = self.env['product.product'].sudo().browse(slow_pids)
        out = []
        for p in products:
            qty = stock_by_pid.get(p.id, 0.0)
            value = qty * (p.standard_price or 0.0)
            out.append({
                'product_id': p.id,
                'name': p.display_name,
                'qty': round(qty, 2),
                'value': round(value, 2),
                'last_move': None,  # opcional: se podría calcular
            })
        # Ordenar por valor congelado descendente (más prioritario para liberar caja).
        out.sort(key=lambda r: r['value'], reverse=True)
        return out

    def _inventory_period_moves(self, SM, company, df, dt):
        """Conteo de movimientos done (entradas y salidas) en el rango."""
        base = [
            ('company_id', '=', company.id),
            ('state', '=', 'done'),
            ('date', '>=', df), ('date', '<=', dt),
        ]
        moves_in = SM.search_count(base + [
            ('location_id.usage', '!=', 'internal'),
            ('location_dest_id.usage', '=', 'internal'),
        ])
        moves_out = SM.search_count(base + [
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '!=', 'internal'),
        ])
        return moves_in, moves_out
