# -*- coding: utf-8 -*-
"""UI: tablas paginadas y drill-down extendido."""

from odoo import _, api, models
from odoo.fields import Domain


TABLE_DEFS = {
    'top_vendors': {
        'columns': [
            {'key': 'name', 'label': _('Proveedor'), 'sortable': True},
            {'key': 'purchases', 'label': _('Compras'), 'type': 'currency', 'sortable': True},
            {'key': 'share_pct', 'label': _('%'), 'type': 'number', 'sortable': True},
            {'key': 'avg_lead_days', 'label': _('Lead time'), 'type': 'number', 'sortable': True},
            {'key': 'delays', 'label': _('Retrasos'), 'type': 'number', 'sortable': True},
            {'key': 'price_var_pct', 'label': _('Var. precio %'), 'type': 'number', 'sortable': True},
        ],
        'widget': 'top_vendors',
    },
    'price_variation': {
        'columns': [
            {'key': 'name', 'label': _('Producto'), 'sortable': True},
            {'key': 'last_price', 'label': _('Último'), 'type': 'currency', 'sortable': True},
            {'key': 'avg_price', 'label': _('Promedio'), 'type': 'currency', 'sortable': True},
            {'key': 'min_price', 'label': _('Mínimo'), 'type': 'currency', 'sortable': True},
            {'key': 'max_price', 'label': _('Máximo'), 'type': 'currency', 'sortable': True},
            {'key': 'variation_pct', 'label': _('Var %'), 'type': 'number', 'sortable': True},
        ],
        'widget': 'price_variation',
    },
    'buyers': {
        'columns': [
            {'key': 'name', 'label': _('Comprador'), 'sortable': True},
            {'key': 'amount', 'label': _('Monto'), 'type': 'currency', 'sortable': True},
            {'key': 'orders', 'label': _('OC'), 'type': 'number', 'sortable': True},
            {'key': 'avg_cycle', 'label': _('Ciclo prom.'), 'type': 'number', 'sortable': True},
            {'key': 'savings', 'label': _('Ahorro'), 'type': 'currency', 'sortable': True},
            {'key': 'compliance_pct', 'label': _('Cumplimiento %'), 'type': 'number', 'sortable': True},
        ],
        'widget': 'buyers',
    },
    'products': {
        'columns': [
            {'key': 'name', 'label': _('Producto'), 'sortable': True},
            {'key': 'qty', 'label': _('Cantidad'), 'type': 'number', 'sortable': True},
            {'key': 'amount', 'label': _('Monto'), 'type': 'currency', 'sortable': True},
            {'key': 'avg_price', 'label': _('Precio prom.'), 'type': 'currency', 'sortable': True},
            {'key': 'growth_pct', 'label': _('Crecimiento %'), 'type': 'number', 'sortable': True},
            {'key': 'last_purchase', 'label': _('Última compra'), 'sortable': True},
        ],
        'widget': 'products',
    },
}


class PurchaseDashboardUI(models.AbstractModel):
    _inherit = 'purchase.dashboard.service'

    @api.model
    def get_default_widget_layout(self):
        self._check_dashboard_access()
        return {
            'widgets': [],
            'hidden': [],
            'pinned': [],
            'favorites': [],
            'heatmapDimension': 'month_vendor',
        }

    @api.model
    def get_table_page(self, filters=None, table_key='top_vendors', page=1, page_size=20, search='', order=''):
        self._check_dashboard_access()
        spec = TABLE_DEFS.get(table_key)
        if not spec:
            return {'rows': [], 'columns': [], 'total': 0, 'pages': 1}
        parsed = self._parse_filters(filters or {})
        cache = {}
        widget = self._widget_builders()[spec['widget']](parsed, cache)
        rows = widget.get('rows') or widget.get('top') or []
        if search:
            q = search.lower()
            rows = [r for r in rows if q in str(r.get('name', '')).lower()]
        sort_field, sort_dir = 'purchases', 'desc'
        if order:
            parts = order.split()
            sort_field = parts[0]
            sort_dir = parts[1] if len(parts) > 1 else 'desc'
        reverse = sort_dir != 'asc'
        rows.sort(key=lambda r: r.get(sort_field) or 0, reverse=reverse)
        total = len(rows)
        page_size = max(1, min(int(page_size or 20), 500))
        page = max(1, int(page or 1))
        pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        return {
            'rows': rows[start:start + page_size],
            'columns': spec['columns'],
            'total': total,
            'pages': pages,
            'page': page,
        }

    @api.model
    def get_entity_drilldown(self, filters=None, model='purchase.order', domain=None, name=None):
        self._check_dashboard_access()
        parsed = self._parse_filters(filters or {})
        base = self._po_base_domain(parsed) if model == 'purchase.order' else []
        full_domain = Domain.AND([base, domain or []]) if base else (domain or [])
        titles = {
            'purchase.order': _('Órdenes de compra'),
            'res.partner': _('Proveedor'),
            'product.product': _('Producto'),
            'account.move': _('Facturas'),
            'stock.picking': _('Recepciones'),
            'account.payment': _('Pagos'),
        }
        return {
            'type': 'ir.actions.act_window',
            'name': name or titles.get(model, model),
            'res_model': model,
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': full_domain,
            'target': 'current',
        }

    @api.model
    def get_drilldown_chain(self, filters=None):
        self._check_dashboard_access()
        return [
            {'id': 'company', 'label': _('Empresa'), 'model': 'purchase.order', 'metric': 'total_purchased'},
            {'id': 'vendor', 'label': _('Proveedor'), 'model': 'res.partner', 'metric': 'active_vendors'},
            {'id': 'category', 'label': _('Categoría'), 'model': 'purchase.order', 'metric': 'total_purchased'},
            {'id': 'product', 'label': _('Producto'), 'model': 'product.product', 'metric': 'total_purchased'},
            {'id': 'order', 'label': _('Orden'), 'model': 'purchase.order', 'metric': 'po_count'},
            {'id': 'receipt', 'label': _('Recepción'), 'model': 'stock.picking',
             'domain': [('picking_type_code', '=', 'incoming')]},
            {'id': 'invoice', 'label': _('Factura'), 'model': 'account.move',
             'domain': [('move_type', 'in', ('in_invoice', 'in_refund'))]},
            {'id': 'payment', 'label': _('Pago'), 'model': 'account.payment',
             'domain': [('payment_type', '=', 'outbound')]},
        ]
