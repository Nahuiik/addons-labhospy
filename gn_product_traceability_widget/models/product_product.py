# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    traceability_move_count = fields.Integer(
        compute='_compute_traceability_move_count',
        string='Traceability Events',
    )

    @api.depends('product_tmpl_id')
    def _compute_traceability_move_count(self):
        service = self.env['product.traceability.service']
        has_access = self.env.user.has_group(
            'gn_product_traceability_widget.group_traceability_user'
        )
        for product in self:
            if not has_access:
                product.traceability_move_count = 0
                continue
            try:
                product.traceability_move_count = service.count_traceability_events(
                    product_id=product.id,
                )
            except Exception:
                product.traceability_move_count = 0

    def action_open_traceability(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_product_traceability_dashboard',
            'name': self.display_name,
            'params': {
                'product_id': self.id,
                'product_tmpl_id': self.product_tmpl_id.id,
            },
        }
