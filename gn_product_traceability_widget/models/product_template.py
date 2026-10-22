# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    traceability_move_count = fields.Integer(
        compute='_compute_traceability_move_count',
        string='Traceability Events',
    )

    @api.depends('product_variant_ids')
    def _compute_traceability_move_count(self):
        service = self.env['product.traceability.service']
        has_access = self.env.user.has_group(
            'gn_product_traceability_widget.group_traceability_user'
        )
        for tmpl in self:
            if not has_access:
                tmpl.traceability_move_count = 0
                continue
            try:
                tmpl.traceability_move_count = service.count_traceability_events(
                    product_tmpl_id=tmpl.id,
                )
            except Exception:
                tmpl.traceability_move_count = 0

    def action_open_traceability(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'gn_product_traceability_dashboard',
            'name': self.display_name,
            'params': {
                'product_tmpl_id': self.id,
                'product_id': self.product_variant_id.id if self.product_variant_count == 1 else False,
            },
        }
