# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.fields import Domain
from odoo.tools.misc import format_datetime


class StockQuantityHistory(models.TransientModel):
    _inherit = 'stock.quantity.history'

    def open_at_date(self):
        """Misma vista Existencias (filtros Almacenes/Categoría) con to_date."""
        self.ensure_one()
        tree_view_id = self.env.ref('stock.product_product_stock_tree').id
        form_view_id = self.env.ref('stock.product_form_view_procurement_button').id
        search_view_id = self.env.ref('stock.product_search_form_view_stock_report').id

        domain = Domain('is_storable', '=', True)
        product_id = self.env.context.get('product_id', False)
        product_tmpl_id = self.env.context.get('product_tmpl_id', False)
        if product_id:
            domain &= Domain('id', '=', product_id)
        elif product_tmpl_id:
            domain &= Domain('product_tmpl_id', '=', product_tmpl_id)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock'),
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'views': [(tree_view_id, 'list'), (form_view_id, 'form')],
            'search_view_id': [search_view_id],
            'domain': domain,
            'context': dict(self.env.context, to_date=self.inventory_datetime),
            'display_name': format_datetime(self.env, self.inventory_datetime),
        }
