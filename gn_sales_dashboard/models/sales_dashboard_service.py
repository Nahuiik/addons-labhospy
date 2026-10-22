# -*- coding: utf-8 -*-
"""Servicio analítico del Dashboard de Ventas Premium."""

import logging
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

PERIOD_PRESETS = (
    'today', 'yesterday', 'this_week', 'this_month', 'this_quarter',
    'this_year', 'last_30', 'last_90', 'custom',
)
COMPARE_MODES = ('none', 'previous', 'yoy')
ORDER_STATES = ('sale', 'done')
INVOICE_TYPES = ('out_invoice', 'out_refund', 'out_receipt')
CRM_OPEN_TYPES = ('opportunity', 'lead')


class SalesDashboardService(models.AbstractModel):
    _name = 'sales.dashboard.service'
    _description = 'Sales Dashboard Premium Data Service'

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @api.model
    def _check_dashboard_access(self):
        if not self.env.user.has_group('gn_sales_dashboard.group_sales_dashboard_user'):
            raise AccessError(_('No tiene permiso para acceder al Dashboard de Ventas.'))

    # ------------------------------------------------------------------
    # Public RPC
    # ------------------------------------------------------------------

    @api.model
    def get_filter_options(self):
        self._check_dashboard_access()
        company = self.env.company
        branches = self.env['res.branch'].search([('company_id', 'in', company.ids)], order='name')
        teams = self.env['crm.team'].search([
            ('company_id', 'in', [False, company.id]),
        ], order='name')
        users = self.env['res.users'].search([
            ('share', '=', False),
            ('company_ids', 'in', company.ids),
        ], order='name', limit=200)
        journals = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', 'sale'),
        ], order='name')
        warehouses = []
        if 'stock.warehouse' in self.env:
            warehouses = self.env['stock.warehouse'].search([
                ('company_id', '=', company.id),
            ], order='name')
        categories = self.env['product.category'].search([], order='complete_name', limit=500)
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
            'order_states': [
                {'id': 'sale', 'label': _('Pedido de venta')},
                {'id': 'done', 'label': _('Bloqueado')},
            ],
            'branches': [{'id': b.id, 'name': b.name} for b in branches],
            'teams': [{'id': t.id, 'name': t.name} for t in teams],
            'users': [{'id': u.id, 'name': u.name} for u in users],
            'journals': [{'id': j.id, 'name': j.name} for j in journals],
            'warehouses': [{'id': w.id, 'name': w.name} for w in warehouses],
            'categories': [{'id': c.id, 'name': c.display_name} for c in categories],
            'channels': self._channel_options(),
            'sparkline_days_presets': [
                {'id': 7, 'label': _('7 días')},
                {'id': 30, 'label': _('30 días')},
                {'id': 90, 'label': _('90 días')},
            ],
        }

    @api.model
    def get_dashboard_core(self, filters=None, sparkline_days=30):
        """Carga principal: encabezado, KPIs y gráfico hero."""
        self._check_dashboard_access()
        t0 = time.time()
        cache = {}
        parsed = self._parse_filters(filters or {})
        compare_parsed = self._comparison_parsed(parsed)
        current = self._compute_metrics(parsed, cache)
        previous = self._compute_metrics(compare_parsed, cache) if compare_parsed else {}
        kpis = self._build_kpi_cards(parsed, current, previous, cache, sparkline_days)
        hero = self._build_hero_chart(parsed, compare_parsed, cache)
        duration_ms = int((time.time() - t0) * 1000)
        return {
            'success': True,
            'filters': self._filters_payload(parsed),
            'currency': self._currency_payload(parsed),
            'header': self._build_header(parsed, duration_ms),
            'kpis': kpis,
            'charts': {'hero_sales': hero},
            'metadata': {
                'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
                'duration_ms': duration_ms,
                'company_ids': parsed['company'].ids,
                'data_sources': {
                    'invoicing': _('Facturas publicadas (out_invoice/out_refund)'),
                    'orders': _('Pedidos confirmados (sale/done)'),
                    'pipeline': _('Oportunidades CRM abiertas'),
                },
            },
        }

    @api.model
    def get_dashboard_init(self, filters=None, sparkline_days=30):
        """Carga inicial en un solo RPC: core + resumen avanzado (health, meta, alertas)."""
        self._check_dashboard_access()
        t0 = time.time()
        cache = {}
        parsed = self._parse_filters(filters or {})
        compare_parsed = self._comparison_parsed(parsed)
        current = self._compute_metrics(parsed, cache)
        previous = self._compute_metrics(compare_parsed, cache) if compare_parsed else {}
        kpis = self._build_kpi_cards(parsed, current, previous, cache, sparkline_days)
        hero = self._build_hero_chart(parsed, compare_parsed, cache)
        duration_ms = int((time.time() - t0) * 1000)
        core = {
            'success': True,
            'filters': self._filters_payload(parsed),
            'currency': self._currency_payload(parsed),
            'header': self._build_header(parsed, duration_ms),
            'kpis': kpis,
            'charts': {'hero_sales': hero},
            'metadata': {
                'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
                'duration_ms': duration_ms,
                'company_ids': parsed['company'].ids,
            },
        }
        advanced = self._build_summary_advanced(
            parsed, cache, metrics=current, prev_metrics=previous,
        )
        return {
            'success': True,
            'core': core,
            'advanced': advanced,
            'duration_ms': duration_ms,
        }

    @api.model
    def get_drilldown_action(self, metric, extra_domain=None, filters=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        return self._drilldown_action(parsed, metric, extra_domain or [])

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    @api.model
    def _channel_options(self):
        SaleOrder = self.env['sale.order']
        if 'source_id' in SaleOrder._fields:
            sources = self.env['utm.source'].search([], order='name', limit=200)
            return [{'id': s.id, 'name': s.name} for s in sources]
        return []

    @api.model
    def _resolve_period(self, filters):
        preset = filters.get('period') or 'this_month'
        today = fields.Date.context_today(self)
        if preset == 'today':
            return preset, today, today
        if preset == 'yesterday':
            y = today - timedelta(days=1)
            return preset, y, y
        if preset == 'this_week':
            return preset, today - timedelta(days=today.weekday()), today
        if preset == 'this_month':
            return preset, today.replace(day=1), today
        if preset == 'this_quarter':
            q = (today.month - 1) // 3
            return preset, date(today.year, q * 3 + 1, 1), today
        if preset == 'this_year':
            return preset, date(today.year, 1, 1), today
        if preset == 'last_30':
            return preset, today - timedelta(days=29), today
        if preset == 'last_90':
            return preset, today - timedelta(days=89), today
        if preset == 'custom':
            df = filters.get('date_from') or today.replace(day=1)
            dt = filters.get('date_to') or today
            if isinstance(df, str):
                df = fields.Date.from_string(df)
            if isinstance(dt, str):
                dt = fields.Date.from_string(dt)
            if df > dt:
                raise UserError(_('La fecha inicial no puede ser posterior a la final.'))
            return preset, df, dt
        return 'this_month', today.replace(day=1), today

    @api.model
    def _parse_filters(self, filters):
        company_id = filters.get('company_id') or self.env.company.id
        company = self.env['res.company'].browse(company_id)
        if company.id not in self.env.companies.ids:
            company = self.env.company
        preset, date_from, date_to = self._resolve_period(filters)
        compare = filters.get('compare_mode') or 'previous'
        if compare not in COMPARE_MODES:
            compare = 'previous'
        return {
            'company': company,
            'period': preset,
            'date_from': date_from,
            'date_to': date_to,
            'compare_mode': compare,
            'branch_id': filters.get('branch_id') or False,
            'team_id': filters.get('team_id') or False,
            'user_id': filters.get('user_id') or False,
            'journal_id': filters.get('journal_id') or False,
            'warehouse_id': filters.get('warehouse_id') or False,
            'channel_id': filters.get('channel_id') or False,
            'partner_id': filters.get('partner_id') or False,
            'category_id': filters.get('category_id') or False,
            'product_id': filters.get('product_id') or False,
            'order_state': filters.get('order_state') or False,
            'currency_id': filters.get('currency_id') or company.currency_id.id,
        }

    @api.model
    def _comparison_parsed(self, parsed):
        mode = parsed.get('compare_mode', 'previous')
        if mode == 'none':
            return None
        if mode == 'yoy':
            df = parsed['date_from'].replace(year=parsed['date_from'].year - 1)
            dt = parsed['date_to'].replace(year=parsed['date_to'].year - 1)
            return {**parsed, 'date_from': df, 'date_to': dt}
        delta = (parsed['date_to'] - parsed['date_from']).days + 1
        prev_end = parsed['date_from'] - timedelta(days=1)
        prev_start = prev_end - timedelta(days=delta - 1)
        return {**parsed, 'date_from': prev_start, 'date_to': prev_end}

    @api.model
    def _filters_payload(self, parsed):
        return {
            'company_id': parsed['company'].id,
            'period': parsed['period'],
            'compare_mode': parsed['compare_mode'],
            'date_from': fields.Date.to_string(parsed['date_from']),
            'date_to': fields.Date.to_string(parsed['date_to']),
            'branch_id': parsed.get('branch_id') or False,
            'team_id': parsed.get('team_id') or False,
            'user_id': parsed.get('user_id') or False,
            'journal_id': parsed.get('journal_id') or False,
            'warehouse_id': parsed.get('warehouse_id') or False,
            'channel_id': parsed.get('channel_id') or False,
            'partner_id': parsed.get('partner_id') or False,
            'category_id': parsed.get('category_id') or False,
            'product_id': parsed.get('product_id') or False,
            'order_state': parsed.get('order_state') or False,
        }

    @api.model
    def _currency_payload(self, parsed):
        currency = self.env['res.currency'].browse(parsed['currency_id'])
        if not currency.exists():
            currency = parsed['company'].currency_id
        return {
            'id': currency.id,
            'symbol': currency.symbol,
            'position': currency.position,
            'decimal_places': currency.decimal_places,
        }

    @api.model
    def _build_header(self, parsed, duration_ms):
        period_label = dict(
            (p['id'], p['label']) for p in [
                {'id': 'today', 'label': _('Hoy')},
                {'id': 'this_month', 'label': _('Mes actual')},
            ]
        ).get(parsed['period'], parsed['period'])
        return {
            'title': _('Dashboard de Ventas'),
            'period_label': period_label,
            'date_from': fields.Date.to_string(parsed['date_from']),
            'date_to': fields.Date.to_string(parsed['date_to']),
            'compare_mode': parsed['compare_mode'],
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'duration_ms': duration_ms,
        }

    # ------------------------------------------------------------------
    # Request-scoped cache (evita releer facturas/pedidos en el mismo RPC)
    # ------------------------------------------------------------------

    @api.model
    def _period_cache_key(self, parsed):
        return (
            parsed['company'].id,
            parsed['date_from'],
            parsed['date_to'],
            parsed.get('branch_id') or 0,
            parsed.get('team_id') or 0,
            parsed.get('user_id') or 0,
            parsed.get('journal_id') or 0,
            parsed.get('warehouse_id') or 0,
            parsed.get('channel_id') or 0,
            parsed.get('partner_id') or 0,
            parsed.get('category_id') or 0,
            parsed.get('product_id') or 0,
            parsed.get('order_state') or '',
        )

    @api.model
    def _cache_get(self, cache, key, loader):
        if cache is None:
            return loader()
        if key not in cache:
            cache[key] = loader()
        return cache[key]

    # ------------------------------------------------------------------
    # Domains
    # ------------------------------------------------------------------

    @api.model
    def _has_branch(self):
        return 'branch_id' in self.env['account.move']._fields

    @api.model
    def _invoice_base_domain(self, parsed):
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('move_type', 'in', list(INVOICE_TYPES)),
            ('state', '=', 'posted'),
        ]
        if parsed.get('branch_id') and self._has_branch():
            domain.append(('branch_id', '=', parsed['branch_id']))
        if parsed.get('journal_id'):
            domain.append(('journal_id', '=', parsed['journal_id']))
        if parsed.get('user_id'):
            field = 'invoice_user_id' if 'invoice_user_id' in self.env['account.move']._fields else 'user_id'
            domain.append((field, '=', parsed['user_id']))
        if parsed.get('partner_id'):
            domain.append(('partner_id', '=', parsed['partner_id']))
        return domain

    @api.model
    def _invoice_period_domain(self, parsed):
        return self._invoice_base_domain(parsed) + [
            ('invoice_date', '>=', parsed['date_from']),
            ('invoice_date', '<=', parsed['date_to']),
        ]

    @api.model
    def _invoices_in_period(self, parsed, cache=None):
        key = ('invoices', self._period_cache_key(parsed))
        return self._cache_get(cache, key, lambda: self.env['account.move'].search(
            self._invoice_period_domain(parsed),
        ))

    @api.model
    def _order_period_domain(self, parsed):
        df = fields.Datetime.to_datetime(parsed['date_from'])
        dt = fields.Datetime.to_datetime(parsed['date_to'] + timedelta(days=1))
        return self._order_base_domain(parsed) + [
            ('date_order', '>=', df),
            ('date_order', '<', dt),
        ]

    @api.model
    def _orders_in_period(self, parsed, cache=None):
        key = ('orders', self._period_cache_key(parsed))
        return self._cache_get(cache, key, lambda: self.env['sale.order'].search(
            self._order_period_domain(parsed),
        ))

    @api.model
    def _order_base_domain(self, parsed):
        states = [parsed['order_state']] if parsed.get('order_state') else list(ORDER_STATES)
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('state', 'in', states),
        ]
        if parsed.get('branch_id') and 'branch_id' in self.env['sale.order']._fields:
            domain.append(('branch_id', '=', parsed['branch_id']))
        if parsed.get('team_id'):
            domain.append(('team_id', '=', parsed['team_id']))
        if parsed.get('user_id'):
            domain.append(('user_id', '=', parsed['user_id']))
        if parsed.get('partner_id'):
            domain.append(('partner_id', '=', parsed['partner_id']))
        if parsed.get('warehouse_id') and 'warehouse_id' in self.env['sale.order']._fields:
            domain.append(('warehouse_id', '=', parsed['warehouse_id']))
        if parsed.get('channel_id') and 'source_id' in self.env['sale.order']._fields:
            domain.append(('source_id', '=', parsed['channel_id']))
        return domain

    @api.model
    def _crm_domain(self, parsed, extra=None):
        domain = [
            ('company_id', 'in', [False, parsed['company'].id]),
            ('type', '=', 'opportunity'),
            ('active', '=', True),
        ]
        if parsed.get('team_id'):
            domain.append(('team_id', '=', parsed['team_id']))
        if parsed.get('user_id'):
            domain.append(('user_id', '=', parsed['user_id']))
        if extra:
            domain.extend(extra)
        return domain

    # ------------------------------------------------------------------
    # Amount helpers
    # ------------------------------------------------------------------

    @api.model
    def _invoice_signed_untaxed(self, move):
        """Importe sin impuestos con signo: NC restan, facturas suman."""
        amt = move.amount_untaxed or 0.0
        if move.move_type == 'out_refund':
            return -abs(amt)
        if move.move_type in ('out_invoice', 'out_receipt'):
            return amt
        return 0.0

    @api.model
    def _invoice_gross_untaxed(self, move):
        if move.move_type == 'out_invoice':
            return move.amount_untaxed or 0.0
        return 0.0

    @api.model
    def _invoice_credit_untaxed(self, move):
        if move.move_type == 'out_refund':
            return abs(move.amount_untaxed or 0.0)
        return 0.0

    @api.model
    def _line_margin_amount(self, line):
        """Margen bruto por línea de factura: subtotal − costo estándar × cantidad."""
        if line.display_type in ('line_section', 'line_note'):
            return 0.0
        if not line.product_id:
            return 0.0
        qty = line.quantity or 0.0
        if not qty:
            return 0.0
        cost = line.product_id.standard_price or 0.0
        if 'purchase_price' in line._fields and line.purchase_price:
            cost = line.purchase_price
        revenue = line.price_subtotal or 0.0
        sign = -1 if line.move_id.move_type == 'out_refund' else 1
        return sign * (revenue - cost * qty)

    @api.model
    def _aggregate_invoices(self, invoices, cache=None):
        if not invoices:
            return {
                'net_sales': 0.0, 'gross_invoicing': 0.0, 'credit_notes': 0.0,
                'gross_margin': 0.0, 'invoice_count': 0, 'invoice_ids': [],
                'credit_note_ids': [], 'partner_ids': [],
            }
        agg_key = ('inv_agg', tuple(invoices.ids))
        if cache is not None and agg_key in cache:
            return cache[agg_key]

        net = gross = credits = margin = 0.0
        partner_ids = set()
        invoice_ids = []
        credit_ids = []
        margin_by_move = defaultdict(float)

        lines = self.env['account.move.line'].search([
            ('move_id', 'in', invoices.ids),
            ('display_type', '=', False),
            ('product_id', '!=', False),
        ])
        move_types = {m.id: m.move_type for m in invoices}
        for line in lines:
            move_type = move_types.get(line.move_id.id)
            if not move_type:
                continue
            qty = line.quantity or 0.0
            if not qty:
                continue
            cost = line.product_id.standard_price or 0.0
            if 'purchase_price' in line._fields and line.purchase_price:
                cost = line.purchase_price
            revenue = line.price_subtotal or 0.0
            sign = -1 if move_type == 'out_refund' else 1
            margin_by_move[line.move_id.id] += sign * (revenue - cost * qty)

        for inv in invoices:
            invoice_ids.append(inv.id)
            net += self._invoice_signed_untaxed(inv)
            gross += self._invoice_gross_untaxed(inv)
            cr = self._invoice_credit_untaxed(inv)
            credits += cr
            if cr:
                credit_ids.append(inv.id)
            if inv.partner_id:
                partner_ids.add(inv.partner_id.id)
            margin += margin_by_move.get(inv.id, 0.0)

        result = {
            'net_sales': net,
            'gross_invoicing': gross,
            'credit_notes': credits,
            'gross_margin': margin,
            'invoice_count': len(invoice_ids),
            'invoice_ids': invoice_ids,
            'credit_note_ids': credit_ids,
            'partner_ids': list(partner_ids),
        }
        if cache is not None:
            cache[agg_key] = result
        return result

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @api.model
    def _compute_metrics(self, parsed, cache=None):
        if not parsed:
            return {}
        metrics_key = ('metrics', self._period_cache_key(parsed))
        if cache is not None and metrics_key in cache:
            return cache[metrics_key]

        invoices = self._invoices_in_period(parsed, cache)
        inv_agg = self._aggregate_invoices(invoices, cache)
        orders = self._orders_in_period(parsed, cache)
        order_net = sum(o.amount_untaxed for o in orders)
        order_ids = orders.ids

        net = inv_agg['net_sales']
        margin = inv_agg['gross_margin']
        inv_count = inv_agg['invoice_count']
        avg_ticket = net / inv_count if inv_count else 0.0
        margin_pct = (margin / net * 100.0) if net else 0.0

        active_customers = len(inv_agg['partner_ids'])
        new_customers = self._count_new_customers(parsed, inv_agg['partner_ids'])

        pipeline_domain = self._crm_domain(parsed, [('probability', '<', 100)])
        pipeline_rows = self.env['crm.lead'].search_read(
            pipeline_domain, ['expected_revenue', 'probability'],
        )
        pipeline_ids = [r['id'] for r in pipeline_rows]
        pipeline_value = sum(r['expected_revenue'] or 0.0 for r in pipeline_rows)
        forecast_close = sum(
            (r['expected_revenue'] or 0.0) * (r['probability'] or 0.0) / 100.0
            for r in pipeline_rows
        )

        won_domain = self._crm_domain(parsed)
        won_extra = [('probability', '=', 100)]
        if 'stage_id' in self.env['crm.lead']._fields:
            won_extra = ['|', ('probability', '=', 100), ('stage_id.is_won', '=', True)]
        if 'date_closed' in self.env['crm.lead']._fields:
            won = self.env['crm.lead'].search(won_domain + won_extra + [
                ('date_closed', '>=', parsed['date_from']),
                ('date_closed', '<=', parsed['date_to']),
            ])
        else:
            won = self.env['crm.lead'].search(won_domain + won_extra + [
                ('write_date', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
                ('write_date', '<',
                 fields.Datetime.to_datetime(parsed['date_to'] + timedelta(days=1))),
            ], limit=500)
        total_leads = self.env['crm.lead'].search_count(
            self._crm_domain(parsed) + [
                ('create_date', '>=', fields.Datetime.to_datetime(parsed['date_from'])),
                ('create_date', '<',
                 fields.Datetime.to_datetime(parsed['date_to'] + timedelta(days=1))),
            ]
        )
        conversion_rate = (len(won) / total_leads * 100.0) if total_leads else 0.0

        target_amount, target_pct = self._target_for_period(parsed, net)

        result = {
            'net_sales': {'value': net, 'ids': inv_agg['invoice_ids'], 'source': 'invoice'},
            'gross_invoicing': {'value': inv_agg['gross_invoicing'], 'ids': inv_agg['invoice_ids'], 'source': 'invoice'},
            'credit_notes': {'value': inv_agg['credit_notes'], 'ids': inv_agg['credit_note_ids'], 'source': 'invoice'},
            'order_count': {'value': len(order_ids), 'ids': order_ids, 'source': 'order'},
            'order_amount': {'value': order_net, 'ids': order_ids, 'source': 'order'},
            'invoice_count': {'value': inv_count, 'ids': inv_agg['invoice_ids'], 'source': 'invoice'},
            'avg_ticket': {'value': avg_ticket, 'ids': inv_agg['invoice_ids'], 'source': 'invoice'},
            'gross_margin': {'value': margin, 'ids': inv_agg['invoice_ids'], 'source': 'invoice'},
            'margin_pct': {'value': margin_pct, 'ids': inv_agg['invoice_ids'], 'source': 'invoice'},
            'active_customers': {'value': active_customers, 'ids': inv_agg['partner_ids'], 'source': 'partner'},
            'new_customers': {'value': new_customers, 'ids': [], 'source': 'partner'},
            'conversion_rate': {'value': conversion_rate, 'ids': won.ids, 'source': 'crm'},
            'pipeline_open': {'value': pipeline_value, 'ids': pipeline_ids, 'source': 'crm'},
            'forecast_close': {'value': forecast_close, 'ids': pipeline_ids, 'source': 'crm'},
            'target_achievement': {'value': target_pct, 'target': target_amount, 'source': 'target'},
            'returns': {'value': inv_agg['credit_notes'], 'ids': inv_agg['credit_note_ids'], 'source': 'invoice'},
        }
        if cache is not None:
            cache[metrics_key] = result
        return result

    @api.model
    def _count_new_customers(self, parsed, partner_ids):
        if not partner_ids:
            return 0
        self.env.cr.execute("""
            SELECT COUNT(*) FROM (
                SELECT am.partner_id
                FROM account_move am
                WHERE am.company_id = %s
                  AND am.move_type IN ('out_invoice', 'out_receipt')
                  AND am.state = 'posted'
                  AND am.partner_id = ANY(%s)
                GROUP BY am.partner_id
                HAVING MIN(am.invoice_date) >= %s
                   AND MIN(am.invoice_date) <= %s
            ) sub
        """, (
            parsed['company'].id,
            list(partner_ids),
            parsed['date_from'],
            parsed['date_to'],
        ))
        row = self.env.cr.fetchone()
        return row[0] if row else 0

    @api.model
    def _target_for_period(self, parsed, net_sales):
        Target = self.env.get('commission.target')
        if not Target:
            return 0.0, 0.0
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('period_start', '<=', parsed['date_to']),
            ('period_end', '>=', parsed['date_from']),
        ]
        if parsed.get('branch_id'):
            domain += [('scope', '=', 'branch'), ('branch_id', '=', parsed['branch_id'])]
        targets = Target.search(domain)
        target_amount = sum(targets.mapped('target_amount'))
        if not target_amount:
            return 0.0, 0.0
        return target_amount, (net_sales / target_amount * 100.0) if target_amount else 0.0

    # ------------------------------------------------------------------
    # KPI cards
    # ------------------------------------------------------------------

    @api.model
    def _kpi_catalog(self):
        return {
            'net_sales': {
                'label': _('Ventas netas'),
                'icon': 'fa-line-chart',
                'format': 'currency',
                'tone': 'primary',
                'tooltip': _('Facturas publicadas menos notas de crédito (sin impuestos). Fuente: contabilidad.'),
            },
            'gross_invoicing': {
                'label': _('Facturación bruta'),
                'icon': 'fa-file-text-o',
                'format': 'currency',
                'tone': 'info',
                'tooltip': _('Total facturas de cliente publicadas, sin restar notas de crédito.'),
            },
            'credit_notes': {
                'label': _('Notas de crédito'),
                'icon': 'fa-undo',
                'format': 'currency',
                'tone': 'warning',
                'tooltip': _('Notas de crédito publicadas del período (valor absoluto).'),
            },
            'order_count': {
                'label': _('Pedidos'),
                'icon': 'fa-shopping-cart',
                'format': 'count',
                'tone': 'neutral',
                'tooltip': _('Pedidos confirmados (sale/done) por fecha del pedido.'),
            },
            'invoice_count': {
                'label': _('Facturas'),
                'icon': 'fa-files-o',
                'format': 'count',
                'tone': 'neutral',
                'tooltip': _('Cantidad de documentos contables publicados en el período.'),
            },
            'avg_ticket': {
                'label': _('Ticket promedio'),
                'icon': 'fa-ticket',
                'format': 'currency',
                'tone': 'info',
                'tooltip': _('Ventas netas / cantidad de facturas publicadas.'),
            },
            'gross_margin': {
                'label': _('Margen bruto'),
                'icon': 'fa-pie-chart',
                'format': 'currency',
                'tone': 'success',
                'tooltip': _('Subtotal de líneas − costo estándar × cantidad. Fuente: facturas.'),
            },
            'margin_pct': {
                'label': _('% Margen'),
                'icon': 'fa-percent',
                'format': 'percent',
                'tone': 'success',
                'tooltip': _('Margen bruto / ventas netas × 100.'),
            },
            'growth': {
                'label': _('Crecimiento'),
                'icon': 'fa-arrow-up',
                'format': 'percent',
                'tone': 'primary',
                'tooltip': _('Variación de ventas netas vs período de comparación.'),
            },
            'active_customers': {
                'label': _('Clientes activos'),
                'icon': 'fa-users',
                'format': 'count',
                'tone': 'info',
                'tooltip': _('Clientes con al menos una factura en el período.'),
            },
            'new_customers': {
                'label': _('Clientes nuevos'),
                'icon': 'fa-user-plus',
                'format': 'count',
                'tone': 'success',
                'tooltip': _('Clientes cuya primera factura cae en el período.'),
            },
            'conversion_rate': {
                'label': _('Tasa de conversión'),
                'icon': 'fa-filter',
                'format': 'percent',
                'tone': 'info',
                'tooltip': _('Oportunidades ganadas / oportunidades creadas en el período.'),
            },
            'pipeline_open': {
                'label': _('Pipeline abierto'),
                'icon': 'fa-sitemap',
                'format': 'currency',
                'tone': 'info',
                'tooltip': _('Valor esperado de oportunidades abiertas (CRM).'),
            },
            'forecast_close': {
                'label': _('Pronóstico de cierre'),
                'icon': 'fa-bullseye',
                'format': 'currency',
                'tone': 'primary',
                'tooltip': _('Suma de ingreso esperado × probabilidad de oportunidades abiertas.'),
            },
            'target_achievement': {
                'label': _('Cumplimiento de meta'),
                'icon': 'fa-flag-checkered',
                'format': 'percent',
                'tone': 'primary',
                'tooltip': _('Ventas netas vs meta del período (commission.target si existe).'),
            },
            'returns': {
                'label': _('Devoluciones'),
                'icon': 'fa-reply',
                'format': 'currency',
                'tone': 'warning',
                'tooltip': _('Notas de crédito del período.'),
            },
        }

    @api.model
    def _variation_pct(self, current, previous):
        if not previous:
            return 0.0 if not current else 100.0
        return ((current - previous) / abs(previous)) * 100.0

    @api.model
    def _build_kpi_cards(self, parsed, current, previous, cache=None, sparkline_days=14):
        cards = []
        net = current.get('net_sales', {}).get('value', 0.0)
        prev_net = previous.get('net_sales', {}).get('value', 0.0)
        growth = self._variation_pct(net, prev_net)

        metrics = dict(current)
        metrics['growth'] = {'value': growth, 'ids': current.get('net_sales', {}).get('ids', []), 'source': 'invoice'}

        end = parsed['date_to']
        start = max(parsed['date_from'], end - timedelta(days=sparkline_days - 1))
        spark_parsed = {**parsed, 'date_from': start, 'date_to': end}
        spark_by_day = self._daily_net_sales_map(spark_parsed, cache)
        spark_points = []
        cur = start
        while cur <= end:
            spark_points.append(spark_by_day.get(fields.Date.to_string(cur), 0.0))
            cur += timedelta(days=1)

        for key, meta in self._kpi_catalog().items():
            data = metrics.get(key, {})
            val = data.get('value', 0.0)
            prev_val = previous.get(key, {}).get('value', 0.0) if key != 'growth' else prev_net
            var = growth if key == 'growth' else self._variation_pct(val, prev_val)
            tone = meta['tone']
            if key in ('growth', 'margin_pct', 'target_achievement', 'conversion_rate'):
                if val >= 0:
                    tone = 'success' if val >= (data.get('target') or 0) or key == 'growth' else meta['tone']
                elif val < 0:
                    tone = 'danger'
            cards.append({
                'key': key,
                'metric': key,
                'label': meta['label'],
                'icon': meta['icon'],
                'format': meta['format'],
                'tone': tone,
                'tooltip': meta['tooltip'],
                'value': val,
                'previous_value': prev_val,
                'variation_pct': var,
                'target': data.get('target'),
                'source': data.get('source', ''),
                'sparkline': spark_points if key in ('net_sales', 'gross_invoicing') else [],
            })
        return cards

    @api.model
    def _daily_net_sales_map(self, parsed, cache=None):
        """Ventas netas por día en una sola pasada ORM."""
        key = ('daily_net', self._period_cache_key(parsed))
        if cache is not None and key in cache:
            return cache[key]
        invoices = self._invoices_in_period(parsed, cache)
        by_day = defaultdict(float)
        for inv in invoices:
            if not inv.invoice_date:
                continue
            day_key = fields.Date.to_string(inv.invoice_date)
            by_day[day_key] += self._invoice_signed_untaxed(inv)
        if cache is not None:
            cache[key] = by_day
        return by_day

    @api.model
    def _build_hero_chart(self, parsed, compare_parsed, cache=None):
        by_day = self._daily_net_sales_map(parsed, cache)
        cmp_by_day = self._daily_net_sales_map(compare_parsed, cache) if compare_parsed else {}
        labels, current_series, previous_series, target_series = [], [], [], []
        target_amount, _pct = self._target_for_period(parsed, 0.0)
        days_in_period = (parsed['date_to'] - parsed['date_from']).days + 1
        daily_target = target_amount / days_in_period if days_in_period and target_amount else 0.0
        delta = days_in_period

        cur = parsed['date_from']
        while cur <= parsed['date_to']:
            key = fields.Date.to_string(cur)
            labels.append(key)
            current_series.append(by_day.get(key, 0.0))
            if compare_parsed:
                if parsed['compare_mode'] == 'yoy':
                    cmp_date = cur.replace(year=cur.year - 1)
                else:
                    cmp_date = compare_parsed['date_from'] + timedelta(
                        days=(cur - parsed['date_from']).days
                    )
                cmp_key = fields.Date.to_string(cmp_date)
                previous_series.append(cmp_by_day.get(cmp_key, 0.0))
            else:
                previous_series.append(0.0)
            target_series.append(daily_target)
            cur += timedelta(days=1)

        return {
            'id': 'hero_sales',
            'title': _('Tendencia de ventas netas'),
            'subtitle': _('Fuente: facturas publicadas (sin impuestos)'),
            'labels': labels,
            'series': [
                {'name': _('Ventas netas'), 'key': 'current', 'data': current_series, 'type': 'line'},
                {'name': _('Comparación'), 'key': 'previous', 'data': previous_series, 'type': 'line'},
                {'name': _('Meta diaria'), 'key': 'target', 'data': target_series, 'type': 'line'},
            ],
            'drilldown': {'enabled': True, 'metric': 'net_sales'},
        }

    # ------------------------------------------------------------------
    # Drill-down actions (Odoo 19 requires ``views``)
    # ------------------------------------------------------------------

    @api.model
    def _views_for_mode(self, view_mode):
        views = []
        for mode in (view_mode or 'list,form').split(','):
            mode = mode.strip()
            if mode == 'tree':
                mode = 'list'
            if mode in ('list', 'form', 'kanban', 'graph', 'pivot'):
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
    def _drilldown_action(self, parsed, metric, extra_domain):
        metrics = self._compute_metrics(parsed)
        meta = metrics.get(metric, {})
        ids = meta.get('ids') or []
        source = meta.get('source', 'invoice')

        model_map = {
            'net_sales': 'account.move',
            'gross_invoicing': 'account.move',
            'credit_notes': 'account.move',
            'returns': 'account.move',
            'invoice_count': 'account.move',
            'avg_ticket': 'account.move',
            'gross_margin': 'account.move',
            'margin_pct': 'account.move',
            'order_count': 'sale.order',
            'order_amount': 'sale.order',
            'active_customers': 'res.partner',
            'new_customers': 'res.partner',
            'conversion_rate': 'crm.lead',
            'pipeline_open': 'crm.lead',
            'forecast_close': 'crm.lead',
            'growth': 'account.move',
        }
        res_model = model_map.get(metric, 'account.move')

        if ids:
            domain = [('id', 'in', ids)] + list(extra_domain)
        elif source == 'invoice':
            domain = self._invoice_base_domain(parsed) + [
                ('invoice_date', '>=', parsed['date_from']),
                ('invoice_date', '<=', parsed['date_to']),
            ] + list(extra_domain)
        elif source == 'order':
            domain = self._order_base_domain(parsed) + list(extra_domain)
        elif source == 'crm':
            domain = self._crm_domain(parsed) + list(extra_domain)
        else:
            domain = [('id', '=', 0)]

        label = self._kpi_catalog().get(metric, {}).get('label', metric)
        ctx = {'create': False}
        if res_model == 'crm.lead':
            ctx['search_default_opportunity'] = 1
        return self._act_window_action(label, res_model, 'list,form', domain, ctx)
