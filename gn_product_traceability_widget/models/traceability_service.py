# -*- coding: utf-8 -*-
"""Central traceability data service — read-only aggregation over stock.move.line."""

from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import formatLang
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

INTERNAL_USAGES = frozenset({'internal'})
DONE_STATES = ('done',)
OPEN_MOVE_STATES = ('draft', 'waiting', 'confirmed', 'partially_available', 'assigned')

EVENT_META = {
    'incoming': {'label': _lt('Recepción'), 'tone': 'success', 'icon': 'fa-arrow-down'},
    'outgoing': {'label': _lt('Entrega'), 'tone': 'danger', 'icon': 'fa-arrow-up'},
    'internal_transfer': {'label': _lt('Transferencia interna'), 'tone': 'info', 'icon': 'fa-exchange'},
    'customer_return': {'label': _lt('Devolución de cliente'), 'tone': 'purple', 'icon': 'fa-undo'},
    'supplier_return': {'label': _lt('Devolución a proveedor'), 'tone': 'purple', 'icon': 'fa-reply'},
    'adjustment_in': {'label': _lt('Ajuste positivo'), 'tone': 'teal', 'icon': 'fa-plus-circle'},
    'adjustment_out': {'label': _lt('Ajuste negativo'), 'tone': 'warning', 'icon': 'fa-minus-circle'},
    'production_in': {'label': _lt('Producción'), 'tone': 'indigo', 'icon': 'fa-industry'},
    'production_out': {'label': _lt('Consumo de fabricación'), 'tone': 'indigo', 'icon': 'fa-cogs'},
    'scrap': {'label': _lt('Desecho'), 'tone': 'dark', 'icon': 'fa-trash'},
    'transit_in': {'label': _lt('Entrada desde tránsito'), 'tone': 'info', 'icon': 'fa-truck'},
    'transit_out': {'label': _lt('Salida a tránsito'), 'tone': 'info', 'icon': 'fa-truck'},
    'initial': {'label': _lt('Entrada inicial'), 'tone': 'success', 'icon': 'fa-flag'},
    'pending': {'label': _lt('Pendiente'), 'tone': 'muted', 'icon': 'fa-clock-o'},
    'cancelled': {'label': _lt('Cancelado'), 'tone': 'muted', 'icon': 'fa-ban'},
    'other': {'label': _lt('Otro'), 'tone': 'neutral', 'icon': 'fa-ellipsis-h'},
}

DEFAULT_PAGE_SIZE = 50

COMMERCIAL_PARTNER_LABELS = {
    'incoming': _lt('Comprado a'),
    'outgoing': _lt('Vendido a'),
    'customer_return': _lt('Devolución de cliente'),
    'supplier_return': _lt('Devolución a proveedor'),
}


class ProductTraceabilityService(models.AbstractModel):
    _name = 'product.traceability.service'
    _description = 'Product Traceability Data Service'

    @api.model
    def _can_show_costs(self):
        return self.env.user.has_group(
            'gn_product_traceability_widget.group_traceability_cost'
        )

    @api.model
    def _costs_enabled(self):
        return (
            self._can_show_costs()
            and 'value' in self.env['stock.move']._fields
        )

    @api.model
    def _company_currency(self, parsed):
        company = self.env['res.company'].browse(
            parsed.get('company_id', self.env.company.id)
        )
        return company.currency_id

    @api.model
    def _format_money(self, amount, currency):
        currency = currency or self.env.company.currency_id
        rounded = currency.round(amount or 0.0)
        return {
            'amount': rounded,
            'amount_fmt': formatLang(self.env, rounded, currency_obj=currency),
        }

    @api.model
    def _currency_payload(self, currency):
        return {
            'id': currency.id,
            'name': currency.name,
            'symbol': currency.symbol,
        }

    @api.model
    def _build_move_cache(self, moves):
        cache = {}
        if 'value' not in self.env['stock.move']._fields:
            return cache
        for move in moves:
            if not move.is_valued:
                cache[move.id] = {'value': 0.0, 'is_valued': False, 'total_qty': 0.0}
                continue
            total_qty = sum(
                ml.quantity_product_uom or ml.quantity
                for ml in move.move_line_ids
                if ml.state == 'done'
            )
            cache[move.id] = {
                'value': move.value or 0.0,
                'is_valued': True,
                'total_qty': total_qty,
            }
        return cache

    @api.model
    def _line_value(self, line, move_cache):
        move = line.move_id
        if not move:
            return 0.0
        data = move_cache.get(move.id)
        if not data or not data.get('is_valued'):
            return 0.0
        total_qty = data.get('total_qty') or 0.0
        if not total_qty:
            return 0.0
        line_qty = line.quantity_product_uom or line.quantity
        return (data['value'] or 0.0) * (line_qty / total_qty)

    @api.model
    def _net_value_delta(self, event_type, value):
        if event_type in ('incoming', 'customer_return', 'adjustment_in', 'production_in', 'transit_in', 'initial'):
            return value
        if event_type in ('outgoing', 'supplier_return', 'adjustment_out', 'production_out', 'scrap', 'transit_out'):
            return -value
        return 0.0

    @api.model
    def _event_value_fields(self, line, event_type, qty, move_cache, currency):
        if not self._costs_enabled():
            return {}
        line_value = abs(self._line_value(line, move_cache))
        move = line.move_id
        is_valued = bool(move and move.is_valued and line_value)
        value_in = line_value if self._is_inflow(event_type) and is_valued else 0.0
        value_out = line_value if self._is_outflow(event_type) and is_valued else 0.0
        unit_cost = (line_value / qty) if qty and is_valued else 0.0
        unit = self._format_money(unit_cost, currency)
        total = self._format_money(line_value if is_valued else 0.0, currency)
        val_in = self._format_money(value_in, currency)
        val_out = self._format_money(value_out, currency)
        return {
            'is_valued': is_valued,
            'unit_cost': unit['amount'],
            'unit_cost_fmt': unit['amount_fmt'],
            'value': total['amount'],
            'value_fmt': total['amount_fmt'],
            'value_in': value_in,
            'value_in_fmt': val_in['amount_fmt'],
            'value_out': value_out,
            'value_out_fmt': val_out['amount_fmt'],
        }

    @api.model
    def _compute_value_balances(self, parsed, events, product, move_cache, currency):
        if not self._costs_enabled():
            return 0.0, 0.0, 0.0, 0.0
        opening_value = 0.0
        if parsed.get('date_from'):
            opening_lines = self._fetch_all_lines_for_balance(parsed, before_date=parsed['date_from'])
            opening_cache = self._build_move_cache(opening_lines.move_id)
            for line in opening_lines:
                et = self.classify_movement(
                    line.location_id.usage, line.location_dest_id.usage,
                    is_scrap=bool(line.scrap_id), is_inventory=bool(line.is_inventory), state=line.state,
                )
                if not parsed.get('include_internal') and et == 'internal_transfer':
                    continue
                if not parsed.get('include_adjustments') and et in ('adjustment_in', 'adjustment_out'):
                    continue
                line_val = abs(self._line_value(line, opening_cache))
                opening_value += self._net_value_delta(et, line_val)
        opening_value = currency.round(opening_value)
        period_in = sum(e.get('value_in') or 0.0 for e in events)
        period_out = sum(e.get('value_out') or 0.0 for e in events)
        running = opening_value
        for event in events:
            line_val = event.get('value') or 0.0
            running += self._net_value_delta(event['type'], line_val)
            fmt = self._format_money(running, currency)
            event['value_balance'] = fmt['amount']
            event['value_balance_fmt'] = fmt['amount_fmt']
        closing_value = currency.round(opening_value + period_in - period_out)
        return opening_value, currency.round(period_in), currency.round(period_out), closing_value

    @api.model
    def _summary_payload(self, parsed, opening_qty, period_in, period_out, closing_qty,
                         opening_value=0.0, period_in_value=0.0, period_out_value=0.0, closing_value=0.0):
        currency = self._company_currency(parsed)
        summary = {
            'opening_qty': opening_qty,
            'incoming_qty': period_in,
            'outgoing_qty': period_out,
            'closing_qty': closing_qty,
            'balance_scope': parsed.get('balance_scope_label'),
        }
        if self._costs_enabled():
            summary.update({
                'opening_value': opening_value,
                'opening_value_fmt': self._format_money(opening_value, currency)['amount_fmt'],
                'incoming_value': period_in_value,
                'incoming_value_fmt': self._format_money(period_in_value, currency)['amount_fmt'],
                'outgoing_value': period_out_value,
                'outgoing_value_fmt': self._format_money(period_out_value, currency)['amount_fmt'],
                'closing_value': closing_value,
                'closing_value_fmt': self._format_money(closing_value, currency)['amount_fmt'],
                'currency': self._currency_payload(currency),
            })
        return summary

    @api.model
    def _resolve_event_partner(self, line, picking):
        partner = line.picking_partner_id or line.move_partner_id or line.owner_id
        if partner or not picking:
            return partner
        for field_name in ('purchase_id', 'sale_id'):
            if field_name not in picking._fields:
                continue
            doc = picking[field_name]
            if doc and doc.partner_id:
                return doc.partner_id
        return picking.partner_id

    @api.model
    def _commercial_partner_fields(self, event_type, partner):
        """Map movement type to supplier/customer display for purchases and sales."""
        empty = {
            'partner': '',
            'partner_id': False,
            'commercial_partner': '',
            'commercial_partner_id': False,
            'commercial_partner_label': '',
            'commercial_partner_role': False,
            'supplier': '',
            'supplier_id': False,
            'customer': '',
            'customer_id': False,
        }
        if not partner:
            return empty
        name = partner.display_name
        role_map = {
            'incoming': 'supplier',
            'supplier_return': 'supplier',
            'outgoing': 'customer',
            'customer_return': 'customer',
        }
        role = role_map.get(event_type)
        label = self.env._(COMMERCIAL_PARTNER_LABELS[event_type]) if event_type in COMMERCIAL_PARTNER_LABELS else ''
        result = {
            'partner': name,
            'partner_id': partner.id,
            'commercial_partner': name,
            'commercial_partner_id': partner.id,
            'commercial_partner_label': label,
            'commercial_partner_role': role or False,
            'supplier': '',
            'supplier_id': False,
            'customer': '',
            'customer_id': False,
        }
        if role == 'supplier':
            result['supplier'] = name
            result['supplier_id'] = partner.id
        elif role == 'customer':
            result['customer'] = name
            result['customer_id'] = partner.id
        return result

    @api.model
    def _check_access(self, export=False):
        group = (
            'gn_product_traceability_widget.group_traceability_export'
            if export
            else 'gn_product_traceability_widget.group_traceability_user'
        )
        if not self.env.user.has_group(group):
            raise AccessError(_('No tiene permiso para acceder a la trazabilidad de productos.'))

    @api.model
    def get_filter_options(self, init_params=None):
        self._check_access()
        ctx = init_params or {}
        company_ids = self.env.companies.ids
        warehouses = self.env['stock.warehouse'].search([
            ('company_id', 'in', company_ids),
        ], order='name', limit=200)
        locations = self.env['stock.location'].search([
            ('usage', '!=', 'view'),
            ('company_id', 'in', company_ids + [False]),
        ], order='complete_name', limit=500)
        operation_types = self.env['stock.picking.type'].search([
            ('company_id', 'in', company_ids),
        ], order='sequence, name', limit=100)
        lots = []
        lot_id = ctx.get('lot_id')
        product_id = ctx.get('product_id')
        product_tmpl_id = ctx.get('product_tmpl_id')
        if lot_id:
            lot = self.env['stock.lot'].browse(lot_id)
            lots = [{'id': lot.id, 'name': lot.name}]
        elif product_id or product_tmpl_id:
            lot_domain = [('company_id', 'in', company_ids + [False])]
            if product_id:
                lot_domain.append(('product_id', '=', product_id))
            else:
                lot_domain.append(('product_id.product_tmpl_id', '=', product_tmpl_id))
            lots = [
                {'id': l.id, 'name': l.name}
                for l in self.env['stock.lot'].search(lot_domain, order='name', limit=200)
            ]
        today = fields.Date.context_today(self)
        return {
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
            'multi_company': len(self.env.companies) > 1,
            'warehouses': [{'id': w.id, 'name': w.name} for w in warehouses],
            'locations': [{'id': l.id, 'name': l.complete_name, 'usage': l.usage} for l in locations],
            'operation_types': [{'id': t.id, 'name': t.display_name, 'code': t.code} for t in operation_types],
            'lots': lots,
            'movement_types': [
                {'key': k, 'label': self.env._(v['label'])} for k, v in EVENT_META.items()
                if k not in ('pending',)
            ],
            'states': [
                {'key': 'done', 'label': _('Hecho')},
                {'key': 'assigned', 'label': _('Asignado')},
                {'key': 'confirmed', 'label': _('Confirmado')},
                {'key': 'waiting', 'label': _('Esperando')},
                {'key': 'draft', 'label': _('Borrador')},
                {'key': 'cancel', 'label': _('Cancelado')},
            ],
            'default_date_to': fields.Date.to_string(today),
            'page_size_options': [50, 100],
            'products': self._product_selector_options(),
        }

    @api.model
    def search_products(self, term='', limit=20):
        """Lightweight product lookup for the dashboard selector."""
        self._check_access()
        domain = [('is_storable', '=', True)]
        if term:
            domain += ['|', '|', ('name', 'ilike', term), ('default_code', 'ilike', term), ('barcode', 'ilike', term)]
        products = self.env['product.product'].search(domain, order='name', limit=limit)
        return [{
            'id': p.id,
            'name': p.display_name,
            'default_code': p.default_code or '',
            'tmpl_id': p.product_tmpl_id.id,
        } for p in products]

    @api.model
    def _product_selector_options(self):
        products = self.env['product.product'].search(
            [('is_storable', '=', True)], order='name', limit=100,
        )
        return [{
            'id': p.id,
            'name': p.display_name,
            'default_code': p.default_code or '',
            'tmpl_id': p.product_tmpl_id.id,
        } for p in products]

    @api.model
    def _empty_traceability_payload(self, parsed, page, page_size):
        return {
            'product': None,
            'needs_product': True,
            'filters': self._filters_payload(parsed),
            'summary': {
                'opening_qty': 0.0,
                'incoming_qty': 0.0,
                'outgoing_qty': 0.0,
                'closing_qty': 0.0,
                'balance_scope': '',
            },
            'kpis': [],
            'events': [],
            'flow_graph': {'nodes': [], 'edges': [], 'branches': []},
            'movement_summary': [],
            'current_locations': [],
            'pending_moves': [],
            'pagination': {'page': page, 'page_size': page_size, 'total': 0, 'has_more': False},
            'meta': {
                'can_export': self.env.user.has_group(
                    'gn_product_traceability_widget.group_traceability_export'
                ),
                'can_show_costs': self._costs_enabled(),
                'updated_at': fields.Datetime.to_string(fields.Datetime.now()),
            },
        }

    @api.model
    def get_product_traceability(self, filters=None, page=1, page_size=DEFAULT_PAGE_SIZE, order='asc'):
        self._check_access()
        parsed = self._parse_filters(filters or {})
        product = self._resolve_product(parsed)
        if not product:
            return self._empty_traceability_payload(parsed, page, page_size)

        product_info = self._product_payload(product, parsed)
        lines, total_count = self._fetch_move_lines(parsed, page, page_size, order)
        move_cache = self._build_move_cache(lines.move_id)
        currency = self._company_currency(parsed)
        events = self._build_events(lines, product, parsed, move_cache, currency)
        opening_qty, period_in, period_out, closing_qty = self._compute_balances(parsed, events, product)
        opening_value, period_in_value, period_out_value, closing_value = self._compute_value_balances(
            parsed, events, product, move_cache, currency,
        )
        kpis = self._build_kpis(
            parsed, product, opening_qty, period_in, period_out, closing_qty, events,
            opening_value, period_in_value, period_out_value, closing_value, currency,
        )
        current_locations = self._current_locations(parsed, product)
        pending = self._pending_moves(parsed, product) if parsed.get('include_pending') else []
        flow_graph = self._build_flow_graph(events)
        movement_summary = self._movement_type_summary(events)

        return {
            'product': product_info,
            'filters': self._filters_payload(parsed),
            'summary': self._summary_payload(
                parsed, opening_qty, period_in, period_out, closing_qty,
                opening_value, period_in_value, period_out_value, closing_value,
            ),
            'kpis': kpis,
            'events': events,
            'flow_graph': flow_graph,
            'movement_summary': movement_summary,
            'current_locations': current_locations,
            'pending_moves': pending,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total_count,
                'has_more': page * page_size < total_count,
            },
            'meta': {
                'can_export': self.env.user.has_group(
                    'gn_product_traceability_widget.group_traceability_export'
                ),
                'can_show_costs': self._costs_enabled(),
                'updated_at': fields.Datetime.to_string(fields.Datetime.now()),
            },
            'needs_product': False,
        }

    @api.model
    def get_export_data(self, filters=None):
        self._check_access(export=True)
        parsed = self._parse_filters(filters or {})
        product = self._resolve_product(parsed)
        if not product:
            raise UserError(_('Seleccione un producto para exportar trazabilidad.'))
        lines, _total = self._fetch_move_lines(parsed, 1, 999999, parsed.get('order', 'asc'))
        move_cache = self._build_move_cache(lines.move_id)
        currency = self._company_currency(parsed)
        events = self._build_events(lines, product, parsed, move_cache, currency)
        opening_qty, period_in, period_out, closing_qty = self._compute_balances(parsed, events, product)
        opening_value, period_in_value, period_out_value, closing_value = self._compute_value_balances(
            parsed, events, product, move_cache, currency,
        )
        movement_summary = self._movement_type_summary(events)
        return {
            'product': self._product_payload(product, parsed),
            'filters': self._filters_payload(parsed),
            'summary': self._summary_payload(
                parsed, opening_qty, period_in, period_out, closing_qty,
                opening_value, period_in_value, period_out_value, closing_value,
            ),
            'kpis': self._build_kpis(
                parsed, product, opening_qty, period_in, period_out, closing_qty, events,
                opening_value, period_in_value, period_out_value, closing_value, currency,
            ),
            'movement_summary': movement_summary,
            'events': events,
            'current_locations': self._current_locations(parsed, product),
            'generated_by': self.env.user.display_name,
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'company': {'name': self.env.company.name},
            'meta': {
                'can_show_costs': self._costs_enabled(),
            },
        }

    @api.model
    def count_traceability_events(self, product_tmpl_id=None, product_id=None, lot_id=None):
        self._check_access()
        domain = self._base_line_domain({
            'product_tmpl_id': product_tmpl_id,
            'product_id': product_id,
            'lot_id': lot_id,
            'include_cancelled': False,
            'include_pending': False,
            'state': 'done',
            'company_id': self.env.company.id,
        })
        return self.env['stock.move.line'].search_count(domain)

    @api.model
    def classify_movement(self, src_usage, dest_usage, *, is_scrap=False, is_inventory=False, state='done'):
        if state == 'cancel':
            return 'cancelled'
        if is_scrap:
            return 'scrap'
        if src_usage == 'supplier' and dest_usage == 'internal':
            return 'incoming'
        if src_usage == 'internal' and dest_usage == 'customer':
            return 'outgoing'
        if src_usage == 'customer' and dest_usage == 'internal':
            return 'customer_return'
        if src_usage == 'internal' and dest_usage == 'supplier':
            return 'supplier_return'
        if src_usage == 'internal' and dest_usage == 'internal':
            return 'internal_transfer'
        if src_usage == 'inventory' and dest_usage == 'internal':
            return 'adjustment_in'
        if src_usage == 'internal' and dest_usage == 'inventory':
            return 'adjustment_out'
        if is_inventory and src_usage == 'inventory':
            return 'adjustment_in'
        if is_inventory and dest_usage == 'inventory':
            return 'adjustment_out'
        if src_usage == 'production' and dest_usage == 'internal':
            return 'production_in'
        if src_usage == 'internal' and dest_usage == 'production':
            return 'production_out'
        if src_usage == 'transit' and dest_usage == 'internal':
            return 'transit_in'
        if src_usage == 'internal' and dest_usage == 'transit':
            return 'transit_out'
        if src_usage == 'inventory' and dest_usage not in INTERNAL_USAGES:
            return 'initial'
        return 'other'

    @api.model
    def _net_stock_delta(self, event_type, qty):
        if event_type in ('incoming', 'customer_return', 'adjustment_in', 'production_in', 'transit_in', 'initial'):
            return qty
        if event_type in ('outgoing', 'supplier_return', 'adjustment_out', 'production_out', 'scrap', 'transit_out'):
            return -qty
        return 0.0

    @api.model
    def _is_inflow(self, event_type):
        return event_type in (
            'incoming', 'customer_return', 'adjustment_in', 'production_in', 'transit_in', 'initial'
        )

    @api.model
    def _is_outflow(self, event_type):
        return event_type in (
            'outgoing', 'supplier_return', 'adjustment_out', 'production_out', 'scrap', 'transit_out'
        )

    @api.model
    def _parse_filters(self, raw):
        company_id = raw.get('company_id') or self.env.company.id
        if company_id not in self.env.companies.ids:
            company_id = self.env.company.id
        parsed = {
            'product_id': raw.get('product_id') and int(raw['product_id']),
            'product_tmpl_id': raw.get('product_tmpl_id') and int(raw['product_tmpl_id']),
            'lot_id': raw.get('lot_id') and int(raw['lot_id']),
            'company_id': int(company_id),
            'warehouse_id': raw.get('warehouse_id') and int(raw['warehouse_id']),
            'location_id': raw.get('location_id') and int(raw['location_id']),
            'operation_type_id': raw.get('operation_type_id') and int(raw['operation_type_id']),
            'movement_type': raw.get('movement_type') or False,
            'state': raw.get('state') or 'done',
            'partner_id': raw.get('partner_id') and int(raw['partner_id']),
            'document': (raw.get('document') or '').strip(),
            'search': (raw.get('search') or '').strip(),
            'date_from': raw.get('date_from') or False,
            'date_to': raw.get('date_to') or False,
            'include_internal': raw.get('include_internal', True),
            'include_adjustments': raw.get('include_adjustments', True),
            'include_cancelled': raw.get('include_cancelled', False),
            'include_pending': raw.get('include_pending', False),
            'order': raw.get('order') or 'asc',
            'view': raw.get('view') or 'timeline',
        }
        if parsed['date_from']:
            parsed['date_from'] = fields.Date.to_date(parsed['date_from'])
        if parsed['date_to']:
            parsed['date_to'] = fields.Date.to_date(parsed['date_to'])
        parsed['balance_scope_label'] = (
            _('Saldo dentro del período filtrado')
            if parsed['date_from'] or parsed['date_to']
            else _('Saldo histórico completo')
        )
        return parsed

    @api.model
    def _filters_payload(self, parsed):
        out = {}
        for key, val in parsed.items():
            if hasattr(val, 'year') and key.startswith('date'):
                out[key] = fields.Date.to_string(val)
            else:
                out[key] = val
        return out

    @api.model
    def _resolve_product(self, parsed):
        Product = self.env['product.product']
        if parsed.get('product_id'):
            product = Product.browse(parsed['product_id'])
            return product if product.exists() else Product
        if parsed.get('product_tmpl_id'):
            tmpl = self.env['product.template'].browse(parsed['product_tmpl_id'])
            if tmpl.exists():
                return tmpl.product_variant_id or Product
        if parsed.get('lot_id'):
            lot = self.env['stock.lot'].browse(parsed['lot_id'])
            if lot.exists():
                return lot.product_id
        return Product

    @api.model
    def _base_line_domain(self, parsed):
        domain = [('company_id', '=', parsed.get('company_id', self.env.company.id))]
        if parsed.get('product_id'):
            domain.append(('product_id', '=', parsed['product_id']))
        elif parsed.get('product_tmpl_id'):
            domain.append(('product_id.product_tmpl_id', '=', parsed['product_tmpl_id']))
        if parsed.get('lot_id'):
            domain.append(('lot_id', '=', parsed['lot_id']))
        if parsed.get('location_id'):
            loc_id = parsed['location_id']
            domain += ['|', ('location_id', '=', loc_id), ('location_dest_id', '=', loc_id)]
        elif parsed.get('warehouse_id'):
            wh = self.env['stock.warehouse'].browse(parsed['warehouse_id'])
            if wh.exists():
                loc_ids = wh.view_location_id.child_ids.ids + [wh.lot_stock_id.id, wh.view_location_id.id]
                domain += ['|', ('location_id', 'in', loc_ids), ('location_dest_id', 'in', loc_ids)]
        if parsed.get('operation_type_id'):
            domain.append(('picking_type_id', '=', parsed['operation_type_id']))
        if parsed.get('partner_id'):
            pid = parsed['partner_id']
            domain += ['|', '|', ('picking_partner_id', '=', pid), ('move_partner_id', '=', pid), ('owner_id', '=', pid)]
        if parsed.get('document'):
            doc = parsed['document']
            domain += ['|', '|', '|', ('picking_id.name', 'ilike', doc), ('origin', 'ilike', doc),
                       ('reference', 'ilike', doc), ('lot_id.name', 'ilike', doc)]
        if parsed.get('search'):
            term = parsed['search']
            domain += [
                '|', '|', '|', '|', '|', '|',
                ('picking_id.name', 'ilike', term), ('origin', 'ilike', term), ('reference', 'ilike', term),
                ('lot_id.name', 'ilike', term), ('location_id.complete_name', 'ilike', term),
                ('location_dest_id.complete_name', 'ilike', term), ('picking_partner_id.name', 'ilike', term),
            ]
        if parsed.get('date_from'):
            dt_from = datetime.combine(parsed['date_from'], datetime.min.time())
            domain.append(('date', '>=', fields.Datetime.to_string(dt_from)))
        if parsed.get('date_to'):
            dt_to = datetime.combine(parsed['date_to'], datetime.max.time())
            domain.append(('date', '<=', fields.Datetime.to_string(dt_to)))
        if parsed.get('include_pending'):
            states = list(OPEN_MOVE_STATES)
            if parsed.get('include_cancelled'):
                states.append('cancel')
            if parsed.get('state') and parsed['state'] != 'done':
                states = [parsed['state']]
            domain.append(('state', 'in', states))
        elif parsed.get('include_cancelled'):
            domain.append(('state', 'in', list(DONE_STATES) + ('cancel',)))
        else:
            domain.append(('state', '=', parsed.get('state') or 'done'))
        return domain

    @api.model
    def _fetch_move_lines(self, parsed, page, page_size, order):
        MoveLine = self.env['stock.move.line']
        domain = self._base_line_domain(parsed)
        total = MoveLine.search_count(domain)
        order_str = 'date asc, id asc' if order == 'asc' else 'date desc, id desc'
        offset = max(0, (page - 1) * page_size)
        lines = MoveLine.search(domain, order=order_str, limit=page_size, offset=offset)
        return lines, total

    @api.model
    def _fetch_all_lines_for_balance(self, parsed, before_date=None):
        base = dict(parsed)
        base.update({'include_pending': False, 'include_cancelled': False, 'state': 'done'})
        domain = self._base_line_domain(base)
        if before_date:
            dt = datetime.combine(before_date, datetime.min.time())
            domain.append(('date', '<', fields.Datetime.to_string(dt)))
        return self.env['stock.move.line'].search(domain, order='date asc, id asc')

    @api.model
    def _build_events(self, lines, product, parsed, move_cache=None, currency=None):
        if not lines:
            return []
        move_cache = move_cache if move_cache is not None else self._build_move_cache(lines.move_id)
        currency = currency or self._company_currency(parsed)
        costs_on = self._costs_enabled()
        picking_map = {p.id: p for p in lines.picking_id}
        user_ids = {picking_map[p].user_id.id for p in picking_map if picking_map[p].user_id}
        user_map = {u.id: u.display_name for u in self.env['res.users'].browse(list(user_ids))}
        uom_name = product.uom_id.name
        state_field = self.env['stock.move.line']._fields['state']
        state_labels = dict(state_field._description_selection(self.env))
        events = []
        for line in lines:
            src_usage = line.location_id.usage or ''
            dest_usage = line.location_dest_id.usage or ''
            is_scrap = bool(line.scrap_id) or getattr(line.location_dest_id, 'scrap_location', False)
            event_type = self.classify_movement(
                src_usage, dest_usage, is_scrap=is_scrap,
                is_inventory=bool(line.is_inventory), state=line.state,
            )
            if not parsed.get('include_internal') and event_type == 'internal_transfer':
                continue
            if not parsed.get('include_adjustments') and event_type in ('adjustment_in', 'adjustment_out'):
                continue
            if parsed.get('movement_type') and event_type != parsed['movement_type']:
                continue
            qty = product.uom_id.round(line.quantity_product_uom or line.quantity)
            meta = EVENT_META.get(event_type, EVENT_META['other'])
            picking = line.picking_id
            partner = self._resolve_event_partner(line, picking)
            user_name = user_map.get(picking.user_id.id, '') if picking and picking.user_id else ''
            highlights = self._search_highlights(parsed.get('search'), line, picking, partner, user_name)
            event = {
                'id': line.id,
                'date': fields.Datetime.to_string(line.date),
                'date_fmt': _format_datetime(self.env, line.date),
                'type': event_type,
                'type_label': self.env._(meta['label']),
                'tone': meta['tone'],
                'icon': meta['icon'],
                'state': line.state,
                'state_label': state_labels.get(line.state, line.state),
                'document': picking.name if picking else (line.reference or line.origin or '—'),
                'reference': line.reference or line.origin or '',
                'origin': line.origin or '',
                'source': line.location_id.complete_name,
                'source_id': line.location_id.id,
                'source_usage': src_usage,
                'destination': line.location_dest_id.complete_name,
                'destination_id': line.location_dest_id.id,
                'destination_usage': dest_usage,
                'qty': qty,
                'in_qty': qty if self._is_inflow(event_type) else 0.0,
                'out_qty': qty if self._is_outflow(event_type) else 0.0,
                'uom': uom_name,
                'lot': line.lot_id.name if line.lot_id else (line.lot_name or ''),
                'lot_id': line.lot_id.id if line.lot_id else False,
                'user': user_name,
                'company': line.company_id.name,
                'picking_id': picking.id if picking else False,
                'move_id': line.move_id.id if line.move_id else False,
                'links': self._document_links(picking, line),
                'highlight': highlights['matched'],
                'highlight_fields': highlights['fields'],
            }
            event.update(self._commercial_partner_fields(event_type, partner))
            if highlights['matched'] and partner and 'partner' in highlights['fields']:
                if event.get('supplier'):
                    highlights['fields'].append('supplier')
                if event.get('customer'):
                    highlights['fields'].append('customer')
                event['highlight_fields'] = highlights['fields']
            if costs_on:
                event.update(self._event_value_fields(line, event_type, qty, move_cache, currency))
            events.append(event)
        return events

    @api.model
    def _search_highlights(self, search, line, picking, partner, user_name=''):
        """Return matched field keys for client-side highlighting."""
        if not search:
            return {'matched': False, 'fields': []}
        term = search.lower()
        field_values = {
            'document': picking.name if picking else (line.reference or line.origin or ''),
            'origin': line.origin or '',
            'reference': line.reference or '',
            'lot': line.lot_id.name if line.lot_id else (line.lot_name or ''),
            'source': line.location_id.complete_name,
            'destination': line.location_dest_id.complete_name,
            'partner': partner.display_name if partner else '',
            'supplier': partner.display_name if partner else '',
            'customer': partner.display_name if partner else '',
            'user': user_name or '',
        }
        matched = [key for key, value in field_values.items() if term in (value or '').lower()]
        return {'matched': bool(matched), 'fields': matched}

    @api.model
    def _document_links(self, picking, line):
        links = []
        if picking:
            links.append({'model': 'stock.picking', 'id': picking.id, 'label': picking.name})
        if line.lot_id:
            links.append({'model': 'stock.lot', 'id': line.lot_id.id, 'label': line.lot_id.name})
        if picking and picking.origin:
            links.append({'model': False, 'id': False, 'label': picking.origin})
        for field_name, model in (('sale_id', 'sale.order'), ('purchase_id', 'purchase.order')):
            if picking and field_name in picking._fields:
                rec = picking[field_name]
                if rec:
                    links.append({'model': model, 'id': rec.id, 'label': rec.name})
        return links

    @api.model
    def _compute_balances(self, parsed, events, product):
        uom = product.uom_id
        opening_qty = 0.0
        if parsed.get('date_from'):
            for line in self._fetch_all_lines_for_balance(parsed, before_date=parsed['date_from']):
                et = self.classify_movement(
                    line.location_id.usage, line.location_dest_id.usage,
                    is_scrap=bool(line.scrap_id), is_inventory=bool(line.is_inventory), state=line.state,
                )
                opening_qty += self._net_stock_delta(et, line.quantity_product_uom or line.quantity)
        opening_qty = uom.round(opening_qty)
        period_in = sum(e['in_qty'] for e in events)
        period_out = sum(e['out_qty'] for e in events)
        running = opening_qty
        for event in events:
            running += self._net_stock_delta(event['type'], event['qty'])
            event['balance'] = uom.round(running)
        closing_qty = uom.round(opening_qty + period_in - period_out)
        return opening_qty, uom.round(period_in), uom.round(period_out), closing_qty

    @api.model
    def _build_kpis(self, parsed, product, opening, period_in, period_out, closing, events,
                    opening_value=0.0, period_in_value=0.0, period_out_value=0.0, closing_value=0.0,
                    currency=None):
        uom = product.uom_id.name
        currency = currency or self._company_currency(parsed)
        product_ctx = product.with_context(
            warehouse=parsed.get('warehouse_id'), location=parsed.get('location_id'),
        ).with_company(parsed.get('company_id', self.env.company.id))
        lot_ids = {e['lot_id'] for e in events if e.get('lot_id')}
        internal_count = sum(1 for e in events if e['type'] == 'internal_transfer')
        adjustment_qty = sum(
            e['qty'] for e in events if e['type'] in ('adjustment_in', 'adjustment_out')
        )
        return_count = sum(
            1 for e in events if e['type'] in ('customer_return', 'supplier_return')
        )
        suppliers = {e['supplier_id'] for e in events if e.get('supplier_id')}
        customers = {e['customer_id'] for e in events if e.get('customer_id')}

        def kpi(key, label, value, helper, tone, icon, uom_label=uom, value_fmt=None):
            row = {
                'key': key, 'label': label, 'value': value, 'uom': uom_label,
                'helper': helper, 'tone': tone, 'icon': icon,
            }
            if value_fmt is not None:
                row['value_fmt'] = value_fmt
            return row

        kpis = [
            kpi('on_hand', _('Existencia actual'), product_ctx.qty_available,
                _('Disponible en almacenes'), 'primary', 'fa-cubes'),
            kpi('incoming', _('Total entradas'), period_in,
                _('Movimientos recibidos'), 'success', 'fa-arrow-down'),
            kpi('outgoing', _('Total salidas'), period_out,
                _('Entregas y consumos'), 'danger', 'fa-arrow-up'),
            kpi('internal', _('Transferencias internas'), internal_count,
                _('Movimientos internos'), 'info', 'fa-exchange', ''),
            kpi('adjustments', _('Ajustes'), adjustment_qty,
                _('Cantidad ajustada en el período'), 'warning', 'fa-sliders'),
            kpi('returns', _('Devoluciones'), return_count,
                _('Devoluciones registradas'), 'purple', 'fa-undo', ''),
            kpi('suppliers', _('Proveedores'), len(suppliers),
                _('Orígenes de compra en el período'), 'purple', 'fa-truck', ''),
            kpi('customers', _('Clientes'), len(customers),
                _('Destinos de venta en el período'), 'danger', 'fa-user', ''),
            kpi('lots', _('Lotes / series'), len(lot_ids),
                _('Identificadores distintos'), 'secondary', 'fa-barcode', ''),
            kpi('last_move', _('Último movimiento'),
                events[-1]['date_fmt'] if events else '—',
                _('Fecha del último evento'), 'neutral', 'fa-clock-o', ''),
            kpi('reserved', _('Reservado'), product_ctx.outgoing_qty,
                _('Salidas pendientes'), 'muted', 'fa-lock'),
            kpi('incoming_pending', _('En tránsito / por recibir'), product_ctx.incoming_qty,
                _('Entradas esperadas'), 'info', 'fa-truck'),
            kpi('closing', _('Saldo final'), closing,
                parsed.get('balance_scope_label', ''), 'primary', 'fa-balance-scale'),
        ]
        if self._costs_enabled():
            net_period_value = currency.round(period_in_value - period_out_value)
            kpis.extend([
                kpi('inventory_value', _('Valor en existencia'), product_ctx.total_value,
                    _('Valor contable del inventario'), 'success', 'fa-money',
                    '', self._format_money(product_ctx.total_value, currency)['amount_fmt']),
                kpi('avg_cost', _('Costo promedio'), product_ctx.avg_cost,
                    _('Costo unitario promedio'), 'info', 'fa-line-chart',
                    '', self._format_money(product_ctx.avg_cost, currency)['amount_fmt']),
                kpi('net_value', _('Valor neto del período'), net_period_value,
                    _('Entradas menos salidas valoradas'), 'warning', 'fa-calculator',
                    '', self._format_money(net_period_value, currency)['amount_fmt']),
            ])
        return kpis

    @api.model
    def _movement_type_summary(self, events):
        """Aggregate counts and quantities per movement type for exports."""
        summary = {}
        for event in events:
            key = event['type']
            bucket = summary.setdefault(key, {
                'type': key,
                'label': event['type_label'],
                'count': 0,
                'qty_in': 0.0,
                'qty_out': 0.0,
                'value_in': 0.0,
                'value_out': 0.0,
            })
            bucket['count'] += 1
            bucket['qty_in'] += event.get('in_qty') or 0.0
            bucket['qty_out'] += event.get('out_qty') or 0.0
            bucket['value_in'] += event.get('value_in') or 0.0
            bucket['value_out'] += event.get('value_out') or 0.0
        return sorted(summary.values(), key=lambda r: r['label'])

    @api.model
    def _current_locations(self, parsed, product):
        domain = [
            ('product_id', '=', product.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
            ('company_id', '=', parsed.get('company_id', self.env.company.id)),
        ]
        if parsed.get('lot_id'):
            domain.append(('lot_id', '=', parsed['lot_id']))
        if parsed.get('warehouse_id'):
            wh = self.env['stock.warehouse'].browse(parsed['warehouse_id'])
            if wh.exists():
                domain.append(('location_id', 'child_of', wh.view_location_id.id))
        read_fields = ['quantity:sum', 'reserved_quantity:sum']
        if self._costs_enabled() and 'value' in self.env['stock.quant']._fields:
            read_fields.append('value:sum')
        groups = self.env['stock.quant']._read_group(
            domain,
            ['location_id'],
            read_fields,
        )
        result = []
        for row in groups:
            location = row[0]
            quantity = row[1]
            reserved_quantity = row[2]
            loc_value = row[3] if len(row) > 3 else 0.0
            if not location:
                continue
            loc_data = {
                'location_id': location.id,
                'location': location.complete_name,
                'qty': product.uom_id.round(quantity or 0),
                'reserved': product.uom_id.round(reserved_quantity or 0),
                'uom': product.uom_id.name,
            }
            if self._costs_enabled():
                currency = self._company_currency(parsed)
                fmt = self._format_money(loc_value or 0.0, currency)
                loc_data['value'] = fmt['amount']
                loc_data['value_fmt'] = fmt['amount_fmt']
            result.append(loc_data)
        return sorted(result, key=lambda r: r['location'])

    @api.model
    def _pending_moves(self, parsed, product):
        domain = [
            ('product_id', '=', product.id),
            ('state', 'in', list(OPEN_MOVE_STATES)),
            ('company_id', '=', parsed.get('company_id', self.env.company.id)),
        ]
        if parsed.get('lot_id'):
            domain.append(('move_line_ids.lot_id', '=', parsed['lot_id']))
        pending = []
        for move in self.env['stock.move'].search(domain, order='date asc', limit=100):
            et = self.classify_movement(move.location_id.usage, move.location_dest_id.usage, state=move.state)
            partner = move.partner_id or (move.picking_id.partner_id if move.picking_id else False)
            row = {
                'id': move.id,
                'date': fields.Datetime.to_string(move.date or fields.Datetime.now()),
                'type': et,
                'type_label': self.env._(EVENT_META['pending']['label']),
                'document': move.reference or move.origin or (move.picking_id.name if move.picking_id else '—'),
                'qty': product.uom_id.round(move.product_uom_qty),
                'uom': product.uom_id.name,
                'state': move.state,
                'source': move.location_id.complete_name,
                'destination': move.location_dest_id.complete_name,
                'picking_id': move.picking_id.id if move.picking_id else False,
            }
            row.update(self._commercial_partner_fields(et, partner))
            pending.append(row)
        return pending

    @api.model
    def _build_flow_graph(self, events):
        """Build node/edge graph for SVG flow map with location branching."""
        if not events:
            return {'nodes': [], 'edges': [], 'branches': []}

        nodes = {}
        edges = []
        branch_map = {}

        def ensure_loc(loc_id, name, usage):
            nid = f'loc-{loc_id}'
            if nid not in nodes:
                nodes[nid] = {
                    'id': nid,
                    'label': name,
                    'kind': 'location',
                    'usage': usage,
                    'tone': self._location_kind(usage),
                }
            return nid

        prev_dest = None
        for idx, event in enumerate(events):
            src_id = ensure_loc(event['source_id'], event['source'], event['source_usage'])
            ev_id = f"ev-{event['id']}"
            dst_id = ensure_loc(event['destination_id'], event['destination'], event['destination_usage'])
            nodes[ev_id] = {
                'id': ev_id,
                'label': event['document'],
                'subtitle': event['type_label'],
                'kind': 'event',
                'tone': event['tone'],
                'event_index': idx,
                'qty': event['qty'],
                'uom': event['uom'],
                'value_fmt': event.get('value_fmt'),
                'supplier': event.get('supplier'),
                'customer': event.get('customer'),
            }
            edges.append({
                'id': f'e-{event["id"]}-in',
                'from': src_id,
                'to': ev_id,
                'label': '',
                'edge_type': 'location_to_event',
            })
            edges.append({
                'id': f'e-{event["id"]}-out',
                'from': ev_id,
                'to': dst_id,
                'label': f"{event['qty']} {event['uom']}",
                'edge_type': 'event_to_location',
            })
            if prev_dest and prev_dest != src_id:
                edges.append({
                    'id': f'chain-{idx}',
                    'from': prev_dest,
                    'to': src_id,
                    'label': '',
                    'edge_type': 'chain',
                    'dashed': True,
                })
            branch_map.setdefault(src_id, []).append(ev_id)
            prev_dest = dst_id

        branches = [
            {'from': src, 'targets': targets}
            for src, targets in branch_map.items()
            if len(targets) > 1
        ]
        return {
            'nodes': list(nodes.values()),
            'edges': edges,
            'branches': branches,
        }

    @api.model
    def _location_kind(self, usage):
        mapping = {
            'supplier': 'supplier',
            'customer': 'customer',
            'internal': 'internal',
            'inventory': 'inventory',
            'production': 'production',
            'transit': 'transit',
        }
        return mapping.get(usage, 'other')

    @api.model
    def _product_payload(self, product, parsed):
        tmpl = product.product_tmpl_id
        tracking_labels = {'none': _('Sin seguimiento'), 'lot': _('Por lote'), 'serial': _('Por número de serie')}
        lot_info = None
        if parsed.get('lot_id'):
            lot = self.env['stock.lot'].browse(parsed['lot_id'])
            if lot.exists():
                lot_info = {
                    'id': lot.id, 'name': lot.name,
                    'create_date': fields.Datetime.to_string(lot.create_date),
                    'product_qty': lot.product_qty,
                }
        payload = {
            'id': product.id,
            'tmpl_id': tmpl.id,
            'name': product.display_name,
            'default_code': product.default_code or tmpl.default_code or '',
            'barcode': product.barcode or '',
            'category': tmpl.categ_id.complete_name if tmpl.categ_id else '',
            'uom': product.uom_id.name,
            'tracking': product.tracking,
            'tracking_label': tracking_labels.get(product.tracking, product.tracking),
            'image_url': f'/web/image/product.product/{product.id}/image_128',
            'lot': lot_info,
        }
        if self._costs_enabled():
            product_ctx = product.with_company(parsed.get('company_id', self.env.company.id))
            currency = self._company_currency(parsed)
            cost_method_labels = {
                'standard': _('Estándar'),
                'average': _('Promedio (AVCO)'),
                'fifo': _('FIFO'),
            }
            payload.update({
                'avg_cost': product_ctx.avg_cost,
                'avg_cost_fmt': self._format_money(product_ctx.avg_cost, currency)['amount_fmt'],
                'total_value': product_ctx.total_value,
                'total_value_fmt': self._format_money(product_ctx.total_value, currency)['amount_fmt'],
                'cost_method': product_ctx.cost_method,
                'cost_method_label': cost_method_labels.get(product_ctx.cost_method, product_ctx.cost_method),
            })
        return payload


def _format_datetime(env, dt):
    if not dt:
        return '—'
    return fields.Datetime.context_timestamp(env.user, dt).strftime('%d/%m/%Y %H:%M')
