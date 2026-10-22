# -*- coding: utf-8 -*-
"""Servicio RPC del Inventory Dashboard Premium (ORM optimizado)."""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

DONE_STATES = ('done',)
OPEN_PICKING_STATES = ('confirmed', 'assigned', 'waiting', 'partially_available')
PERIOD_PRESETS = (
    'today', 'yesterday', 'this_week', 'this_month',
    'last_30', 'last_90', 'this_year', 'custom',
)


class InventoryDashboardService(models.AbstractModel):
    _name = 'inventory.dashboard.service'
    _description = 'Inventory Dashboard Premium Data Service'

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @api.model
    def _check_dashboard_access(self):
        if not self.env.user.has_group(
            'dev_advance_inventory_dashboard.group_allow_access_inventory'
        ):
            raise AccessError(_('No tiene permiso para acceder al Dashboard de Inventario.'))

    @api.model
    def _can_read(self, model_name):
        try:
            self.env[model_name].check_access('read')
            return True
        except AccessError:
            return False

    # ------------------------------------------------------------------
    # Public RPC
    # ------------------------------------------------------------------

    @api.model
    def get_filter_options(self):
        self._check_dashboard_access()
        company = self.env.company
        warehouses = self.env['stock.warehouse'].search([
            ('company_id', 'in', self.env.companies.ids),
        ], order='name', limit=200)
        branches = []
        if 'branch_id' in self.env['stock.picking']._fields:
            branches = self.env['res.branch'].search([
                ('company_id', 'in', self.env.companies.ids),
            ], order='name', limit=200)
        locations = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', 'in', self.env.companies.ids),
        ], order='complete_name', limit=300)
        categories = self.env['product.category'].search([], order='complete_name', limit=200)
        operation_types = self.env['stock.picking.type'].search([
            ('company_id', 'in', self.env.companies.ids),
        ], order='sequence, name', limit=100)
        users = self.env['res.users'].search([
            ('company_ids', 'in', company.id),
            ('share', '=', False),
        ], order='name', limit=200)
        suppliers = self.env['res.partner'].search([
            ('supplier_rank', '>', 0),
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
        ], order='name', limit=200)
        customers = self.env['res.partner'].search([
            ('customer_rank', '>', 0),
            '|', ('company_id', '=', False), ('company_id', '=', company.id),
        ], order='name', limit=200)
        today = fields.Date.context_today(self)
        return {
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
            'multi_company': len(self.env.companies) > 1,
            'warehouses': [{'id': w.id, 'name': w.name} for w in warehouses],
            'branches': [{'id': b.id, 'name': b.name} for b in branches],
            'locations': [{'id': l.id, 'name': l.complete_name} for l in locations],
            'categories': [{'id': c.id, 'name': c.complete_name} for c in categories],
            'operation_types': [{'id': t.id, 'name': t.display_name} for t in operation_types],
            'users': [{'id': u.id, 'name': u.name} for u in users],
            'suppliers': [{'id': p.id, 'name': p.display_name} for p in suppliers],
            'customers': [{'id': p.id, 'name': p.display_name} for p in customers],
            'period_presets': self._period_preset_options(),
            'date_from': fields.Date.to_string(today.replace(day=1)),
            'date_to': fields.Date.to_string(today),
            'currency_symbol': company.currency_id.symbol or '$',
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        """Payload consolidado para minimizar round-trips RPC."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        prev = self._previous_parsed(parsed)
        current = self._compute_metrics(parsed)
        previous = self._compute_metrics(prev)
        return {
            'filters': self._filters_payload(parsed),
            'header': self._build_header(parsed),
            'health': self._build_health(parsed, current),
            'kpis': self._build_kpis(parsed, current, previous),
            'alerts': self._build_alerts(parsed, current),
            'insights': self._build_insights(parsed, current),
            'recommendations': self._build_recommendations(parsed, current),
            'charts': self._build_charts(parsed, current),
            'tables': self._build_tables(parsed, filters or {}),
            'quick_actions': self._quick_actions(),
            'updated_at': fields.Datetime.now().isoformat(),
        }

    @api.model
    def get_table_page(self, filters, table_key, page=1, page_size=10, search='', order=''):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        return self._table_page(parsed, table_key, page, page_size, search, order)

    @api.model
    def save_user_layout(self, layout_id, name, layout_json, is_default=False):
        return self.env['inventory.dashboard.layout'].save_layout(
            layout_id, name, layout_json, is_default,
        )

    @api.model
    def get_user_layouts(self):
        return self.env['inventory.dashboard.layout'].get_layouts()

    @api.model
    def reset_user_layout(self, layout_id=None):
        return self.env['inventory.dashboard.layout'].reset_layout(layout_id)

    @api.model
    def get_drilldown_action(self, metric, extra_domain=None, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        return self._drilldown_action(parsed, metric, extra_domain or [])

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    @api.model
    def _period_preset_options(self):
        return [
            {'id': 'today', 'name': _('Hoy')},
            {'id': 'yesterday', 'name': _('Ayer')},
            {'id': 'this_week', 'name': _('Esta semana')},
            {'id': 'this_month', 'name': _('Este mes')},
            {'id': 'last_30', 'name': _('Últimos 30 días')},
            {'id': 'last_90', 'name': _('Últimos 90 días')},
            {'id': 'this_year', 'name': _('Este año')},
            {'id': 'custom', 'name': _('Personalizado')},
        ]

    @api.model
    def _resolve_period(self, filters):
        today = fields.Date.context_today(self)
        preset = filters.get('period') or 'this_month'
        if preset not in PERIOD_PRESETS:
            preset = 'this_month'
        if preset == 'custom':
            date_from = filters.get('date_from') or fields.Date.to_string(today.replace(day=1))
            date_to = filters.get('date_to') or fields.Date.to_string(today)
            date_from = fields.Date.from_string(date_from) if isinstance(date_from, str) else date_from
            date_to = fields.Date.from_string(date_to) if isinstance(date_to, str) else date_to
        elif preset == 'today':
            date_from = date_to = today
        elif preset == 'yesterday':
            date_from = date_to = today - timedelta(days=1)
        elif preset == 'this_week':
            date_from = today - timedelta(days=today.weekday())
            date_to = today
        elif preset == 'this_month':
            date_from = today.replace(day=1)
            date_to = today
        elif preset == 'last_30':
            date_from = today - timedelta(days=29)
            date_to = today
        elif preset == 'last_90':
            date_from = today - timedelta(days=89)
            date_to = today
        else:  # this_year
            date_from = today.replace(month=1, day=1)
            date_to = today
        if date_from > date_to:
            raise UserError(_('La fecha inicial no puede ser posterior a la final.'))
        return preset, date_from, date_to

    @api.model
    def _parse_filters(self, filters):
        company_id = filters.get('company_id') or self.env.company.id
        company = self.env['res.company'].browse(company_id)
        if company.id not in self.env.companies.ids:
            company = self.env.company
        preset, date_from, date_to = self._resolve_period(filters)
        return {
            'company': company,
            'branch_id': filters.get('branch_id') or False,
            'warehouse_id': filters.get('warehouse_id') or False,
            'location_id': filters.get('location_id') or False,
            'category_id': filters.get('category_id') or False,
            'product_id': filters.get('product_id') or False,
            'supplier_id': filters.get('supplier_id') or False,
            'customer_id': filters.get('customer_id') or False,
            'responsible_id': filters.get('responsible_id') or False,
            'operation_type_id': filters.get('operation_type_id') or False,
            'period': preset,
            'date_from': date_from,
            'date_to': date_to,
        }

    @api.model
    def _previous_parsed(self, parsed):
        delta = (parsed['date_to'] - parsed['date_from']).days + 1
        prev_end = parsed['date_from'] - timedelta(days=1)
        prev_start = prev_end - timedelta(days=delta - 1)
        return {**parsed, 'date_from': prev_start, 'date_to': prev_end}

    @api.model
    def _filters_payload(self, parsed):
        wh_name = _('Todos')
        if parsed['warehouse_id']:
            wh = self.env['stock.warehouse'].browse(parsed['warehouse_id'])
            wh_name = wh.display_name
        branch_name = _('Todas')
        if parsed.get('branch_id'):
            branch = self.env['res.branch'].browse(parsed['branch_id'])
            if branch.exists():
                branch_name = branch.name
        return {
            'company_id': parsed['company'].id,
            'branch_id': parsed.get('branch_id') or False,
            'branch_name': branch_name,
            'warehouse_id': parsed['warehouse_id'],
            'warehouse_name': wh_name,
            'period': parsed['period'],
            'date_from': fields.Date.to_string(parsed['date_from']),
            'date_to': fields.Date.to_string(parsed['date_to']),
        }

    @api.model
    def _warehouse_locations(self, warehouse_id):
        if not warehouse_id:
            return []
        wh = self.env['stock.warehouse'].browse(warehouse_id)
        if not wh.exists():
            return []
        return self.env['stock.location'].search([
            ('id', 'child_of', wh.view_location_id.id),
            ('usage', '=', 'internal'),
        ]).ids

    @api.model
    def _has_branch_filter(self):
        return 'branch_id' in self.env['stock.picking']._fields

    @api.model
    def _picking_done_domain(self, parsed, extra=None):
        """Pickings validados por ``date_done`` dentro del periodo."""
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('date_done', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
            ('date_done', '<',
             fields.Datetime.to_datetime(parsed['date_to'] + timedelta(days=1))),
        ]
        if parsed.get('branch_id') and self._has_branch_filter():
            domain.append(('branch_id', '=', parsed['branch_id']))
        if parsed['warehouse_id']:
            domain.append(('picking_type_id.warehouse_id', '=', parsed['warehouse_id']))
        if parsed['operation_type_id']:
            domain.append(('picking_type_id', '=', parsed['operation_type_id']))
        if parsed['responsible_id']:
            domain.append(('user_id', '=', parsed['responsible_id']))
        if parsed['product_id']:
            domain.append(('move_ids.product_id', '=', parsed['product_id']))
        if extra:
            domain.extend(extra)
        return domain

    @api.model
    def _product_domain(self, parsed, extra=None):
        domain = [
            ('is_storable', '=', True),
            ('company_id', 'in', (False, parsed['company'].id)),
        ]
        if parsed['category_id']:
            domain.append(('categ_id', 'child_of', parsed['category_id']))
        if parsed['product_id']:
            domain.append(('id', '=', parsed['product_id']))
        if parsed['supplier_id']:
            domain.append(('seller_ids.partner_id', '=', parsed['supplier_id']))
        if extra:
            domain.extend(extra)
        return domain

    @api.model
    def _picking_domain(self, parsed, extra=None):
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('scheduled_date', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
            ('scheduled_date', '<',
             fields.Datetime.to_datetime(parsed['date_to'] + timedelta(days=1))),
        ]
        if parsed.get('branch_id') and self._has_branch_filter():
            domain.append(('branch_id', '=', parsed['branch_id']))
        if parsed['warehouse_id']:
            domain.append(('picking_type_id.warehouse_id', '=', parsed['warehouse_id']))
        if parsed['operation_type_id']:
            domain.append(('picking_type_id', '=', parsed['operation_type_id']))
        if parsed['responsible_id']:
            domain.append(('user_id', '=', parsed['responsible_id']))
        if parsed['product_id']:
            domain.append(('move_ids.product_id', '=', parsed['product_id']))
        if parsed['supplier_id']:
            domain += [
                ('picking_type_code', '=', 'incoming'),
                ('partner_id', '=', parsed['supplier_id']),
            ]
        if parsed['customer_id']:
            domain += [
                ('picking_type_code', '=', 'outgoing'),
                ('partner_id', '=', parsed['customer_id']),
            ]
        if extra:
            domain.extend(extra)
        return domain

    @api.model
    def _move_line_domain(self, parsed, extra=None):
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('state', '=', 'done'),
            ('date', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
            ('date', '<',
             fields.Datetime.to_datetime(parsed['date_to'] + timedelta(days=1))),
        ]
        if parsed.get('branch_id') and self._has_branch_filter():
            domain.append(('picking_id.branch_id', '=', parsed['branch_id']))
        if parsed['warehouse_id']:
            loc_ids = self._warehouse_locations(parsed['warehouse_id'])
            if loc_ids:
                domain += ['|',
                           ('location_id', 'in', loc_ids),
                           ('location_dest_id', 'in', loc_ids)]
        if parsed['location_id']:
            domain += ['|',
                       ('location_id', '=', parsed['location_id']),
                       ('location_dest_id', '=', parsed['location_id'])]
        if parsed['product_id']:
            domain.append(('product_id', '=', parsed['product_id']))
        if parsed['category_id']:
            domain.append(('product_id.categ_id', 'child_of', parsed['category_id']))
        if extra:
            domain.extend(extra)
        return domain

    @api.model
    def _quant_domain(self, parsed, extra=None):
        domain = [('location_id.usage', '=', 'internal')]
        domain.append(('company_id', '=', parsed['company'].id))
        if parsed.get('branch_id') and self._has_branch_filter():
            domain.append(('location_id.branch_id', '=', parsed['branch_id']))
        if parsed['warehouse_id']:
            loc_ids = self._warehouse_locations(parsed['warehouse_id'])
            if loc_ids:
                domain.append(('location_id', 'in', loc_ids))
        if parsed['location_id']:
            domain.append(('location_id', '=', parsed['location_id']))
        if parsed['product_id']:
            domain.append(('product_id', '=', parsed['product_id']))
        if parsed['category_id']:
            domain.append(('product_id.categ_id', 'child_of', parsed['category_id']))
        if extra:
            domain.extend(extra)
        return domain

    # ------------------------------------------------------------------
    # Metrics core
    # ------------------------------------------------------------------

    @api.model
    def _compute_metrics(self, parsed):
        today = fields.Date.context_today(self)
        m = defaultdict(lambda: {'value': 0.0, 'count': 0, 'ids': []})
        Product = self.env['product.product']
        Picking = self.env['stock.picking']
        Quant = self.env['stock.quant']
        Move = self.env['stock.move']
        MoveLine = self.env['stock.move.line']
        Purchase = self.env['purchase.order']

        pdomain = self._product_domain(parsed)
        pk_in = self._picking_domain(parsed, [('picking_type_code', '=', 'incoming')])
        pk_out = self._picking_domain(parsed, [('picking_type_code', '=', 'outgoing')])

        # Pickings abiertos (recepciones O entregas, no AND imposible)
        open_pk = Picking.search(
            self._picking_domain(parsed, [
                ('picking_type_code', 'in', ('incoming', 'outgoing')),
                ('state', 'in', OPEN_PICKING_STATES),
            ])
        )
        m['open_pickings']['count'] = len(open_pk)
        m['open_pickings']['ids'] = open_pk.ids

        overdue = Picking.search(
            self._picking_domain(parsed, [
                ('scheduled_date', '<', fields.Datetime.to_datetime(today)),
                ('state', 'not in', [*DONE_STATES, 'cancel']),
            ])
        )
        m['overdue_pickings']['count'] = len(overdue)
        m['overdue_pickings']['ids'] = overdue.ids

        awaiting_del = Picking.search(pk_out + [
            ('state', 'in', OPEN_PICKING_STATES),
        ])
        m['awaiting_deliveries']['count'] = len(awaiting_del)
        m['awaiting_deliveries']['ids'] = awaiting_del.ids

        overdue_del = Picking.search(pk_out + [
            ('scheduled_date', '<', fields.Datetime.to_datetime(today)),
            ('state', 'not in', [*DONE_STATES, 'cancel']),
        ])
        m['overdue_deliveries']['count'] = len(overdue_del)
        m['overdue_deliveries']['ids'] = overdue_del.ids

        receipts_today = Picking.search(
            self._picking_domain({**parsed, 'date_from': today, 'date_to': today}, [
                ('picking_type_code', '=', 'incoming'),
            ])
        )
        m['receipts_today']['count'] = len(receipts_today)
        m['receipts_today']['ids'] = receipts_today.ids

        deliveries_today = Picking.search(
            self._picking_domain({**parsed, 'date_from': today, 'date_to': today}, [
                ('picking_type_code', '=', 'outgoing'),
            ])
        )
        m['deliveries_today']['count'] = len(deliveries_today)
        m['deliveries_today']['ids'] = deliveries_today.ids

        overdue_rec = Picking.search(
            self._picking_domain(parsed, [
                ('picking_type_code', '=', 'incoming'),
                ('scheduled_date', '<', fields.Datetime.to_datetime(today)),
                ('state', 'not in', [*DONE_STATES, 'cancel']),
            ])
        )
        m['overdue_receipts']['count'] = len(overdue_rec)
        m['overdue_receipts']['ids'] = overdue_rec.ids

        # Products
        quant_rows = Quant._read_group(
            domain=self._quant_domain(parsed),
            groupby=['product_id'],
            aggregates=['quantity:sum', 'reserved_quantity:sum', 'id:recordset'],
        )
        use_branch_products = bool(parsed.get('branch_id') and self._has_branch_filter())
        if use_branch_products:
            oos_ids = [
                product.id for product, qty_sum, _res, _recs in quant_rows
                if product and (qty_sum or 0) <= 0
            ]
            avail_ids = [
                product.id for product, qty_sum, _res, _recs in quant_rows
                if product and (qty_sum or 0) > 0
            ]
            m['out_of_stock']['count'] = len(oos_ids)
            m['out_of_stock']['ids'] = oos_ids
            m['available_products']['count'] = len(avail_ids)
            m['available_products']['ids'] = avail_ids
            m['total_products']['count'] = len({
                product.id for product, _q, _r, _recs in quant_rows if product
            })
        else:
            out_stock = Product.search(pdomain + [('qty_available', '<=', 0)])
            m['out_of_stock']['count'] = len(out_stock)
            m['out_of_stock']['ids'] = out_stock.ids

            available = Product.search(pdomain + [('qty_available', '>', 0)])
            m['available_products']['count'] = len(available)
            m['available_products']['ids'] = available.ids

            total_products = Product.search_count(pdomain)
            m['total_products']['count'] = total_products

        negative = Quant.search(self._quant_domain(parsed, [('quantity', '<', 0)]))
        m['negative_inventory']['count'] = len(negative)
        m['negative_inventory']['ids'] = negative.ids

        reserved = Product.search(pdomain + [('virtual_available', '<', 0)])
        m['reserved_products']['count'] = len(reserved)
        m['reserved_products']['ids'] = reserved.ids

        # Stock quantities via quants (quant_rows ya calculado arriba)
        total_qty = sum(float(q or 0) for _, q, _, _ in quant_rows)
        total_reserved = sum(float(r or 0) for _, _, r, _ in quant_rows)
        m['stock_quantity']['value'] = total_qty
        m['reserved_quantity']['value'] = total_reserved

        incoming_rows = MoveLine._read_group(
            domain=self._move_line_domain(parsed, [
                ('picking_id.picking_type_code', '=', 'incoming'),
            ]),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
        )
        outgoing_rows = MoveLine._read_group(
            domain=self._move_line_domain(parsed, [
                ('picking_id.picking_type_code', '=', 'outgoing'),
            ]),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
        )
        m['incoming_quantity']['value'] = sum(float(r[1] or 0) for r in incoming_rows)
        m['outgoing_quantity']['value'] = sum(float(r[1] or 0) for r in outgoing_rows)

        # Inventory value
        inv_value = 0.0
        avg_cost_sum = 0.0
        avg_cost_cnt = 0
        for product, qty_sum, _res, _recs in quant_rows:
            if not product:
                continue
            cost = product.standard_price or 0.0
            inv_value += (qty_sum or 0) * cost
            if cost:
                avg_cost_sum += cost
                avg_cost_cnt += 1
        m['inventory_value']['value'] = inv_value
        m['average_cost']['value'] = avg_cost_sum / avg_cost_cnt if avg_cost_cnt else 0.0

        # Purchase
        po_waiting = Purchase.search([
            ('company_id', '=', parsed['company'].id),
            ('state', 'in', ('draft', 'sent', 'to approve')),
        ])
        m['purchase_orders_waiting']['count'] = len(po_waiting)
        m['purchase_orders_waiting']['ids'] = po_waiting.ids

        backorders = Picking.search(self._picking_domain(parsed, [('backorder_id', '!=', False)]))
        m['backorders']['count'] = len(backorders)
        m['backorders']['ids'] = backorders.ids

        # Data quality
        no_vendor = Product.search(pdomain + [('seller_ids', '=', False)])
        m['products_without_vendor']['count'] = len(no_vendor)
        m['products_without_vendor']['ids'] = no_vendor.ids

        no_barcode = Product.search(pdomain + ['|', ('barcode', '=', False), ('barcode', '=', '')])
        m['products_without_barcode']['count'] = len(no_barcode)
        m['products_without_barcode']['ids'] = no_barcode.ids

        no_cost = Product.search(pdomain + [('standard_price', '<=', 0)])
        m['products_without_cost']['count'] = len(no_cost)
        m['products_without_cost']['ids'] = no_cost.ids

        # Movement classification (90-day window for dead/slow/fast)
        analysis_end = parsed['date_to']
        analysis_start = analysis_end - timedelta(days=90)
        move_domain = [
            ('company_id', '=', parsed['company'].id),
            ('state', '=', 'done'),
            ('date', '>=', fields.Datetime.to_datetime(analysis_start)),
            ('date', '<=', fields.Datetime.to_datetime(analysis_end + timedelta(days=1))),
        ]
        if parsed['warehouse_id']:
            loc_ids = self._warehouse_locations(parsed['warehouse_id'])
            if loc_ids:
                move_domain += ['|', ('location_id', 'in', loc_ids), ('location_dest_id', 'in', loc_ids)]
        if parsed.get('branch_id') and self._has_branch_filter():
            move_domain.append(('picking_id.branch_id', '=', parsed['branch_id']))
        moved_products = {
            row[0].id for row in MoveLine._read_group(
                domain=move_domain, groupby=['product_id'], aggregates=['__count'],
            ) if row[0]
        }
        all_stocked = Product.search(pdomain + [('qty_available', '>', 0)])
        dead = all_stocked.filtered(lambda p: p.id not in moved_products)
        m['dead_stock']['count'] = len(dead)
        m['dead_stock']['ids'] = dead.ids

        # Turnover approximation
        cogs_qty = sum(
            row[1] or 0 for row in MoveLine._read_group(
                domain=self._move_line_domain(parsed, [
                    ('location_dest_id.usage', 'not in', ('internal', 'transit')),
                ]),
                groupby=['product_id'],
                aggregates=['quantity:sum'],
            )
        )
        avg_inv = inv_value or 1.0
        m['inventory_turnover']['value'] = round(cogs_qty / avg_inv, 2) if avg_inv else 0.0
        daily_usage = cogs_qty / max((parsed['date_to'] - parsed['date_from']).days + 1, 1)
        m['days_of_inventory']['value'] = round(total_qty / daily_usage, 1) if daily_usage else 0.0

        # Fill rate / OTIF / nivel de servicio (métricas operativas reales)
        out_picking_ids = Picking.search(
            pk_out + [('state', '!=', 'cancel')]
        ).ids
        out_moves = Move.search([
            ('picking_id', 'in', out_picking_ids or [0]),
            ('state', '!=', 'cancel'),
        ]) if out_picking_ids else Move.browse()
        demanded = sum(out_moves.mapped('product_uom_qty'))
        fulfilled = sum(
            move.quantity or 0.0
            for move in out_moves.filtered(lambda mv: mv.state == 'done')
        )
        m['fill_rate']['value'] = round(
            fulfilled / demanded * 100, 1,
        ) if demanded else 100.0

        done_out = Picking.search(
            self._picking_done_domain(parsed, [
                ('picking_type_code', '=', 'outgoing'),
                ('state', '=', 'done'),
            ])
        )
        on_time = done_out.filtered(
            lambda p: p.date_done and p.scheduled_date and p.date_done <= p.scheduled_date
        )
        m['otif']['value'] = round(
            len(on_time) / len(done_out) * 100, 1,
        ) if done_out else 100.0

        no_backorder = done_out.filtered(lambda p: not p.backorder_id)
        m['service_level']['value'] = round(
            len(no_backorder) / len(done_out) * 100, 1,
        ) if done_out else 100.0

        # Picking times (hours)
        done_pickings = Picking.search(
            self._picking_domain(parsed, [('state', '=', 'done')]), limit=500,
        )
        durations = []
        for p in done_pickings:
            if p.date_done and p.scheduled_date:
                delta = p.date_done - p.scheduled_date
                durations.append(abs(delta.total_seconds()) / 3600.0)
        m['average_picking_time']['value'] = round(sum(durations) / len(durations), 1) if durations else 0.0
        out_done = done_pickings.filtered(lambda p: p.picking_type_code == 'outgoing')
        out_dur = []
        for p in out_done:
            if p.date_done and p.scheduled_date:
                out_dur.append(abs((p.date_done - p.scheduled_date).total_seconds()) / 3600.0)
        m['average_delivery_time']['value'] = round(sum(out_dur) / len(out_dur), 1) if out_dur else 0.0

        # Warehouse occupancy (reserved vs on hand)
        m['warehouse_occupancy']['value'] = round(
            total_reserved / total_qty * 100, 1,
        ) if total_qty else 0.0

        m['holding_cost']['value'] = inv_value * 0.25 / 12  # 25% anual simplificado
        m['inventory_accuracy']['value'] = max(
            0.0, 100.0 - m['negative_inventory']['count'] * 2,
        )

        return dict(m)

    # ------------------------------------------------------------------
    # Presentation builders
    # ------------------------------------------------------------------

    @api.model
    def _build_header(self, parsed):
        user = self.env.user
        wh_name = _('Todos los almacenes')
        if parsed['warehouse_id']:
            wh_name = self.env['stock.warehouse'].browse(parsed['warehouse_id']).display_name
        branch_name = ''
        if parsed.get('branch_id'):
            branch = self.env['res.branch'].browse(parsed['branch_id'])
            if branch.exists():
                branch_name = branch.name
        hour = datetime.now().hour
        if hour < 12:
            greeting = _('Buenos días')
        elif hour < 18:
            greeting = _('Buenas tardes')
        else:
            greeting = _('Buenas noches')
        return {
            'user_name': user.name,
            'user_id': user.id,
            'user_img': bool(user.image_128),
            'company_id': parsed['company'].id,
            'company_has_logo': bool(parsed['company'].logo),
            'greeting': greeting,
            'company_name': parsed['company'].name,
            'warehouse_name': wh_name,
            'branch_name': branch_name,
            'today': fields.Date.to_string(fields.Date.context_today(self)),
            'connected_users': self.env['res.users'].search_count([('login_date', '!=', False)]),
        }

    @api.model
    def _build_health(self, parsed, metrics):
        score = 100.0
        total_ops = max(metrics.get('open_pickings', {}).get('count', 0), 1)
        score -= min(25, metrics.get('out_of_stock', {}).get('count', 0) * 2)
        score -= min(20, metrics.get('overdue_deliveries', {}).get('count', 0) * 3)
        score -= min(15, metrics.get('overdue_receipts', {}).get('count', 0) * 3)
        score -= min(15, metrics.get('negative_inventory', {}).get('count', 0) * 5)
        score -= min(10, metrics.get('dead_stock', {}).get('count', 0))
        score -= min(10, max(0, 100 - metrics.get('fill_rate', {}).get('value', 100)) * 0.2)
        turnover = metrics.get('inventory_turnover', {}).get('value', 0)
        if turnover < 1:
            score -= 5
        score = max(0, min(100, round(score)))
        if score >= 75:
            status, color = _('Saludable'), 'success'
        elif score >= 50:
            status, color = _('Atención'), 'warning'
        else:
            status, color = _('Crítico'), 'danger'
        return {
            'score': score,
            'status': status,
            'color': color,
            'factors': [
                {'label': _('Agotados'), 'value': metrics.get('out_of_stock', {}).get('count', 0)},
                {'label': _('Entregas atrasadas'), 'value': metrics.get('overdue_deliveries', {}).get('count', 0)},
                {'label': _('Recepciones atrasadas'), 'value': metrics.get('overdue_receipts', {}).get('count', 0)},
                {'label': _('Inventario negativo'), 'value': metrics.get('negative_inventory', {}).get('count', 0)},
                {'label': _('Rotación'), 'value': turnover},
                {'label': _('Fill rate'), 'value': metrics.get('fill_rate', {}).get('value', 0)},
            ],
        }

    @api.model
    def _kpi_catalog(self):
        return {
            'open_pickings': {'label': _('Pickings abiertos'), 'icon': 'fa-cubes', 'format': 'count', 'tone': 'info', 'metric': 'open_pickings'},
            'overdue_pickings': {'label': _('Pickings atrasados'), 'icon': 'fa-clock-o', 'format': 'count', 'tone': 'danger', 'metric': 'overdue_pickings'},
            'awaiting_deliveries': {'label': _('Entregas pendientes'), 'icon': 'fa-truck', 'format': 'count', 'tone': 'warning', 'metric': 'awaiting_deliveries'},
            'overdue_deliveries': {'label': _('Entregas atrasadas'), 'icon': 'fa-exclamation-triangle', 'format': 'count', 'tone': 'danger', 'metric': 'overdue_deliveries'},
            'out_of_stock': {'label': _('Productos agotados'), 'icon': 'fa-ban', 'format': 'count', 'tone': 'danger', 'metric': 'out_of_stock'},
            'negative_inventory': {'label': _('Inventario negativo'), 'icon': 'fa-minus-circle', 'format': 'count', 'tone': 'danger', 'metric': 'negative_inventory'},
            'reserved_products': {'label': _('Productos reservados'), 'icon': 'fa-lock', 'format': 'count', 'tone': 'warning', 'metric': 'reserved_products'},
            'available_products': {'label': _('Productos disponibles'), 'icon': 'fa-check-circle', 'format': 'count', 'tone': 'success', 'metric': 'available_products'},
            'inventory_value': {'label': _('Valor de inventario'), 'icon': 'fa-money', 'format': 'money', 'tone': 'info', 'metric': 'inventory_value'},
            'average_cost': {'label': _('Costo promedio'), 'icon': 'fa-calculator', 'format': 'money', 'tone': 'neutral', 'metric': 'average_cost'},
            'total_products': {'label': _('Total productos'), 'icon': 'fa-cube', 'format': 'count', 'tone': 'neutral', 'metric': 'total_products'},
            'stock_quantity': {'label': _('Cantidad en stock'), 'icon': 'fa-database', 'format': 'qty', 'tone': 'info', 'metric': 'stock_quantity'},
            'incoming_quantity': {'label': _('Cantidad entrante'), 'icon': 'fa-sign-in', 'format': 'qty', 'tone': 'success', 'metric': 'incoming_quantity'},
            'outgoing_quantity': {'label': _('Cantidad saliente'), 'icon': 'fa-sign-out', 'format': 'qty', 'tone': 'warning', 'metric': 'outgoing_quantity'},
            'receipts_today': {'label': _('Recepciones hoy'), 'icon': 'fa-download', 'format': 'count', 'tone': 'success', 'metric': 'receipts_today'},
            'deliveries_today': {'label': _('Entregas hoy'), 'icon': 'fa-upload', 'format': 'count', 'tone': 'info', 'metric': 'deliveries_today'},
            'purchase_orders_waiting': {'label': _('OC en espera'), 'icon': 'fa-shopping-cart', 'format': 'count', 'tone': 'warning', 'metric': 'purchase_orders_waiting'},
            'backorders': {'label': _('Backorders'), 'icon': 'fa-undo', 'format': 'count', 'tone': 'warning', 'metric': 'backorders'},
            'average_picking_time': {'label': _('Tiempo promedio picking (h)'), 'icon': 'fa-hourglass-half', 'format': 'hours', 'tone': 'neutral', 'metric': 'average_picking_time'},
            'average_delivery_time': {'label': _('Tiempo promedio entrega (h)'), 'icon': 'fa-hourglass-end', 'format': 'hours', 'tone': 'neutral', 'metric': 'average_delivery_time'},
            'warehouse_occupancy': {'label': _('Ocupación almacén'), 'icon': 'fa-building', 'format': 'percent', 'tone': 'info', 'metric': 'warehouse_occupancy'},
            'products_without_vendor': {'label': _('Sin proveedor'), 'icon': 'fa-user-times', 'format': 'count', 'tone': 'warning', 'metric': 'products_without_vendor'},
            'products_without_barcode': {'label': _('Sin código de barras'), 'icon': 'fa-barcode', 'format': 'count', 'tone': 'warning', 'metric': 'products_without_barcode'},
            'products_without_cost': {'label': _('Sin costo'), 'icon': 'fa-usd', 'format': 'count', 'tone': 'warning', 'metric': 'products_without_cost'},
            'dead_stock': {'label': _('Stock muerto'), 'icon': 'fa-archive', 'format': 'count', 'tone': 'danger', 'metric': 'dead_stock'},
            'inventory_turnover': {'label': _('Rotación de inventario'), 'icon': 'fa-refresh', 'format': 'ratio', 'tone': 'info', 'metric': 'inventory_turnover'},
            'days_of_inventory': {'label': _('Días de inventario'), 'icon': 'fa-calendar', 'format': 'days', 'tone': 'info', 'metric': 'days_of_inventory'},
            'holding_cost': {'label': _('Costo de mantener'), 'icon': 'fa-bank', 'format': 'money', 'tone': 'warning', 'metric': 'holding_cost'},
            'inventory_accuracy': {'label': _('Precisión de inventario'), 'icon': 'fa-bullseye', 'format': 'percent', 'tone': 'success', 'metric': 'inventory_accuracy'},
            'service_level': {'label': _('Nivel de servicio'), 'icon': 'fa-line-chart', 'format': 'percent', 'tone': 'success', 'metric': 'service_level'},
            'fill_rate': {'label': _('Fill rate'), 'icon': 'fa-pie-chart', 'format': 'percent', 'tone': 'success', 'metric': 'fill_rate'},
            'otif': {'label': _('OTIF'), 'icon': 'fa-check-square-o', 'format': 'percent', 'tone': 'success', 'metric': 'otif'},
        }

    @api.model
    def _metric_value(self, key, data):
        row = data.get(key, {})
        if row.get('value') is not None and row.get('value') != 0:
            return row['value']
        return row.get('count', 0)

    @api.model
    def _variation(self, cur, prev):
        if not prev:
            return 100.0 if cur else 0.0
        return round((cur - prev) / abs(prev) * 100.0, 1)

    @api.model
    def _sparkline(self, cur_val):
        return [max(0, float(cur_val or 0) * f) for f in (0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 1.0)]

    @api.model
    def _build_kpis(self, parsed, current, previous):
        catalog = self._kpi_catalog()
        items = []
        for key, meta in catalog.items():
            cur_val = self._metric_value(key, current)
            prev_val = self._metric_value(key, previous)
            var = self._variation(cur_val, prev_val)
            items.append({
                'key': key,
                'label': meta['label'],
                'icon': meta['icon'],
                'tone': meta['tone'],
                'format': meta['format'],
                'metric': meta['metric'],
                'value': cur_val,
                'count': current.get(key, {}).get('count', 0),
                'variation_pct': var,
                'trend': 'up' if var > 0.5 else ('down' if var < -0.5 else 'flat'),
                'sparkline': self._sparkline(cur_val),
            })
        return items

    @api.model
    def _build_alerts(self, parsed, metrics):
        defs = [
            ('out_of_stock', 'danger', _('Productos agotados')),
            ('negative_inventory', 'danger', _('Inventario negativo')),
            ('overdue_receipts', 'warning', _('Recepciones atrasadas')),
            ('overdue_deliveries', 'warning', _('Entregas atrasadas')),
            ('backorders', 'warning', _('Pedidos bloqueados / backorders')),
            ('products_without_vendor', 'warning', _('Productos sin proveedor')),
            ('products_without_barcode', 'info', _('Productos sin código de barras')),
            ('products_without_cost', 'info', _('Productos sin costo')),
            ('dead_stock', 'warning', _('Stock muerto')),
            ('reserved_products', 'info', _('Inventario reservado crítico')),
        ]
        alerts = []
        for key, level, title in defs:
            cnt = metrics.get(key, {}).get('count', 0)
            if cnt:
                alerts.append({
                    'key': key,
                    'level': level,
                    'title': title,
                    'count': cnt,
                    'description': _('%s registros requieren atención.') % cnt,
                    'metric': key,
                })
        return alerts

    @api.model
    def _build_insights(self, parsed, metrics):
        MoveLine = self.env['stock.move.line']
        Product = self.env['product.product']
        Picking = self.env['stock.picking']
        insights = []

        top_sold = MoveLine._read_group(
            domain=self._move_line_domain(parsed, [
                ('location_dest_id.usage', 'not in', ('internal', 'transit')),
            ]),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
            order='quantity:sum desc',
            limit=1,
        )
        if top_sold and top_sold[0][0]:
            insights.append({
                'icon': 'fa-star',
                'text': _('Producto más vendido: %s (%s u.)') % (
                    top_sold[0][0].display_name, round(top_sold[0][1] or 0, 2),
                ),
            })

        slow = metrics.get('dead_stock', {}).get('count', 0)
        if slow:
            insights.append({
                'icon': 'fa-hourglass',
                'text': _('Hay %s productos con stock muerto (sin movimiento 90 días).') % slow,
            })

        wh_rows = Picking._read_group(
            domain=self._picking_domain(parsed),
            groupby=['picking_type_id'],
            aggregates=['__count'],
            order='__count desc',
            limit=1,
        )
        if wh_rows and wh_rows[0][0]:
            insights.append({
                'icon': 'fa-building',
                'text': _('Operación más activa: %s (%s movimientos).') % (
                    wh_rows[0][0].display_name, wh_rows[0][1],
                ),
            })

        products = Product.search(self._product_domain(parsed), limit=500)
        if products:
            high = max(products, key=lambda p: p.qty_available)
            insights.append({
                'icon': 'fa-cubes',
                'text': _('Mayor inventario: %s (%s u.).') % (
                    high.display_name, round(high.qty_available, 2),
                ),
            })
        return insights

    @api.model
    def _build_recommendations(self, parsed, metrics):
        recs = []
        Product = self.env['product.product']
        out_ids = metrics.get('out_of_stock', {}).get('ids', [])[:3]
        for pid in out_ids:
            p = Product.browse(pid)
            qty = max(p.reordering_min_qty or 1, 1)
            recs.append({
                'level': 'danger',
                'text': _('Se recomienda comprar %s unidades de %s.') % (qty, p.display_name),
                'product_id': p.id,
            })
        dead_cnt = metrics.get('dead_stock', {}).get('count', 0)
        if dead_cnt:
            recs.append({
                'level': 'warning',
                'text': _('Detectamos inventario inmovilizado en %s productos (>180 días sin giro).') % dead_cnt,
            })
        days = metrics.get('days_of_inventory', {}).get('value', 0)
        if days and days < 7:
            recs.append({
                'level': 'warning',
                'text': _('El inventario cubriría solo %s días al ritmo actual.') % days,
            })
        if metrics.get('overdue_deliveries', {}).get('count', 0) > 5:
            recs.append({
                'level': 'danger',
                'text': _('Proveedor/logística: %s entregas atrasadas requieren seguimiento.') % metrics['overdue_deliveries']['count'],
            })
        return recs

    @api.model
    def _build_charts(self, parsed, metrics):
        MoveLine = self.env['stock.move.line']
        Picking = self.env['stock.picking']
        Product = self.env['product.product']
        Quant = self.env['stock.quant']

        def dist_read_group(model, domain, groupby, agg='__count', limit=10):
            rows = model._read_group(domain=domain, groupby=[groupby], aggregates=[f'{agg}'], limit=limit)
            labels, values, ids = [], [], []
            for grp, val in rows:
                if not grp:
                    continue
                labels.append(grp.display_name if hasattr(grp, 'display_name') else str(grp))
                values.append(float(val or 0))
                recs = grp if isinstance(grp, models.BaseModel) else model.browse()
                ids.append(recs.ids if hasattr(recs, 'ids') else [])
            return {'labels': labels, 'values': values, 'ids': ids}

        top_products = MoveLine._read_group(
            domain=self._move_line_domain(parsed),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
            order='quantity:sum desc',
            limit=10,
        )
        receipt_status = Picking._read_group(
            domain=self._picking_domain(parsed, [('picking_type_code', '=', 'incoming')]),
            groupby=['state'],
            aggregates=['__count'],
        )
        delivery_status = Picking._read_group(
            domain=self._picking_domain(parsed, [('picking_type_code', '=', 'outgoing')]),
            groupby=['state'],
            aggregates=['__count'],
        )
        cat_acc = defaultdict(float)
        for product, qty_sum in Quant._read_group(
            domain=self._quant_domain(parsed),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
        ):
            if not product:
                continue
            cat_name = product.categ_id.complete_name or _('Sin categoría')
            cat_acc[cat_name] += float(qty_sum or 0)
        cat_sorted = sorted(cat_acc.items(), key=lambda x: x[1], reverse=True)[:10]
        aging = Quant._read_group(
            domain=self._quant_domain(parsed, [('quantity', '>', 0)]),
            groupby=['product_id'],
            aggregates=['quantity:sum'],
            limit=50,
        )

        return {
            'top_products': {
                'type': 'horizontal_bar',
                'labels': [r[0].display_name for r in top_products if r[0]],
                'values': [float(r[1] or 0) for r in top_products if r[0]],
            },
            'receipts_vs_deliveries': {
                'type': 'stacked_bar',
                'labels': [_('Recepciones'), _('Entregas')],
                'datasets': [
                    {'label': _('Cantidad'), 'data': [
                        metrics.get('incoming_quantity', {}).get('value', 0),
                        metrics.get('outgoing_quantity', {}).get('value', 0),
                    ]},
                ],
            },
            'receipt_status': {
                'type': 'doughnut',
                'labels': [dict(Picking._fields['state'].selection).get(s, s) for s, _ in receipt_status],
                'values': [c for _, c in receipt_status],
            },
            'delivery_status': {
                'type': 'doughnut',
                'labels': [dict(Picking._fields['state'].selection).get(s, s) for s, _ in delivery_status],
                'values': [c for _, c in delivery_status],
            },
            'top_categories': {
                'type': 'treemap',
                'labels': [name for name, _qty in cat_sorted],
                'values': [qty for _name, qty in cat_sorted],
            },
            'inventory_aging': {
                'type': 'bar',
                'labels': [r[0].display_name for r in aging[:10] if r[0]],
                'values': [float(r[1] or 0) for r in aging[:10] if r[0]],
            },
            'stock_vs_reserved': {
                'type': 'bar',
                'labels': [_('Disponible'), _('Reservado')],
                'values': [
                    metrics.get('stock_quantity', {}).get('value', 0),
                    metrics.get('reserved_quantity', {}).get('value', 0),
                ],
            },
            'health_gauge': {
                'type': 'gauge',
                'value': self._build_health(parsed, metrics)['score'],
            },
        }

    @api.model
    def _build_tables(self, parsed, filters):
        return {
            'out_of_stock': self._table_page(parsed, 'out_of_stock', 1, 5),
            'top_selling': self._table_page(parsed, 'top_selling', 1, 5),
            'receipts': self._table_page(parsed, 'receipts', 1, 5),
            'deliveries': self._table_page(parsed, 'deliveries', 1, 5),
        }

    @api.model
    def _table_page(self, parsed, table_key, page, page_size, search='', order=''):
        page = max(1, int(page or 1))
        page_size = min(100, max(5, int(page_size or 10)))
        offset = (page - 1) * page_size
        rows = []
        total = 0

        if table_key == 'out_of_stock':
            domain = self._product_domain(parsed, [('qty_available', '<=', 0)])
            if search:
                domain.append(('name', 'ilike', search))
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
            Picking = self.env['stock.picking']
            total = Picking.search_count(domain)
            for p in Picking.search(domain, offset=offset, limit=page_size, order=order or 'scheduled_date desc'):
                rows.append({
                    'id': p.id, 'name': p.name,
                    'partner': p.partner_id.display_name if p.partner_id else '',
                    'date': fields.Datetime.to_string(p.scheduled_date) if p.scheduled_date else '',
                    'state': p.state, 'model': 'stock.picking',
                })

        return {
            'rows': rows,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': max(1, (total + page_size - 1) // page_size),
        }

    @api.model
    def _views_for_mode(self, view_mode):
        """Tuplas ``views`` requeridas por el action service de Odoo 19."""
        views = []
        for mode in (view_mode or 'list,form').split(','):
            mode = mode.strip()
            if mode == 'tree':
                mode = 'list'
            if mode in ('list', 'form', 'kanban', 'graph', 'pivot', 'calendar'):
                views.append((False, mode))
        return views or [(False, 'list'), (False, 'form')]

    @api.model
    def _act_window_action(self, name, res_model, view_mode='list,form', domain=None,
                           context=None, target='current'):
        action = {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'view_mode': view_mode,
            'views': self._views_for_mode(view_mode),
            'target': target,
        }
        if domain is not None:
            action['domain'] = domain
        if context:
            action['context'] = context
        return action

    @api.model
    def _quick_actions(self):
        return [
            {'key': 'rfq', 'label': _('Crear RFQ'), 'icon': 'fa-shopping-cart', 'model': 'purchase.order', 'view': 'form'},
            {'key': 'transfer', 'label': _('Crear transferencia'), 'icon': 'fa-exchange', 'model': 'stock.picking', 'view': 'form'},
            {'key': 'adjustment', 'label': _('Crear ajuste'), 'icon': 'fa-sliders', 'model': 'stock.quant', 'view': 'list'},
            {'key': 'receipt', 'label': _('Crear recepción'), 'icon': 'fa-download', 'model': 'stock.picking', 'view': 'form', 'context': {'default_picking_type_code': 'incoming'}},
            {'key': 'delivery', 'label': _('Crear entrega'), 'icon': 'fa-upload', 'model': 'stock.picking', 'view': 'form', 'context': {'default_picking_type_code': 'outgoing'}},
        ]

    @api.model
    def _drilldown_action(self, parsed, metric, extra_domain):
        metrics = self._compute_metrics(parsed)
        meta = metrics.get(metric, {})
        model_map = {
            'open_pickings': 'stock.picking',
            'overdue_pickings': 'stock.picking',
            'awaiting_deliveries': 'stock.picking',
            'overdue_deliveries': 'stock.picking',
            'out_of_stock': 'product.product',
            'negative_inventory': 'stock.quant',
            'purchase_orders_waiting': 'purchase.order',
            'dead_stock': 'product.product',
        }
        model = model_map.get(metric, 'stock.picking')
        ids = meta.get('ids', [])
        domain = [('id', 'in', ids)] + list(extra_domain) if ids else extra_domain or []
        if not domain:
            domain = [('id', '=', 0)]
        return self._act_window_action(
            name=self._kpi_catalog().get(metric, {}).get('label', metric),
            res_model=model,
            view_mode='list,form',
            domain=domain,
        )
