# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    gn_unpack_dest_product_id = fields.Many2one(
        'product.product',
        string='Producto destino (unidad)',
        domain="[('is_storable', '=', True)]",
        help='Producto unidad al que se transforma este empaque (ej. pack 15 → botella).',
    )
    gn_unpack_ratio = fields.Float(
        string='Unidades por paquete',
        digits='Product Unit',
        help='Cantidad de unidades destino generadas por cada unidad de producto origen.',
    )

    def _gn_pack_get_unpack_defaults(self, product=None):
        self.ensure_one()
        if not product:
            product = (
                self.product_variant_id
                if self.product_variant_count == 1
                else self.env['product.product']
            )
        dest = self.gn_unpack_dest_product_id
        return {
            'source_uom_id': self.uom_id.id if self.uom_id else False,
            'dest_product_id': dest.id if dest else False,
            'dest_uom_id': dest.uom_id.id if dest else False,
            'unpack_ratio': self.gn_unpack_ratio or 0.0,
        }

    def action_gn_pack_open_transform(self):
        self.ensure_one()
        if self.product_variant_count != 1:
            raise UserError(
                _('Configure la transformación en un producto con una sola variante.')
            )
        if not self.is_storable:
            raise UserError(
                _('El producto origen debe ser almacenable (seguimiento de inventario activo).')
            )
        product = self.product_variant_id
        if not self.gn_unpack_dest_product_id:
            raise UserError(
                _('Indique el producto destino (unidad) antes de transformar.')
            )
        if not self.gn_unpack_ratio:
            raise UserError(_('Indique las unidades por paquete (relación origen → destino).'))
        defaults = self._gn_pack_get_unpack_defaults(product)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transformar paquete'),
            'res_model': 'gn.pack.transform',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_source_product_id': product.id,
                'default_source_uom_id': defaults['source_uom_id'],
                'default_dest_product_id': defaults['dest_product_id'],
                'default_dest_uom_id': defaults['dest_uom_id'],
                'default_unpack_ratio': defaults['unpack_ratio'],
                'default_source_qty': 1.0,
            },
        }
