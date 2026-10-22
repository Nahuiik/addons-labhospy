# -*- coding: utf-8 -*-
from odoo import models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _gn_pack_get_production_location(self):
        """Ubicación virtual de producción para transformaciones paquete → unidad."""
        self.ensure_one()
        Location = self.env['stock.location']
        default_loc_id = self.env['ir.default']._get(
            'product.template', 'property_stock_production', company_id=self.id,
        )
        if default_loc_id:
            location = Location.browse(default_loc_id)
            if location.exists() and location.company_id.id in (False, self.id):
                return location
        location = Location.search([
            ('company_id', '=', self.id),
            ('usage', '=', 'production'),
        ], limit=1)
        if location:
            return location
        self._create_production_location()
        default_loc_id = self.env['ir.default']._get(
            'product.template', 'property_stock_production', company_id=self.id,
        )
        return Location.browse(default_loc_id)
