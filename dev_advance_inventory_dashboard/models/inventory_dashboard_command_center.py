# -*- coding: utf-8 -*-
"""Inventory Command Center — extensión Enterprise (Odoo 19)."""

from datetime import timedelta

from odoo import _, api, fields, models


class InventoryDashboardCommandCenter(models.AbstractModel):
    _inherit = 'inventory.dashboard.service'

    PERIOD_PRESETS_EXTRA = ('this_quarter',)

    # ------------------------------------------------------------------
    # Filtros ampliados
    # ------------------------------------------------------------------

    @api.model
    def _period_preset_options(self):
        opts = super()._period_preset_options()
        opts.insert(4, {'id': 'this_quarter', 'name': _('Este trimestre')})
        return opts

    @api.model
    def _resolve_period(self, filters):
        preset = filters.get('period') or 'this_month'
        if preset == 'this_quarter':
            today = fields.Date.context_today(self)
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            date_from = today.replace(month=quarter_start_month, day=1)
            return 'this_quarter', date_from, today
        return super()._resolve_period(filters)

    @api.model
    def _parse_filters(self, filters):
        parsed = super()._parse_filters(filters)
        parsed['lot_id'] = filters.get('lot_id') or False
        return parsed

    @api.model
    def get_filter_options(self):
        opts = super().get_filter_options()
        company = self.env.company
        lots = self.env['stock.lot'].search([
            ('company_id', 'in', (False, company.id)),
        ], order='name', limit=300)
        opts['lots'] = [{'id': l.id, 'name': l.display_name} for l in lots]
        opts['refresh_presets'] = [
            {'id': 0, 'name': _('Manual')},
            {'id': 1, 'name': _('1 min')},
            {'id': 5, 'name': _('5 min')},
            {'id': 15, 'name': _('15 min')},
            {'id': 30, 'name': _('30 min')},
        ]
        opts['layout_presets'] = [
            {'id': 'management', 'name': _('Gerencia')},
            {'id': 'purchasing', 'name': _('Compras')},
            {'id': 'logistics', 'name': _('Logística')},
            {'id': 'warehouse', 'name': _('Bodega')},
            {'id': 'finance', 'name': _('Dirección Financiera')},
        ]
        return opts

    @api.model
    def get_layout_preset(self, preset_id):
        """Plantillas de layout por rol."""
        self._check_dashboard_access()
        presets = {
            'management': ['executive_header', 'executive_kpis', 'hero_chart', 'alerts_insights', 'financial', 'advanced_charts', 'tables'],
            'purchasing': ['executive_header', 'executive_kpis', 'alerts_insights', 'financial', 'tables', 'activity', 'quick_actions'],
            'logistics': ['executive_header', 'executive_kpis', 'hero_chart', 'alerts_insights', 'activity', 'advanced_charts', 'tables'],
            'warehouse': ['executive_header', 'executive_kpis', 'alerts_insights', 'activity', 'tables', 'quick_actions'],
            'finance': ['executive_header', 'financial', 'executive_kpis', 'advanced_charts', 'tables'],
        }
        widget_ids = presets.get(preset_id, presets['management'])
        all_widgets = [
            'executive_header', 'executive_kpis', 'hero_chart', 'alerts_insights',
            'financial', 'advanced_charts', 'activity', 'quick_actions', 'tables',
        ]
        return {
            'widgets': [
                {'id': wid, 'type': wid, 'visible': wid in widget_ids, 'size': 'full', 'order': i}
                for i, wid in enumerate(all_widgets)
            ],
            'kpi_keys': [],
            'chart_keys': [],
        }

    # ------------------------------------------------------------------
    # Payload ampliado
    # ------------------------------------------------------------------

    # Payload ampliado vía get_dashboard_core / get_dashboard_widgets (timeseries)

    @api.model
    def _compute_extended_metrics(self, parsed):
        m = super()._compute_extended_metrics(parsed)
        Product = self.env['product.product']
        Picking = self.env['stock.picking']
        Quant = self.env['stock.quant']
        pdomain = self._product_domain(parsed)
        pk_in = self._picking_domain(parsed, [('picking_type_code', '=', 'incoming')])

        pending_rec = Picking.search(pk_in + [('state', 'in', ('confirmed', 'assigned', 'waiting', 'partially_available'))])
        m['pending_receipts'] = {'count': len(pending_rec), 'ids': pending_rec.ids}

        quant_rows = Quant._read_group(
            domain=self._quant_domain(parsed), groupby=['product_id'],
            aggregates=['quantity:sum', 'reserved_quantity:sum'],
        )
        total_qty = sum(float(q or 0) for _, q, _ in quant_rows)
        total_reserved = sum(float(r or 0) for _, _, r in quant_rows)
        m['available_quantity'] = {'value': max(0.0, total_qty - total_reserved)}

        no_cat = Product.search(pdomain + [('categ_id', '=', False)])
        m['products_without_category'] = {'count': len(no_cat), 'ids': no_cat.ids}

        sold_ids = {
            p.id for p, _q in self.env['stock.move.line']._read_group(
                domain=self._move_line_domain(parsed, [
                    ('location_dest_id.usage', 'not in', ('internal', 'transit')),
                ]),
                groupby=['product_id'], aggregates=['quantity:sum'],
            ) if p
        }
        all_prods = Product.search(pdomain)
        never_sold = all_prods.filtered(lambda p: p.id not in sold_ids)
        m['never_sold'] = {'count': len(never_sold), 'ids': never_sold.ids}

        purchased_ids = {
            p.id for p, _q in self.env['stock.move.line']._read_group(
                domain=self._move_line_domain(parsed, [
                    ('location_id.usage', 'not in', ('internal', 'transit')),
                ]),
                groupby=['product_id'], aggregates=['quantity:sum'],
            ) if p
        }
        never_purchased = all_prods.filtered(lambda p: p.id not in purchased_ids)
        m['never_purchased'] = {'count': len(never_purchased), 'ids': never_purchased.ids}

        inv_value = sum(
            float(qty or 0) * (product.standard_price or 0)
            for product, qty, _res in quant_rows if product
        )
        m['working_capital'] = {'value': inv_value}

        fully_reserved = Product.search(pdomain + [('qty_available', '>', 0), ('virtual_available', '<=', 0)])
        m['fully_reserved'] = {'count': len(fully_reserved), 'ids': fully_reserved.ids}

        near_stockout = Product.search(pdomain + [
            ('qty_available', '>', 0),
            ('qty_available', '<=', 5),
        ])
        m['near_stockout'] = {'count': len(near_stockout), 'ids': near_stockout.ids}

        excess = m.get('excess_stock', {}).get('ids') or []
        m['excess_stock'] = m.get('excess_stock', {'count': len(excess), 'ids': excess})

        return m

    @api.model
    def _kpi_catalog(self):
        catalog = super()._kpi_catalog()
        catalog.update({
            'pending_receipts': {'label': _('Recepciones pendientes'), 'icon': 'fa-inbox', 'format': 'count', 'tone': 'warning', 'metric': 'pending_receipts'},
            'available_quantity': {'label': _('Inventario disponible'), 'icon': 'fa-check-square', 'format': 'qty', 'tone': 'success', 'metric': 'available_quantity'},
            'reserved_quantity': {'label': _('Inventario reservado'), 'icon': 'fa-lock', 'format': 'qty', 'tone': 'warning', 'metric': 'reserved_quantity'},
            'products_without_category': {'label': _('Sin categoría'), 'icon': 'fa-folder-open-o', 'format': 'count', 'tone': 'warning', 'metric': 'products_without_category'},
            'never_sold': {'label': _('Nunca vendidos'), 'icon': 'fa-times-circle', 'format': 'count', 'tone': 'neutral', 'metric': 'never_sold'},
            'never_purchased': {'label': _('Nunca comprados'), 'icon': 'fa-shopping-basket', 'format': 'count', 'tone': 'neutral', 'metric': 'never_purchased'},
            'working_capital': {'label': _('Capital de trabajo'), 'icon': 'fa-briefcase', 'format': 'money', 'tone': 'info', 'metric': 'working_capital'},
            'fully_reserved': {'label': _('Reservado totalmente'), 'icon': 'fa-chain', 'format': 'count', 'tone': 'warning', 'metric': 'fully_reserved'},
            'near_stockout': {'label': _('Próximos a agotarse'), 'icon': 'fa-battery-quarter', 'format': 'count', 'tone': 'danger', 'metric': 'near_stockout'},
        })
        return catalog

    @api.model
    def _build_health(self, parsed, metrics):
        health = super()._build_health(parsed, metrics)
        score = health['score']
        if score >= 90:
            status, color, status_key = _('Excelente'), 'excellent', 'excellent'
        elif score >= 75:
            status, color, status_key = _('Saludable'), 'success', 'healthy'
        elif score >= 50:
            status, color, status_key = _('Atención'), 'warning', 'warning'
        else:
            status, color, status_key = _('Crítico'), 'danger', 'critical'
        health.update({
            'status': status,
            'color': color,
            'status_key': status_key,
            'tooltip': _(
                'Puntuación basada en: agotados (-2 c/u), entregas atrasadas (-3), '
                'recepciones atrasadas (-3), inventario negativo (-5), stock muerto, '
                'fill rate, rotación y reservas críticas.'
            ),
        })
        return health

    @api.model
    def _build_alerts(self, parsed, metrics):
        alerts = super()._build_alerts(parsed, metrics)
        extra = [
            ('near_stockout', 'danger', _('Próximos a agotarse')),
            ('excess_stock', 'warning', _('Stock excesivo')),
            ('fully_reserved', 'warning', _('Inventario reservado totalmente')),
            ('critical_stock', 'danger', _('Stock crítico')),
            ('never_sold', 'info', _('Productos nunca vendidos')),
        ]
        existing = {a['key'] for a in alerts}
        for key, level, title in extra:
            cnt = metrics.get(key, {}).get('count', 0)
            if cnt and key not in existing:
                alerts.append({
                    'key': key,
                    'level': level,
                    'title': title,
                    'count': cnt,
                    'description': _('%s registros — impacto operativo detectado.') % cnt,
                    'metric': key,
                    'impact': _('Alto') if level == 'danger' else _('Medio'),
                })
        return sorted(alerts, key=lambda a: {'danger': 0, 'warning': 1, 'info': 2}.get(a['level'], 3))

    @api.model
    def _build_insights(self, parsed, metrics):
        insights = super()._build_insights(parsed, metrics)
        MoveLine = self.env['stock.move.line']
        Picking = self.env['stock.picking']

        slow = MoveLine._read_group(
            domain=self._move_line_domain(parsed),
            groupby=['product_id'], aggregates=['quantity:sum'],
            order='quantity:sum asc', limit=1,
        )
        if slow and slow[0][0]:
            insights.append({
                'icon': 'fa-hourglass-half',
                'text': _('Producto más lento: %s (%s u.)') % (
                    slow[0][0].display_name, round(slow[0][1] or 0, 2),
                ),
            })

        sup_rows = Picking._read_group(
            domain=self._picking_domain(parsed, [
                ('picking_type_code', '=', 'incoming'), ('state', '=', 'done'),
            ]),
            groupby=['partner_id'], aggregates=['__count'],
            order='__count desc', limit=1,
        )
        if sup_rows and sup_rows[0][0]:
            insights.append({
                'icon': 'fa-truck',
                'text': _('Proveedor más eficiente: %s (%s recepciones).') % (
                    sup_rows[0][0].display_name, sup_rows[0][1],
                ),
            })

        overdue_sup = Picking._read_group(
            domain=self._picking_domain(parsed, [
                ('picking_type_code', '=', 'incoming'),
                ('state', 'not in', ('done', 'cancel')),
            ]),
            groupby=['partner_id'], aggregates=['__count'],
            order='__count desc', limit=1,
        )
        if overdue_sup and overdue_sup[0][0]:
            insights.append({
                'icon': 'fa-warning',
                'text': _('Proveedor con más retrasos: %s (%s pendientes).') % (
                    overdue_sup[0][0].display_name, overdue_sup[0][1],
                ),
            })

        return insights[:12]

    @api.model
    def _build_recommendations(self, parsed, metrics):
        recs = super()._build_recommendations(parsed, metrics)
        near = metrics.get('near_stockout', {}).get('count', 0)
        if near:
            recs.insert(0, {
                'level': 'danger',
                'priority': _('Alta'),
                'impact': _('Ruptura de stock en días'),
                'action': _('Generar reabastecimiento'),
                'text': _('%s productos se agotarán pronto — revise reglas de reorden.') % near,
            })
        excess = metrics.get('excess_stock', {}).get('count', 0)
        if excess:
            recs.append({
                'level': 'warning',
                'priority': _('Media'),
                'impact': _('Capital inmovilizado'),
                'action': _('Promoción o transferencia'),
                'text': _('Sobreinventario detectado en %s productos.') % excess,
            })
        return recs

    @api.model
    def _build_activity_feed(self, parsed):
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        feed = []
        pickings = Picking.search(
            self._picking_domain(parsed),
            order='write_date desc, id desc', limit=12,
        )
        for p in pickings:
            icon = 'fa-download' if p.picking_type_code == 'incoming' else (
                'fa-upload' if p.picking_type_code == 'outgoing' else 'fa-exchange'
            )
            feed.append({
                'type': p.picking_type_code or 'internal',
                'title': p.name,
                'subtitle': p.partner_id.display_name if p.partner_id else p.picking_type_id.display_name,
                'datetime': fields.Datetime.to_string(p.date_done or p.scheduled_date or p.create_date),
                'user': p.user_id.name or '',
                'state': p.state,
                'model': 'stock.picking',
                'id': p.id,
                'icon': icon,
            })
        moves = Move.search([
            ('company_id', '=', parsed['company'].id),
            ('state', '=', 'done'),
            ('date', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
        ], order='date desc', limit=5)
        for mv in moves:
            feed.append({
                'type': 'move',
                'title': mv.product_id.display_name,
                'subtitle': _('Movimiento: %s u.') % round(mv.quantity, 2),
                'datetime': fields.Datetime.to_string(mv.date),
                'user': mv.picking_id.user_id.name if mv.picking_id else '',
                'state': mv.state,
                'model': 'stock.move',
                'id': mv.id,
                'icon': 'fa-arrows',
            })
        feed.sort(key=lambda x: x.get('datetime') or '', reverse=True)
        return feed[:15]

    @api.model
    def _build_financial_panel(self, parsed, metrics):
        keys = [
            ('inventory_value', _('Valor total inventario'), 'money'),
            ('available_quantity', _('Inventario disponible (u.)'), 'qty'),
            ('reserved_quantity', _('Inventario reservado (u.)'), 'qty'),
            ('inventory_turnover', _('Inventory turnover'), 'ratio'),
            ('days_of_inventory', _('Days of supply'), 'days'),
            ('holding_cost', _('Holding cost'), 'money'),
            ('working_capital', _('Capital de trabajo'), 'money'),
            ('dead_stock', _('Stock muerto (prod.)'), 'count'),
            ('inventory_accuracy', _('Exactitud inventario'), 'percent'),
            ('fill_rate', _('Fill rate'), 'percent'),
            ('otif', _('OTIF'), 'percent'),
            ('average_cost', _('Costo promedio'), 'money'),
        ]
        items = []
        for key, label, fmt in keys:
            val = self._metric_value(key, metrics)
            items.append({
                'key': key, 'label': label, 'value': val, 'format': fmt, 'metric': key,
            })
        return {'title': _('Dashboard financiero de inventario'), 'items': items}

    @api.model
    def _quick_actions(self):
        actions = super()._quick_actions()
        actions.extend([
            {'key': 'sale_rfq', 'label': _('Solicitud cotización'), 'icon': 'fa-file-text-o', 'model': 'sale.order', 'view': 'form'},
            {'key': 'replenish', 'label': _('Reabastecer'), 'icon': 'fa-plus-circle', 'model': 'stock.warehouse.orderpoint', 'view': 'list'},
            {'key': 'validate_picking', 'label': _('Validar picking'), 'icon': 'fa-check', 'model': 'stock.picking', 'view': 'list', 'context': {'search_default_ready': 1}},
        ])
        return actions

    @api.model
    def _drilldown_action(self, parsed, metric, extra_domain):
        model_map = {
            'pending_receipts': 'stock.picking',
            'available_quantity': 'stock.quant',
            'products_without_category': 'product.product',
            'never_sold': 'product.product',
            'never_purchased': 'product.product',
            'working_capital': 'product.product',
            'fully_reserved': 'product.product',
            'near_stockout': 'product.product',
        }
        action = super()._drilldown_action(parsed, metric, extra_domain)
        if metric in model_map:
            action['res_model'] = model_map[metric]
        return action
