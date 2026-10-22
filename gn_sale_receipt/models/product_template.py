# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo import _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    for_sale_receipt = fields.Boolean(
        string="Es para recibo de ventas",
        default=False,
        help="Marcar este producto como disponible para recibos de venta. Solo aplica para productos tipo servicio.",
    )
    
    def write(self, vals):
        """Validar que solo productos tipo servicio puedan marcarse como para recibos de venta"""
        if 'for_sale_receipt' in vals and vals['for_sale_receipt']:
            for product in self:
                product_type = vals.get('type', product.type)
                if product_type != 'service':
                    raise ValidationError(
                        _("Solo los productos tipo 'Servicio' pueden marcarse como 'Es para recibo de ventas'.")
                    )
        
        # Si se cambia el tipo de producto a algo distinto de 'service', desmarcar for_sale_receipt
        if 'type' in vals and vals['type'] != 'service':
            for product in self:
                if product.for_sale_receipt:
                    vals['for_sale_receipt'] = False
        
        return super().write(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Validar que solo productos tipo servicio puedan marcarse como para recibos de venta"""
        for vals in vals_list:
            if vals.get('for_sale_receipt') and vals.get('type') != 'service':
                raise ValidationError(
                    _("Solo los productos tipo 'Servicio' pueden marcarse como 'Es para recibo de ventas'.")
                )
        return super().create(vals_list)

