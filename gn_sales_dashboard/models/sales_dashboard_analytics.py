# -*- coding: utf-8 -*-
"""Analytics Fase 2: rankings, productos, clientes, pipeline y tablas."""

import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

WIDGET_KEYS = (
    'seller_ranking', 'team_ranking', 'top_products', 'top_customers',
    'pipeline_funnel', 'pipeline_chart',
)

TABLE_REGISTRY = {
    'recent_invoices': {
        'model': 'account.move',
        'label_key': 'recent_invoices',
        'columns': [
            ('date', 'date', 'date'),
            ('name', 'name', 'char'),
            ('partner', 'partner', 'char'),
            ('salesperson', 'salesperson', 'char'),
            ('amount', 'amount', 'currency'),
            ('state', 'state', 'char'),
        ],
    },
    'recent_orders': {
        'model': 'sale.order',
        'label_key': 'recent_orders',
        'columns': [
            ('date', 'date', 'date'),
            ('name', 'name', 'char'),
            ('partner', 'partner', 'char'),
            ('salesperson', 'salesperson', 'char'),
            ('amount', 'amount', 'currency'),
            ('state', 'state', 'char'),
        ],
    },
    'top_customers_table': {
        'model': 'res.partner',
        'label_key': 'top_customers_table',
        'columns': [
            ('name', 'customer', 'char'),
            ('sales', 'net_sales_col', 'currency'),
            ('orders', 'orders', 'number'),
            ('avg_ticket', 'avg_ticket', 'currency'),
            ('last_purchase', 'last_purchase', 'date'),
        ],
    },
    'top_products_table': {
        'model': 'product.product',
        'label_key': 'top_products_table',
        'columns': [
            ('name', 'product', 'char'),
            ('sku', 'sku', 'char'),
            ('qty', 'qty', 'number'),
            ('sales', 'net_sales_col', 'currency'),
            ('margin', 'margin', 'currency'),
        ],
    },
}

TABLE_LABELS = {
    'recent_invoices': 'Facturas recientes',
    'recent_orders': 'Pedidos recientes',
    'top_customers_table': 'Top clientes',
    'top_products_table': 'Top productos',
}

COLUMN_LABELS = {
    'date': 'Fecha', 'name': 'Documento', 'partner': 'Cliente', 'salesperson': 'Vendedor',
    'amount': 'Total', 'state': 'Estado', 'customer': 'Cliente', 'net_sales_col': 'Ventas netas',
    'orders': 'Pedidos', 'avg_ticket': 'Ticket prom.', 'last_purchase': 'Última compra',
    'product': 'Producto', 'sku': 'SKU', 'qty': 'Cantidad', 'margin': 'Margen',
}


class SalesDashboardAnalytics(models.AbstractModel):
    _inherit = 'sales.dashboard.service'

    # ------------------------------------------------------------------
    # Public RPC — widgets lazy
    # ------------------------------------------------------------------

    @api.model
    def get_dashboard_widgets(self, filters=None, keys=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        cache = {}
        requested = keys or list(WIDGET_KEYS)
        out = {}
        builders = {
            'seller_ranking': self._build_seller_ranking,
            'team_ranking': self._build_team_ranking,
            'top_products': self._build_top_products,
            'top_customers': self._build_top_customers,
            'pipeline_funnel': self._build_pipeline_funnel,
            'pipeline_chart': self._build_pipeline_chart,
        }
        for key in requested:
            builder = builders.get(key)
            if builder:
                out[key] = builder(parsed, cache=cache)
        return {'success': True, 'widgets': out}

    @api.model
    def get_table_page(self, filters=None, table_key='recent_invoices', page=1,
                       page_size=25, search='', order=''):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        if table_key not in TABLE_REGISTRY:
            return {'rows': [], 'columns': [], 'total': 0, 'pages': 0, 'page': page}
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 25)))
        if table_key in ('recent_invoices', 'recent_orders'):
            return self._table_recent_documents(parsed, table_key, page, page_size, search, order)
        if table_key == 'top_customers_table':
            return self._table_top_customers(parsed, page, page_size, search, order)
        if table_key == 'top_products_table':
            return self._table_top_products(parsed, page, page_size, search, order)
        return {'rows': [], 'columns': [], 'total': 0, 'pages': 0, 'page': page}

    @api.model
    def get_entity_drilldown(self, filters=None, res_model=None, domain=None, name=None):
        """Drill-down genérico desde filas de ranking o pipeline."""
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        dom = list(domain or [])
        if res_model == 'account.move':
            dom = list(Domain.AND([
                domain or [],
                self._invoice_base_domain(parsed),
                [
                    ('invoice_date', '>=', parsed['date_from']),
                    ('invoice_date', '<=', parsed['date_to']),
                ],
            ]))
        elif res_model == 'account.move.line':
            inv_ids = self._invoices_in_period(parsed, None).ids
            dom = list(Domain.AND([domain or [], [('move_id', 'in', inv_ids or [0])]]))
        elif res_model == 'sale.order':
            dom = list(Domain.AND([domain or [], self._order_base_domain(parsed)]))
        elif res_model == 'crm.lead':
            dom = list(Domain.AND([domain or [], self._crm_domain(parsed)]))
        if not dom:
            dom = [('id', '=', 0)]
        return self._act_window_action(
            name or _('Registros'),
            res_model,
            'list,form',
            dom,
            {'create': False},
        )

    # ------------------------------------------------------------------
    # Rankings — vendedores
    # ------------------------------------------------------------------

    @api.model
    def _salesperson_field(self):
        Move = self.env['account.move']
        if 'invoice_user_id' in Move._fields:
            return 'invoice_user_id'
        return 'user_id'

    @api.model
    def _build_seller_ranking(self, parsed, limit=15, cache=None):
        invoices = self._invoices_in_period(parsed, cache)
        sp_field = self._salesperson_field()
        buckets = defaultdict(lambda: {
            'sales': 0.0, 'margin': 0.0, 'invoices': 0, 'invoice_ids': [],
            'orders': 0, 'order_ids': [], 'user_id': False, 'name': _('Sin vendedor'),
        })
        for inv in invoices:
            user = getattr(inv, sp_field, False) or inv.user_id
            uid = user.id if user else 0
            key = uid or 0
            b = buckets[key]
            b['user_id'] = uid
            b['name'] = user.name if user else _('Sin vendedor')
            b['sales'] += self._invoice_signed_untaxed(inv)
            b['invoices'] += 1
            b['invoice_ids'].append(inv.id)
            for line in inv.invoice_line_ids:
                b['margin'] += self._line_margin_amount(line)

        orders = self._orders_in_period(parsed, cache)
        for order in orders:
            uid = order.user_id.id if order.user_id else 0
            buckets[uid]['orders'] += 1
            buckets[uid]['order_ids'].append(order.id)
            if not buckets[uid]['user_id'] and order.user_id:
                buckets[uid]['user_id'] = uid
                buckets[uid]['name'] = order.user_id.name

        rows = sorted(buckets.values(), key=lambda r: r['sales'], reverse=True)[:limit]
        target_map = self._targets_by_user(parsed)
        result = []
        for idx, row in enumerate(rows, start=1):
            target = target_map.get(row['user_id'], 0.0)
            achievement = (row['sales'] / target * 100.0) if target else 0.0
            avg_ticket = row['sales'] / row['invoices'] if row['invoices'] else 0.0
            result.append({
                'rank': idx,
                'medal': idx if idx <= 3 else False,
                'user_id': row['user_id'],
                'name': row['name'],
                'sales': row['sales'],
                'margin': row['margin'],
                'margin_pct': (row['margin'] / row['sales'] * 100.0) if row['sales'] else 0.0,
                'invoices': row['invoices'],
                'orders': row['orders'],
                'avg_ticket': avg_ticket,
                'target': target,
                'achievement': achievement,
                'model': 'account.move',
                'domain': [(sp_field, '=', row['user_id'])] if row['user_id'] else [],
            })
        return {'rows': result, 'source': 'invoice'}

    @api.model
    def _targets_by_user(self, parsed):
        Target = self.env.get('commission.target')
        if not Target or 'hr.employee' not in self.env:
            return {}
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('scope', '=', 'employee'),
            ('period_start', '<=', parsed['date_to']),
            ('period_end', '>=', parsed['date_from']),
        ]
        by_user = {}
        for target in Target.search(domain):
            emp = target.employee_id
            if emp and emp.user_id:
                by_user[emp.user_id.id] = by_user.get(emp.user_id.id, 0.0) + target.target_amount
        return by_user

    @api.model
    def _targets_by_team(self, parsed):
        by_team = defaultdict(float)
        Target = self.env.get('commission.target')
        if not Target:
            return by_team
        domain = [
            ('company_id', '=', parsed['company'].id),
            ('scope', '=', 'employee'),
            ('period_start', '<=', parsed['date_to']),
            ('period_end', '>=', parsed['date_from']),
        ]
        for target in Target.search(domain):
            emp = target.employee_id
            if emp and emp.user_id and emp.user_id.sale_team_id:
                by_team[emp.user_id.sale_team_id.id] += target.target_amount
        branch_domain = [
            ('company_id', '=', parsed['company'].id),
            ('scope', '=', 'branch'),
            ('period_start', '<=', parsed['date_to']),
            ('period_end', '>=', parsed['date_from']),
        ]
        if parsed.get('branch_id'):
            branch_domain.append(('branch_id', '=', parsed['branch_id']))
        for target in Target.search(branch_domain):
            team = self.env['crm.team'].search([
                ('company_id', 'in', [False, parsed['company'].id]),
            ], limit=1)
            if team:
                by_team[team.id] += target.target_amount
        return by_team

    # ------------------------------------------------------------------
    # Rankings — equipos
    # ------------------------------------------------------------------

    @api.model
    def _build_team_ranking(self, parsed, limit=12, cache=None):
        invoices = self._invoices_in_period(parsed, cache)
        sp_field = self._salesperson_field()
        buckets = defaultdict(lambda: {
            'sales': 0.0, 'margin': 0.0, 'invoices': 0, 'members': set(),
            'team_id': False, 'name': _('Sin equipo'),
        })
        for inv in invoices:
            user = getattr(inv, sp_field, False) or inv.user_id
            team = user.sale_team_id if user else False
            tid = team.id if team else 0
            b = buckets[tid]
            b['team_id'] = tid
            b['name'] = team.name if team else _('Sin equipo')
            b['sales'] += self._invoice_signed_untaxed(inv)
            b['invoices'] += 1
            if user:
                b['members'].add(user.id)
            for line in inv.invoice_line_ids:
                b['margin'] += self._line_margin_amount(line)

        target_map = self._targets_by_team(parsed)
        rows = sorted(buckets.values(), key=lambda r: r['sales'], reverse=True)[:limit]
        sp_field = self._salesperson_field()
        result = []
        for idx, row in enumerate(rows, start=1):
            target = target_map.get(row['team_id'], 0.0)
            member_ids = list(row['members'])
            result.append({
                'rank': idx,
                'team_id': row['team_id'],
                'name': row['name'],
                'leader': self._team_leader_name(row['team_id']),
                'sales': row['sales'],
                'margin': row['margin'],
                'invoices': row['invoices'],
                'members_count': len(member_ids),
                'target': target,
                'achievement': (row['sales'] / target * 100.0) if target else 0.0,
                'model': 'account.move',
                'domain': [(sp_field, 'in', member_ids)] if member_ids else [],
            })
        return {'rows': result, 'source': 'invoice'}

    @api.model
    def _team_leader_name(self, team_id):
        if not team_id:
            return ''
        team = self.env['crm.team'].browse(team_id)
        return team.user_id.name if team.user_id else ''

    # ------------------------------------------------------------------
    # Productos
    # ------------------------------------------------------------------

    @api.model
    def _invoice_lines_in_period(self, parsed, cache=None):
        invoices = self._invoices_in_period(parsed, cache)
        if not invoices:
            return self.env['account.move.line']
        domain = [
            ('move_id', 'in', invoices.ids),
            ('display_type', '=', 'product'),
            ('product_id', '!=', False),
        ]
        if parsed.get('product_id'):
            domain.append(('product_id', '=', parsed['product_id']))
        if parsed.get('category_id'):
            domain.append(('product_id.categ_id', 'child_of', parsed['category_id']))
        return self.env['account.move.line'].search(domain)

    @api.model
    def _build_top_products(self, parsed, limit=15, cache=None):
        lines = self._invoice_lines_in_period(parsed, cache)
        if not lines:
            return {'rows': [], 'source': 'invoice_line'}

        grouped = lines._read_group(
            domain=[('id', 'in', lines.ids)],
            groupby=['product_id'],
            aggregates=['price_subtotal:sum', 'quantity:sum'],
        )
        rows = []
        for product, subtotal_sum, qty_sum in grouped:
            if not product:
                continue
            margin = 0.0
            plines = lines.filtered(lambda l, p=product: l.product_id == p)
            for line in plines:
                margin += self._line_margin_amount(line)
            qty = qty_sum or 0.0
            sales = subtotal_sum or 0.0
            rows.append({
                'product_id': product.id,
                'name': product.display_name,
                'sku': product.default_code or '',
                'category': product.categ_id.display_name if product.categ_id else '',
                'image_url': f'/web/image/product.product/{product.id}/image_128',
                'qty': qty,
                'sales': sales,
                'margin': margin,
                'margin_pct': (margin / sales * 100.0) if sales else 0.0,
                'stock_qty': product.qty_available if 'qty_available' in product._fields else 0.0,
                'model': 'account.move.line',
                'domain': [('product_id', '=', product.id)],
            })
        rows.sort(key=lambda r: r['sales'], reverse=True)
        return {'rows': rows[:limit], 'source': 'invoice_line'}

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------

    @api.model
    def _build_top_customers(self, parsed, limit=20, cache=None):
        invoices = self._invoices_in_period(parsed, cache)
        buckets = defaultdict(lambda: {
            'sales': 0.0, 'margin': 0.0, 'invoices': 0, 'partner_id': False,
            'name': '', 'last_purchase': False,
        })
        for inv in invoices:
            partner = inv.partner_id.commercial_partner_id
            if not partner:
                continue
            pid = partner.id
            b = buckets[pid]
            b['partner_id'] = pid
            b['name'] = partner.display_name
            b['sales'] += self._invoice_signed_untaxed(inv)
            b['invoices'] += 1
            inv_date = inv.invoice_date
            if inv_date and (not b['last_purchase'] or inv_date > b['last_purchase']):
                b['last_purchase'] = inv_date
            for line in inv.invoice_line_ids:
                b['margin'] += self._line_margin_amount(line)

        orders = self._orders_in_period(parsed, cache)
        order_count = defaultdict(int)
        for order in orders:
            partner = order.partner_id.commercial_partner_id
            if partner:
                order_count[partner.id] += 1

        today = parsed['date_to']
        rows = sorted(buckets.values(), key=lambda r: r['sales'], reverse=True)[:limit]
        result = []
        for row in rows:
            pid = row['partner_id']
            last = row['last_purchase']
            days_since = (today - last).days if last else None
            avg_ticket = row['sales'] / row['invoices'] if row['invoices'] else 0.0
            segment = self._customer_segment(days_since, row['invoices'], row['sales'])
            result.append({
                'partner_id': pid,
                'name': row['name'],
                'city': self.env['res.partner'].browse(pid).city or '',
                'country': self.env['res.partner'].browse(pid).country_id.name or '',
                'sales': row['sales'],
                'margin': row['margin'],
                'orders': order_count.get(pid, 0),
                'invoices': row['invoices'],
                'avg_ticket': avg_ticket,
                'last_purchase': fields.Date.to_string(last) if last else '',
                'days_since': days_since,
                'segment': segment,
                'model': 'res.partner',
                'domain': [('id', '=', pid)],
            })
        return {'rows': result, 'source': 'invoice'}

    @api.model
    def _customer_segment(self, days_since, invoice_count, sales):
        if days_since is None:
            return _('Nuevo')
        if days_since > 180:
            return _('Inactivo')
        if days_since > 90:
            return _('En riesgo')
        if invoice_count >= 5 and sales > 0:
            return _('VIP')
        if invoice_count <= 1:
            return _('Nuevo')
        return _('Frecuente')

    # ------------------------------------------------------------------
    # Pipeline CRM
    # ------------------------------------------------------------------

    @api.model
    def _open_leads(self, parsed):
        domain = self._crm_domain(parsed, [
            ('type', '=', 'opportunity'),
            ('probability', '<', 100),
        ])
        if parsed.get('team_id'):
            domain.append(('team_id', '=', parsed['team_id']))
        return self.env['crm.lead'].search(domain)

    @api.model
    def _build_pipeline_funnel(self, parsed, cache=None):
        leads = self._open_leads(parsed)
        stage_data = defaultdict(lambda: {
            'count': 0, 'expected': 0.0, 'weighted': 0.0, 'prob_sum': 0.0,
            'lead_ids': [], 'stage_id': False, 'name': _('Sin etapa'),
            'sequence': 999,
        })
        for lead in leads:
            stage = lead.stage_id
            sid = stage.id if stage else 0
            b = stage_data[sid]
            b['stage_id'] = sid
            b['name'] = stage.name if stage else _('Sin etapa')
            b['sequence'] = stage.sequence if stage else 999
            b['count'] += 1
            exp = lead.expected_revenue or 0.0
            prob = lead.probability or 0.0
            b['expected'] += exp
            b['weighted'] += exp * prob / 100.0
            b['prob_sum'] += prob
            b['lead_ids'].append(lead.id)

        rows = sorted(stage_data.values(), key=lambda r: r['sequence'])
        for row in rows:
            row['avg_probability'] = row['prob_sum'] / row['count'] if row['count'] else 0.0
            row['model'] = 'crm.lead'
            row['domain'] = [('stage_id', '=', row['stage_id'])] if row['stage_id'] else []
            del row['prob_sum']
            del row['lead_ids']
        return {
            'rows': rows,
            'totals': {
                'count': len(leads),
                'expected': sum(leads.mapped('expected_revenue')),
                'weighted': sum(
                    (l.expected_revenue or 0.0) * (l.probability or 0.0) / 100.0
                    for l in leads
                ),
            },
            'source': 'crm',
        }

    @api.model
    def _build_pipeline_chart(self, parsed, cache=None):
        funnel = self._build_pipeline_funnel(parsed)
        rows = funnel.get('rows', [])
        return {
            'id': 'pipeline_funnel',
            'title': _('Pipeline comercial'),
            'subtitle': _('Oportunidades abiertas por etapa'),
            'labels': [r['name'] for r in rows],
            'series': [{
                'name': _('Valor esperado'),
                'key': 'expected',
                'data': [r['expected'] for r in rows],
                'type': 'funnel',
            }],
            'counts': [r['count'] for r in rows],
            'stage_ids': [r['stage_id'] for r in rows],
            'drilldown': {'enabled': True, 'model': 'crm.lead'},
        }

    # ------------------------------------------------------------------
    # Tablas paginadas
    # ------------------------------------------------------------------

    @api.model
    def _table_columns_payload(self, table_key):
        spec = TABLE_REGISTRY[table_key]
        return [
            {'key': k, 'label': _(COLUMN_LABELS.get(lk, lk)), 'type': typ, 'sortable': True}
            for k, lk, typ in spec['columns']
        ]

    @api.model
    def _table_recent_documents(self, parsed, table_key, page, page_size, search, order):
        is_invoice = table_key == 'recent_invoices'
        if is_invoice:
            records = self._invoices_in_period(parsed, None)
            Model = self.env['account.move']
            sp_field = self._salesperson_field()
        else:
            records = self._orders_in_period(parsed, None)
            Model = self.env['sale.order']
            sp_field = 'user_id'

        if search:
            needle = search.lower()
            if is_invoice:
                records = records.filtered(
                    lambda m: needle in (m.name or '').lower()
                    or needle in (m.partner_id.display_name or '').lower()
                )
            else:
                records = records.filtered(
                    lambda o: needle in (o.name or '').lower()
                    or needle in (o.partner_id.display_name or '').lower()
                )

        sort_field = (order.split()[0] if order else 'date')
        reverse = order.endswith('desc') if order else True
        if is_invoice:
            key_fn = lambda m: m.invoice_date or m.date or fields.Date.today()
            if sort_field == 'amount':
                key_fn = lambda m: m.amount_untaxed
            elif sort_field == 'name':
                key_fn = lambda m: m.name or ''
            elif sort_field == 'partner':
                key_fn = lambda m: m.partner_id.display_name or ''
        else:
            key_fn = lambda o: o.date_order
            if sort_field == 'amount':
                key_fn = lambda o: o.amount_untaxed
            elif sort_field == 'name':
                key_fn = lambda o: o.name or ''
            elif sort_field == 'partner':
                key_fn = lambda o: o.partner_id.display_name or ''

        sorted_recs = sorted(records, key=key_fn, reverse=reverse)
        total = len(sorted_recs)
        pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size
        page_recs = sorted_recs[offset:offset + page_size]

        rows = []
        for rec in page_recs:
            if is_invoice:
                user = getattr(rec, sp_field, False) or rec.user_id
                rows.append({
                    'id': rec.id,
                    'model': 'account.move',
                    'date': fields.Date.to_string(rec.invoice_date or rec.date),
                    'name': rec.name,
                    'partner': rec.partner_id.display_name,
                    'salesperson': user.name if user else '',
                    'amount': self._invoice_signed_untaxed(rec),
                    'state': dict(rec._fields['state'].selection).get(rec.state, rec.state),
                })
            else:
                rows.append({
                    'id': rec.id,
                    'model': 'sale.order',
                    'date': fields.Datetime.to_string(rec.date_order) if rec.date_order else '',
                    'name': rec.name,
                    'partner': rec.partner_id.display_name,
                    'salesperson': rec.user_id.name if rec.user_id else '',
                    'amount': rec.amount_untaxed,
                    'state': dict(rec._fields['state'].selection).get(rec.state, rec.state),
                })

        return {
            'rows': rows,
            'columns': self._table_columns_payload(table_key),
            'total': total,
            'pages': pages,
            'page': page,
        }

    @api.model
    def _table_top_customers(self, parsed, page, page_size, search, order):
        data = self._build_top_customers(parsed, limit=500)
        rows = data.get('rows', [])
        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in (r.get('name') or '').lower()]
        sort_field = order.split()[0] if order else 'sales'
        reverse = order.endswith('desc') if order else True
        rows.sort(key=lambda r: r.get(sort_field) or 0, reverse=reverse)
        return self._paginate_rows(rows, page, page_size, 'top_customers_table')

    @api.model
    def _table_top_products(self, parsed, page, page_size, search, order):
        data = self._build_top_products(parsed, limit=500)
        rows = data.get('rows', [])
        if search:
            needle = search.lower()
            rows = [
                r for r in rows
                if needle in (r.get('name') or '').lower()
                or needle in (r.get('sku') or '').lower()
            ]
        sort_field = order.split()[0] if order else 'sales'
        reverse = order.endswith('desc') if order else True
        rows.sort(key=lambda r: r.get(sort_field) or 0, reverse=reverse)
        return self._paginate_rows(rows, page, page_size, 'top_products_table')

    @api.model
    def _paginate_rows(self, rows, page, page_size, table_key):
        total = len(rows)
        pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size
        page_rows = rows[offset:offset + page_size]
        out_rows = []
        for row in page_rows:
            if table_key == 'top_customers_table':
                out_rows.append({
                    'id': row['partner_id'],
                    'model': 'res.partner',
                    'name': row['name'],
                    'sales': row['sales'],
                    'orders': row['orders'],
                    'avg_ticket': row['avg_ticket'],
                    'last_purchase': row['last_purchase'],
                    'segment': row.get('segment', ''),
                })
            else:
                out_rows.append({
                    'id': row['product_id'],
                    'model': 'product.product',
                    'name': row['name'],
                    'sku': row['sku'],
                    'qty': row['qty'],
                    'sales': row['sales'],
                    'margin': row['margin'],
                })
        return {
            'rows': out_rows,
            'columns': self._table_columns_payload(table_key),
            'total': total,
            'pages': pages,
            'page': page,
        }

    @api.model
    def _drilldown_action(self, parsed, metric, extra_domain):
        action = super()._drilldown_action(parsed, metric, extra_domain)
        pipeline_metrics = {
            'pipeline_stage': ('crm.lead', extra_domain),
        }
        if metric in pipeline_metrics:
            model, domain = pipeline_metrics[metric]
            return self._act_window_action(
                _('Oportunidades'), model, 'list,form', domain, {'create': False},
            )
        return action
