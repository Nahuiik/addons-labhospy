# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    traceability_move_count = fields.Integer(
        compute='_compute_traceability_move_count',
        string='Traceability Events',
    )

    @api.depends('product_id')
    def _compute_traceability_move_count(self):
        service = self.env['product.traceability.service']
        has_access = self.env.user.has_group(
            'gn_product_traceability_widget.group_traceability_user'
        )
        for lot in self:
            if not has_access:
                lot.traceability_move_count = 0
                continue
            try:
                lot.traceability_move_count = service.count_traceability_events(lot_id=lot.id)
            except Exception:
                lot.traceability_move_count = 0

    def action_open_traceability(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_product_traceability_dashboard',
            'name': self.name,
            'params': {
                'product_id': self.product_id.id,
                'product_tmpl_id': self.product_id.product_tmpl_id.id,
                'lot_id': self.id,
            },
        }
