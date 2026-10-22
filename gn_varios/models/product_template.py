# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    has_warranty = fields.Boolean(string='Tiene Garantía', default=False)
    warranty_time_id = fields.Many2one(
        'gn.warranty.time',
        string='Tiempo de Garantía',
        ondelete='set null',
    )
    country_of_origin_id = fields.Many2one(
        'res.country',
        string='País de Origen',
        ondelete='set null',
    )

    @api.constrains('has_warranty', 'warranty_time_id')
    def _check_warranty_time_when_enabled(self):
        for template in self:
            if template.has_warranty and not template.warranty_time_id:
                raise ValidationError(
                    _('Debe seleccionar un tiempo de garantía cuando "Tiene Garantía" está activo.')
                )
